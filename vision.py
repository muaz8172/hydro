#!/usr/bin/env python3
"""
Plant camera -> MQTT (offline, local only)
- Every 10 s it fetches a photo from the MaixCAM over USB (http://10.122.173.1:8080/snap.jpg,
  served by maixcam/hydro_cam/main.py), checks it and publishes it live for the dashboard
- Every 15 min (and when "snap" is sent to hydro/vision/cmd) it also saves the photo to
  data/vision/YYYY-MM-DD/HH-MM-SS.jpg and appends a row to data/vision/vision_log.csv
  (saving every 10 s would be ~150 MB/day)
- Checks leaf colour (green vs yellow/brown share) and gives a health result:
  healthy / check / unhealthy / no_plant. This is a colour rule, not an AI model (no dataset yet)
- Publishes (retained, so a reloaded dashboard gets the last one at once):
    hydro/vision        JSON result
    hydro/vision/image  the JPEG itself (binary)
    hydro/vision/status "online" / "offline: <reason>"
- Photos older than 30 days are deleted, except the first photo of each day

Test with: python3 vision.py --once
"""

import csv
import io
import json
import os
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt
from PIL import Image, ImageChops, ImageStat

CAM_URL    = os.environ.get("HYDRO_CAM_URL", "http://10.122.173.1:8080/snap.jpg")
INTERVAL      = int(os.environ.get("HYDRO_VISION_INTERVAL", "10"))        # s between live photos
SAVE_INTERVAL = int(os.environ.get("HYDRO_VISION_SAVE_INTERVAL", "900"))  # s between saved photos
KEEP_DAYS  = 30
BROKER     = "localhost"

TOPIC_RESULT = "hydro/vision"
TOPIC_IMAGE  = "hydro/vision/image"
TOPIC_STATUS = "hydro/vision/status"
TOPIC_CMD    = "hydro/vision/cmd"

VISION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vision")
CSV_PATH   = os.path.join(VISION_DIR, "vision_log.csv")
CSV_FIELDS = ["time", "image", "canopy_pct", "yellow_pct", "greenness", "health", "reasons"]

# Only look at this part of the photo (fractions: left, top, right, bottom), to skip
# walls/trays around the plants. (0, 0, 1, 1) = whole photo.
ROI = (0.0, 0.0, 1.0, 1.0)

# Colour bands in PIL HSV (all 0-255; hue 255 = 360 deg)
MIN_SAT, MIN_VAL = 50, 40           # below this = grey/white/black background, not plant
GREEN_HUE  = (45, 120)              # ~63-170 deg
YELLOW_HUE = (25, 44)               # ~35-62 deg
BROWN_HUE  = (10, 24)               # ~14-34 deg (only dark enough pixels count; red/pink excluded)
BROWN_MAX_VAL = 170

# Health rules (yellow/brown share of the plant area, %)
CHECK_YELLOW_PCT     = 8
UNHEALTHY_YELLOW_PCT = 20
MIN_GREEN_PCT        = 2            # less GREEN than this in view -> "no_plant" (so red/orange
                                    # objects alone never count as a sick plant)

snap_requested = False


# ================= Leaf colour check =================
def band(channel, lo, hi):
    """255 where lo <= value <= hi, else 0."""
    return channel.point(lambda x: 255 if lo <= x <= hi else 0)


def count(mask):
    return mask.histogram()[255]


def analyse(jpeg):
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    w, h = img.size
    img = img.crop((int(ROI[0] * w), int(ROI[1] * h), int(ROI[2] * w), int(ROI[3] * h)))
    img.thumbnail((320, 320))                       # plenty for colour shares, and fast
    hue, sat, val = img.convert("HSV").split()

    coloured = ImageChops.multiply(band(sat, MIN_SAT, 255), band(val, MIN_VAL, 255))
    green  = ImageChops.multiply(coloured, band(hue, *GREEN_HUE))
    yellow = ImageChops.multiply(coloured, band(hue, *YELLOW_HUE))
    brown  = ImageChops.multiply(ImageChops.multiply(coloured, band(hue, *BROWN_HUE)),
                                 band(val, 0, BROWN_MAX_VAL))

    total = img.width * img.height
    g, y, b = count(green), count(yellow), count(brown)
    canopy = g + y + b
    canopy_pct = 100 * canopy / total
    yellow_pct = 100 * (y + b) / canopy if canopy else 0.0

    # Excess-green index over the plant pixels: (2G - R - B) / (R + G + B), -1..1, higher = greener
    plant_mask = ImageChops.lighter(ImageChops.lighter(green, yellow), brown)
    if canopy:
        r_, g_, b_ = ImageStat.Stat(img, plant_mask).mean
        greenness = (2 * g_ - r_ - b_) / max(r_ + g_ + b_, 1)
    else:
        greenness = None

    reasons = []
    if 100 * g / total < MIN_GREEN_PCT:
        health = "no_plant"
        canopy_pct = yellow_pct = greenness = None   # too few plant pixels to mean anything
        reasons.append("No plant in view (check camera aim / grow light)")
    elif yellow_pct > UNHEALTHY_YELLOW_PCT:
        health = "unhealthy"
        reasons.append(f"Yellow/brown leaf area {yellow_pct:.0f}% (> {UNHEALTHY_YELLOW_PCT}%)")
    elif yellow_pct > CHECK_YELLOW_PCT:
        health = "check"
        reasons.append(f"Yellow/brown leaf area {yellow_pct:.0f}% (> {CHECK_YELLOW_PCT}%)")
    else:
        health = "healthy"

    return {
        "canopy_pct": None if canopy_pct is None else round(canopy_pct, 1),
        "yellow_pct": None if yellow_pct is None else round(yellow_pct, 1),
        "greenness":  None if greenness is None else round(greenness, 3),
        "health":     health,
        "health_reasons": reasons,
    }


# ================= Storage =================
def save(jpeg, now):
    rel = os.path.join(now.strftime("%Y-%m-%d"), now.strftime("%H-%M-%S") + ".jpg")
    path = os.path.join(VISION_DIR, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(jpeg)
    return rel


def log_row(now, rel, result):
    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CSV_FIELDS)
        w.writerow([now.strftime("%Y-%m-%d %H:%M:%S"), rel, result["canopy_pct"],
                    result["yellow_pct"], result["greenness"], result["health"],
                    "; ".join(result["health_reasons"])])


def cleanup(now):
    """Delete photos older than KEEP_DAYS, keeping the first photo of each day."""
    cutoff = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for day in os.listdir(VISION_DIR):
        folder = os.path.join(VISION_DIR, day)
        if not os.path.isdir(folder) or day >= cutoff:
            continue
        photos = sorted(p for p in os.listdir(folder) if p.endswith(".jpg"))
        for p in photos[1:]:
            os.remove(os.path.join(folder, p))
        if not photos:
            shutil.rmtree(folder, ignore_errors=True)


# ================= Camera + MQTT =================
def fetch():
    with urllib.request.urlopen(CAM_URL, timeout=15) as r:
        data = r.read()
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("camera did not return a JPEG")
    return data


last_status = None


def set_status(client, status):
    global last_status
    if status != last_status:           # only log/publish changes, not every 10 s
        print(f"[vision] camera {status}", flush=True)
        client.publish(TOPIC_STATUS, status, retain=True)
        last_status = status


def take_photo(client, keep):
    """Fetch, check and publish one photo. keep=True also saves it to disk + CSV.
    Returns True if the camera answered."""
    now = datetime.now()
    try:
        jpeg = fetch()
    except Exception as e:
        set_status(client, f"offline: {e}")
        return False
    set_status(client, "online")

    rel = save(jpeg, now) if keep else None
    result = {"ts": int(now.timestamp()), "image": rel, **analyse(jpeg)}
    client.publish(TOPIC_IMAGE, jpeg, retain=True)
    client.publish(TOPIC_RESULT, json.dumps(result), retain=True)
    if keep:
        log_row(now, rel, result)
        print(f"[vision] saved {rel}  {result['health']}  canopy {result['canopy_pct']}%  "
              f"yellow/brown {result['yellow_pct']}%", flush=True)
        cleanup(now)
    return True


def on_connect(client, userdata, flags, reason_code, properties=None):
    global last_status
    last_status = None                  # re-publish status after a broker restart
    client.subscribe(TOPIC_CMD)
    print("[mqtt] connected", flush=True)


def on_message(client, userdata, msg):
    global snap_requested
    if msg.payload.decode(errors="replace").strip().lower() == "snap":
        snap_requested = True


def make_client():
    try:    # paho-mqtt 2.x
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="hydro-vision")
    except AttributeError:
        return mqtt.Client(client_id="hydro-vision")


def main():
    global snap_requested
    os.makedirs(VISION_DIR, exist_ok=True)
    client = make_client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.will_set(TOPIC_STATUS, "offline: vision.py stopped", retain=True)
    client.connect(BROKER, 1883)
    client.loop_start()

    if "--once" in sys.argv:        # test: one photo, then exit
        take_photo(client, keep=True)
        time.sleep(1)               # let the publishes go out
        client.disconnect()         # clean exit, so the "stopped" will isn't sent
        client.loop_stop()
        return

    next_photo = next_save = 0.0
    while True:
        now = time.monotonic()
        if snap_requested or now >= next_photo:
            keep = snap_requested or now >= next_save
            snap_requested = False
            if take_photo(client, keep) and keep:
                next_save = now + SAVE_INTERVAL
            next_photo = now + INTERVAL
        time.sleep(0.2)


if __name__ == "__main__":
    main()
