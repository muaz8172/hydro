#!/usr/bin/env python3
"""
Hydro dashboard server (offline, standard library only)
- Serves the dashboard page (frontend/) on port 8000, like `python3 -m http.server`
- Adds a small read-only history API over the session CSVs that bridge.py writes:
    GET /api/history?range=1h|24h|7d            readings on a fixed time grid (null = no data)
    GET /api/actuators/history?range=...        pump ON intervals + runs/on-time per pump
    GET /api/vision/history?range=...           rows from data/vision/vision_log.csv
    GET /api/export.csv?range=...               every session CSV row in the range, one file
Bucket sizes: 1h = 2 s (raw), 24h = 60 s, 7d = 600 s. Each bucket is the mean of its rows.

Run: python3 backend/server.py   (hydro-dashboard.service does this at boot)
"""

import csv
import io
import json
import os
import re
import sys
import time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # repo root (backend/..)
FRONTEND = os.path.join(ROOT, "frontend")
LOG_DIR = os.path.join(ROOT, "data", "logs")
VISION_CSV = os.path.join(ROOT, "data", "vision", "vision_log.csv")
PORT = int(os.environ.get("HYDRO_DASH_PORT", "8000"))

RANGES = {"1h": (3600, 2), "24h": (86400, 60), "7d": (7 * 86400, 600)}
SERIES = ["ph", "ec", "temp", "hum", "level_pct"]
PUMPS = ["pump_a", "pump_b", "pump_sample"]
GAP_S = 10                      # no row for this long = ESP32/bridge gap (rows come every 2 s)
NAME_RE = re.compile(r"log_(\d+)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.csv$")

_cache = {}                     # path -> (mtime, size, rows)


def num(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def read_log(path):
    """Parsed rows of one session CSV: list of (ts, dict). Cached until the file changes."""
    st = os.stat(path)
    hit = _cache.get(path)
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2]
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                ts = datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S").timestamp()
            except (KeyError, TypeError, ValueError):
                continue                                  # half-written last line
            rows.append((ts, r))
    _cache[path] = (st.st_mtime, st.st_size, rows)
    return rows


def logs_in(start, end):
    """Session CSVs that can hold rows between start and end, oldest first."""
    out = []
    if not os.path.isdir(LOG_DIR):
        return out
    for name in os.listdir(LOG_DIR):
        m = NAME_RE.match(name)
        if not m:
            continue
        path = os.path.join(LOG_DIR, name)
        opened = datetime.strptime(m.group(2), "%Y-%m-%d_%H-%M-%S").timestamp()
        if opened <= end and os.path.getmtime(path) >= start:
            out.append((int(m.group(1)), path))
    return [p for _, p in sorted(out)]


def rows_in(start, end):
    for path in logs_in(start, end):
        for ts, r in read_log(path):
            if start <= ts <= end:
                yield ts, r, path


def parse_range(q):
    key = (q.get("range") or ["24h"])[0]
    if key not in RANGES:
        key = "24h"
    span, bucket = RANGES[key]
    end = time.time()
    return key, end - span, end, bucket


def history(q):
    key, start, end, bucket = parse_range(q)
    n = int((end - start) // bucket)
    start = end - n * bucket
    sums = {s: [0.0] * n for s in SERIES}
    cnts = {s: [0] * n for s in SERIES}
    for ts, r, _ in rows_in(start, end):
        i = min(n - 1, int((ts - start) // bucket))
        for s in SERIES:
            v = num(r.get(s))
            if s == "ec" and r.get("ec_low") == "1":
                v = None                                  # below the sensor floor, not a real value
            if s == "ph" and v is not None and not 0 <= v <= 14:
                v = None                                  # outside the pH scale: probe fault, not a reading
            if v is not None:
                sums[s][i] += v
                cnts[s][i] += 1
    out = {"range": key, "start": start, "end": end, "bucket": bucket,
           "t": [round(start + (i + 1) * bucket) for i in range(n)]}
    for s in SERIES:
        out[s] = [round(sums[s][i] / cnts[s][i], 3) if cnts[s][i] else None for i in range(n)]
    return out


def actuators(q):
    key, start, end, _ = parse_range(q)
    out = {"range": key, "start": start, "end": end, "pumps": {}}
    for p in PUMPS:
        runs, on_s, cur, last_ts, last_path = [], 0.0, None, None, None
        for ts, r, path in rows_in(start, end):
            if cur and (path != last_path or ts - last_ts > GAP_S):
                runs.append({"start": cur, "end": last_ts, "cut": True})   # data stopped mid-run
                cur = None
            v = r.get(p)
            if v == "1" and cur is None:
                cur = ts
            elif v != "1" and cur is not None:
                runs.append({"start": cur, "end": ts, "cut": False})
                cur = None
            last_ts, last_path = ts, path
        if cur is not None:
            live = end - last_ts <= GAP_S
            runs.append({"start": cur, "end": end if live else last_ts, "cut": not live, "open": live})
        on_s = sum(x["end"] - x["start"] for x in runs)
        out["pumps"][p] = {"runs": runs, "count": len(runs), "on_seconds": round(on_s)}
    return out


def vision(q):
    key, start, end, _ = parse_range(q)
    rows = []
    if os.path.exists(VISION_CSV):
        with open(VISION_CSV, newline="") as f:
            for r in csv.DictReader(f):
                try:
                    ts = datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S").timestamp()
                except (KeyError, TypeError, ValueError):
                    continue
                if start <= ts <= end:
                    rows.append({"ts": ts, "stage": r.get("stage") or None,
                                 "stage_conf": num(r.get("stage_conf")), "size": r.get("size") or None,
                                 "health": r.get("health") or None})
    return {"range": key, "start": start, "end": end, "rows": rows}


def export_csv(q):
    key, start, end, _ = parse_range(q)
    rows = [r for _, r, _ in rows_in(start, end)]
    if not rows:
        return key, "no rows in this range\n"
    fields = list(dict.fromkeys(k for r in rows for k in r))   # older logs lack the pump columns
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, restval="")
    w.writeheader()
    w.writerows(rows)
    return key, buf.getvalue()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=FRONTEND, **kw)

    def send_json(self, obj):
        body = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/api/history":
                return self.send_json(history(q))
            if u.path == "/api/actuators/history":
                return self.send_json(actuators(q))
            if u.path == "/api/vision/history":
                return self.send_json(vision(q))
            if u.path == "/api/export.csv":
                key, text = export_csv(q)
                body = text.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="hydro_{key}_{datetime.now():%Y-%m-%d_%H-%M}.csv"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        except Exception as e:                            # never take the page down with the API
            print(f"[api] {u.path}: {e!r}", file=sys.stderr, flush=True)
            self.send_error(500, str(e))
            return
        if u.path.startswith("/api/"):
            return self.send_error(404)
        super().do_GET()

    def end_headers(self):
        if self.path.startswith("/live/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):                    # quiet: the page polls every few seconds
        if not str(args[1] if len(args) > 1 else "").startswith(("2", "3")):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    print(f"[dash] http://0.0.0.0:{PORT}  (logs: {LOG_DIR})", flush=True)
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
