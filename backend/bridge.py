#!/usr/bin/env python3
"""
ESP32 -> MQTT bridge (offline, local only)
- Reads JSON lines from /dev/esp32, publishes to hydro/sensors
  (with log_id and row added, matching the session CSV line)
- Non-JSON lines (calibration messages) -> hydro/log
- Messages sent to hydro/cmd are forwarded to the ESP32 (e.g. "status", "ph7")
- Auto-reconnects if the USB cable is unplugged
- Starts a new CSV log in data/logs/ every time the ESP32 connects
  (plugging it in, or the bridge starting at boot), e.g. log_0007_2026-09-23_04-50-12.csv
"""

import csv
import json
import os
import re
import time
import serial
import paho.mqtt.client as mqtt

PORT       = "/dev/esp32"
BAUD       = 115200
BROKER     = "localhost"
TOPIC_DATA = "hydro/sensors"
TOPIC_LOG  = "hydro/log"
TOPIC_CMD  = "hydro/cmd"

ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root (backend/..)
LOG_DIR    = os.path.join(ROOT, "data", "logs")
LOG_FIELDS = ["temp", "hum", "ec", "ec_low", "ph", "level", "level_pct", "level_low",
              "dist_cm", "ec_mv", "po_mv", "pump_a", "pump_b", "pump_auto", "pump_sample"]

ser = None


class SessionLog:
    """One CSV file per ESP32 connection. log_id counts up across files."""

    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        ids = [int(m.group(1)) for f in os.listdir(LOG_DIR)
               if (m := re.match(r"log_(\d+)_", f))]
        self.log_id = max(ids, default=0) + 1
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        self.path = os.path.join(LOG_DIR, f"log_{self.log_id:04d}_{stamp}.csv")
        self.file = open(self.path, "w", newline="")
        self.writer = csv.writer(self.file)
        self.writer.writerow(["log_id", "row", "time"] + LOG_FIELDS)
        self.file.flush()
        self.rows = 0
        print(f"[log] new log #{self.log_id}: {self.path}", flush=True)

    def write(self, data):
        self.rows += 1
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data["ts"]))
        values = [int(v) if isinstance(v, bool) else v
                  for v in (data.get(f) for f in LOG_FIELDS)]
        self.writer.writerow([self.log_id, self.rows, t] + values)
        self.file.flush()   # keep the file current if power is cut

    def close(self):
        self.file.close()


def make_client():
    try:    # paho-mqtt 2.x
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="hydro-bridge")
    except AttributeError:   # paho-mqtt 1.x
        return mqtt.Client(client_id="hydro-bridge")


def on_connect(client, userdata, *args):
    client.subscribe(TOPIC_CMD)
    print("[mqtt] connected", flush=True)


def on_message(client, userdata, msg):
    cmd = msg.payload.decode(errors="ignore").strip()
    if cmd and ser is not None and ser.is_open:
        ser.write((cmd + "\n").encode())
        print(f"[cmd] -> ESP32: {cmd}", flush=True)


def open_serial():
    while True:
        try:
            s = serial.Serial(PORT, BAUD, timeout=5, exclusive=True)
            print(f"[serial] opened {PORT}", flush=True)
            return s
        except serial.SerialException as e:
            print(f"[serial] waiting for {PORT}: {e}", flush=True)
            time.sleep(3)


def main():
    global ser
    client = make_client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect_async(BROKER, 1883, 60)
    client.loop_start()

    while True:
        ser = open_serial()
        log = SessionLog()
        try:
            while True:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        print(f"[skip] bad JSON: {line}", flush=True)
                        continue
                    data["ts"] = int(time.time())
                    log.write(data)
                    # same log_id/row as the CSV line, so MQTT and the log file match
                    data = {"log_id": log.log_id, "row": log.rows, **data}
                    client.publish(TOPIC_DATA, json.dumps(data))
                else:
                    print(f"[esp32] {line}", flush=True)
                    client.publish(TOPIC_LOG, line)

        except (serial.SerialException, OSError) as e:
            print(f"[serial] lost connection: {e}", flush=True)
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            log.close()
            time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[bridge] stopped")
