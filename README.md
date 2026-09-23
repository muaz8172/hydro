# hydro

A local, offline ESP32-to-MQTT bridge for a hydroponics monitoring setup.

`bridge.py` reads sensor data from an ESP32 over USB serial and republishes it
to a local MQTT broker, with auto-reconnect if the ESP32 is unplugged or the
broker restarts.

## How it works

- Reads JSON lines from the ESP32 (`/dev/esp32`) and publishes them to
  `hydro/sensors`, tagged with a Unix timestamp.
- Non-JSON lines (e.g. calibration/debug output) are published to `hydro/log`.
- Messages published to `hydro/cmd` are forwarded to the ESP32 over serial
  (e.g. `status`, `ph7`).
- If the USB connection drops, the bridge waits and retries until the ESP32
  reappears.

## Requirements

- Python 3
- A local MQTT broker (e.g. [Mosquitto](https://mosquitto.org/)) running on
  `localhost:1883`
- An ESP32 exposed at `/dev/esp32` (e.g. via a udev rule symlinking its serial
  device)

Install dependencies:

```bash
pip install pyserial paho-mqtt
```

## Usage

```bash
python3 bridge.py
```

## Configuration

Settings are constants at the top of `bridge.py`:

| Name         | Default         | Description                  |
|--------------|-----------------|-------------------------------|
| `PORT`       | `/dev/esp32`    | Serial device path            |
| `BAUD`       | `115200`        | Serial baud rate              |
| `BROKER`     | `localhost`     | MQTT broker host              |
| `TOPIC_DATA` | `hydro/sensors` | Topic for parsed sensor JSON  |
| `TOPIC_LOG`  | `hydro/log`     | Topic for raw/non-JSON lines  |
| `TOPIC_CMD`  | `hydro/cmd`     | Topic for commands to ESP32   |
