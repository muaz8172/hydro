#!/usr/bin/env python3
"""
ESP32 -> MQTT bridge (offline, local only)
- Reads JSON lines from /dev/esp32, publishes to hydro/sensors
- Non-JSON lines (calibration messages) -> hydro/log
- Messages sent to hydro/cmd are forwarded to the ESP32 (e.g. "status", "ph7")
- Auto-reconnects if the USB cable is unplugged
"""

import json
import time
import serial
import paho.mqtt.client as mqtt

PORT       = "/dev/esp32"
BAUD       = 115200
BROKER     = "localhost"
TOPIC_DATA = "hydro/sensors"
TOPIC_LOG  = "hydro/log"
TOPIC_CMD  = "hydro/cmd"

ser = None


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
            s = serial.Serial(PORT, BAUD, timeout=5)
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
            time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[bridge] stopped")
