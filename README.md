# Indoor Vertical Garden Monitoring & Automation System

Hydroponic lettuce (*Lactuca sativa*) monitoring system. An **ESP32** reads the sensors and sends data over a **USB cable** to a **Raspberry Pi 5**, which publishes it to a local **MQTT broker (Mosquitto)**. Everything runs **offline**; no Wi-Fi or internet is needed at runtime.

```
ESP32 --USB serial (115200)--> bridge.py --> Mosquitto (localhost)
                                               |-- hydro/sensors  (sensor data, JSON)
                                               |-- hydro/log      (ESP32 messages)
                                               |-- hydro/cmd      (commands to ESP32)
                                 |
                                 +--> data/logs/log_NNNN_<date>_<time>.csv  (new file per connection)
```

**Full system guide (PDF):** [`docs/Hydro_System_Guide.pdf`](docs/Hydro_System_Guide.pdf): how it works, what has been built, and how to run it.

---

## Repository structure

```
hydro/
├── README.md
├── frontend/                  # Dashboard page (runs in the browser)
│   ├── index.html             #   Overview / Graphs / Calibration tabs
│   ├── vendor/                #   mqtt.js + uPlot (offline, no CDN)
│   └── live -> ../data/vision/live   # latest camera photo (HTTP fallback)
├── backend/                   # Everything that runs on the Pi 5
│   ├── bridge.py              #   ESP32 serial -> MQTT bridge + CSV session logs
│   ├── vision.py              #   plant camera -> leaf colour check + stage model -> MQTT + photos
│   ├── server.py              #   serves frontend/ + history API on port 8000
│   ├── models/stage.onnx      #   trained growth-stage model (+ report)
│   ├── train/train_stage.py   #   trains the growth-stage model (cross-validation + report)
│   ├── systemd/               #   hydro-bridge / hydro-vision / hydro-dashboard .service
│   ├── mosquitto/local.conf   #   local-only Mosquitto config
│   └── udev/99-esp32.rules    #   fixed /dev/esp32 port name
├── data/                      # Runtime data, not in git: logs/ (session CSVs), vision/ (photos)
├── maixcam/hydro_cam/         # MaixCAM app (runs ON the camera): preview + photo server
├── dataset/lettuce_growth_stages/  # Lettuce photos by growth stage (seedling / vegetative / matured)
├── dataset/lettuce_224/       # Same photos as 224x224 JPEG + labels.csv (stage + size)
├── docs/                      # Dashboard design plan, system guide PDF
├── Circuit Diagram/           # Wiring diagram (EasyEDA project)
└── firmware/                  # ESP32 sketches (Arduino IDE)
    ├── Full_code/             #   MAIN firmware: DHT22 + EC + pH + HC-SR04 + pumps -> JSON
    │   ├── Full_code.ino
    │   ├── DFRobot_EC.cpp     #   PATCHED EC library (ESP32 fixes)
    │   └── DFRobot_EC.h
    ├── Relay_Test/            #   2-channel relay test (Pump A / Pump B)
    ├── DHT22/                 #   single-sensor test sketches
    ├── EC_Sensor/
    ├── PH_Sensor/
    └── esp32_hydroponic_sensors/   # earlier combined sensor sketch
```

---

## Hardware and wiring

| Sensor | Module pin | ESP32 pin | Notes |
|---|---|---|---|
| DHT22 (air temp/humidity) | DATA / VCC / GND | GPIO15 / 3.3V / GND | 10k pull-up if the module has none |
| EC sensor (EC V2.1) | A0 / VCC / GND | GPIO34 / **3.3V** / GND | T1 unconnected |
| pH sensor (PH-4502C) | Po / V+ / G | GPIO35 via divider / **5V** / GND | Do, To unconnected |
| HC-SR04 (water level) | TRIG / ECHO / VCC / GND | GPIO32 / GPIO33 via divider / **5V** / GND | Mounted above the tank, facing down |
| 2-channel relay (Pump A / Pump B) | IN1 / IN2 / VCC / GND | GPIO25 / GPIO26 / **5V** / GND | Active LOW; GND shared with ESP32 |
| 1-channel relay (sampling pump) | IN / VCC / GND | GPIO27 / **5V** / GND | Active LOW; GND shared with ESP32 |

**pH voltage divider (required).** The PH-4502C runs on 5V and its output can exceed 3.3V:

```
Po --[10k]--+-- GPIO35
            |
          [20k]
            |
GND --------+
```

**HC-SR04 echo divider (required).** The HC-SR04 runs on 5V, so its ECHO pulse is 5V. TRIG can be driven directly from GPIO32 (3.3V is enough):

```
ECHO --[1k]--+-- GPIO33
             |
           [2k]
             |
GND ---------+
```

> ⚠️ Never put more than 3.3V on an ESP32 pin.
> Keep the pH and EC probes in **separate containers** when testing; they interfere with each other.

---

## Part 1: ESP32 firmware

### Libraries (Arduino IDE → Library Manager)
- **DHT sensor library** (Adafruit)
- **Adafruit Unified Sensor**

The EC library is **not** installed from the Library Manager. Use the patched `DFRobot_EC.cpp` / `.h` inside `firmware/Full_code/`. It fixes:
- a `strupr()` bug that could corrupt memory
- calibration not surviving a reboot (missing `EEPROM.commit()` on ESP32)
- `exitec` saving only one calibration point

### Upload
1. Open `firmware/Full_code/Full_code.ino` in the Arduino IDE.
2. Board: **ESP32 Dev Module**, then upload.
3. Serial Monitor at **115200 baud**, line ending **Newline**.
4. You should see one JSON line every 2 seconds:

```json
{"temp":28.1,"hum":70.2,"ec":1.45,"ec_low":false,"ph":6.20,"level":9.8,"level_pct":72,"level_low":false,"ec_mv":237,"po_mv":2650,"dist_cm":10.2,"pump_a":true,"pump_b":true,"pump_auto":true,"pump_sample":true,"temp_ok":true}
```

| Field | Meaning |
|---|---|
| `temp`, `hum` | Air temperature (°C) and humidity (%) |
| `ec` | Electrical conductivity (mS/cm) |
| `ec_low` | `true` = signal below the ESP32 ADC floor (EC < ~0.6 mS/cm) |
| `ph` | pH value |
| `level` | Water height above the tank bottom (cm), `null` if no echo |
| `level_pct` | Water level in % (0 = empty, 100 = full, after tank calibration) |
| `level_low` | `true` = level below 20 % (`LOW_LEVEL_PCT`) |
| `ec_mv`, `po_mv` | Raw sensor voltages (for debugging/calibration) |
| `dist_cm` | Raw HC-SR04 distance, sensor → water surface (cm) |
| `pump_a`, `pump_b` | Pump A / Pump B relay state |
| `pump_auto` | `true` = pumps in auto (EC/pH) mode, `false` = manual |
| `pump_sample` | Sampling pump relay state |
| `temp_ok` | `true` = air temperature inside 25–36 °C (`TEMP_MIN`/`TEMP_MAX`), `null` = no DHT22 reading. Only reported; nothing heats or cools |

Lines starting with `#` or `>>>` are messages, not data.

> Close the Arduino IDE Serial Monitor before running the bridge on the Pi. Only one program can use the port at a time.

### Relay test (Pump A / Pump B) ✅ tested

`firmware/Relay_Test/Relay_Test.ino` is a standalone sketch that checks the 2-channel relay module before it goes into the main firmware.

**Setup:** relay **IN1 → Pump A**, **IN2 → Pump B** (GPIO25 / GPIO26). Only Pump A and Pump B are connected to the relay.

**Method:**
1. Upload `Relay_Test.ino`, open the Serial Monitor (115200, Newline).
2. **Auto mode** runs at boot: Pump A ON 2 s → OFF 2 s → Pump B ON 2 s → OFF 2 s, repeating.
3. Typing any command switches to manual:

| Command | Action |
|---|---|
| `1on` / `1off` | Pump A (relay 1) ON / OFF |
| `2on` / `2off` | Pump B (relay 2) ON / OFF |
| `alloff` | Both OFF |
| `auto` | Back to the automatic sequence |

**Result:** both relays switched correctly and Pump A and Pump B ran on command. **Test successful.**

> The relays are set OFF *before* the pins become outputs, so the pumps don't kick on at boot. If your module turns ON with HIGH, set `ACTIVE_LOW` to `false`.

### Pump auto control (EC + pH target)

In `Full_code.ino`, Pump A and Pump B **run until EC and pH both reach the target, then stop**. If either value leaves the target again, both pumps start again.

Targets are set at the top of `Full_code.ino`. Pumps run when EC **or** pH is **lower or higher** than the target, and stop when both are inside. Auto mode is on at boot.
```cpp
#define EC_MIN  1.2      // mS/cm
#define EC_MAX  1.8      // mS/cm
#define PH_MIN  5.5
#define PH_MAX  6.5
```

| EC | pH | Pump A + Pump B |
|---|---|---|
| Lower than 1.2 **or** higher than 1.8 | any | **ON** |
| any | Lower than 5.5 **or** higher than 6.5 | **ON** |
| 1.2 – 1.8 mS/cm | 5.5 – 6.5 | **OFF** (target reached) |
| `ec_low` = `true` (EC below ~0.6) | any | **ON** (counted as under target) |
| any | pH reading invalid | **OFF** (safety) |
| any | any, **tank low** | **OFF** (see below) |

**Manual control** (Serial Monitor or `mosquitto_pub -t hydro/cmd -m "<command>"`):

| Command | Action |
|---|---|
| `pumpaon` / `pumpaoff` | Pump A ON / OFF (switches to manual mode) |
| `pumpbon` / `pumpboff` | Pump B ON / OFF (switches to manual mode) |
| `pumpauto` | Back to auto (EC + pH target) mode |

The pump state is in every JSON line (`pump_a`, `pump_b`, `pump_auto`), and `status` shows the mode and targets.

> The sensors take time to settle after nutrient is added, so EC/pH can overshoot the target before the pumps stop. If that happens, switch to short timed doses (e.g. 2 s ON, wait 30–60 s, re-check).

### Sampling pump (always on)

A separate **1-channel relay on GPIO27** drives the sampling pump. It **runs all the time** from boot (switched on with the first reading, ~2 s after start-up) and is not affected by EC/pH.

| Command | Action |
|---|---|
| `sampleoff` | Stop the sampling pump (e.g. for maintenance) |
| `sampleon` | Start it again |

State is in the JSON (`pump_sample`) and in `status`. If your 1-channel module turns ON with HIGH, set `SAMPLE_ACTIVE_LOW` to `false`.

### Tank low pump stop (dry-run protection)

In `Full_code.ino`, Pump A, Pump B **and the sampling pump** are **forced OFF when the tank is low**, so they never run dry.

| Condition | Pumps |
|---|---|
| `level_low` = `true` (water below `LOW_LEVEL_PCT`, default **20 %**) | **Both OFF**, in auto *and* manual mode |
| Tank low + `pumpaon` / `pumpbon` / `sampleon` | Refused: `# ... blocked: tank LOW. Refill first` |
| Tank refilled | **Auto:** back to EC/pH control. **Manual:** stay OFF until switched on again. **Sampling pump:** back ON (unless `sampleoff`) |

Serial messages when it changes:
```
# Tank LOW - pumps stopped
# Tank OK - pumps allowed
```

> ⚠️ The protection is only active **after the tank is calibrated** (`tankempty` → `tankfull`). Before that, the level uses default distances and could falsely block the pumps.
> If the HC-SR04 gets no echo (`level` = `null`), the pumps are **not** stopped; they keep following EC/pH.

---

## Part 2: Raspberry Pi 5 setup (one time)

### 1. Install packages
```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients python3-serial python3-paho-mqtt git
```

### 2. Fixed port name `/dev/esp32`
The ESP32 uses a CP2102 USB chip (`10c4:ea60`, check with `lsusb`).
```bash
sudo cp backend/udev/99-esp32.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
sudo usermod -aG dialout $USER
sudo reboot
```
`backend/udev/99-esp32.rules` contains:
```
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="esp32"
```

### 3. Mosquitto (local only)
```bash
sudo cp backend/mosquitto/local.conf /etc/mosquitto/conf.d/local.conf
sudo systemctl restart mosquitto
sudo systemctl enable mosquitto
```
`backend/mosquitto/local.conf` contains:
```
listener 1883 localhost
listener 9001
protocol websockets
allow_anonymous true
```

### 4. Bridge as a service (starts at boot)
```bash
sudo cp backend/systemd/hydro-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hydro-bridge
```

The bridge also logs every reading to CSV. Each time the ESP32 connects (plugged in, Pi
reboot, or bridge restart) it starts a new file in `data/logs/`, named
`log_NNNN_<date>_<time>.csv`. The log ID `NNNN` counts up and is also the `log_id` column;
`row` numbers the readings inside the file. The `data/` folder is ignored by git.

Columns: `log_id, row, time, temp, hum, ec, ec_low, ph, level, level_pct, level_low, dist_cm,
ec_mv, po_mv, pump_a, pump_b, pump_auto, pump_sample`. Booleans are stored as `1`/`0`, and a
missing value (`null`, or a field older firmware doesn't send) is an empty cell. Logs made before
the pump columns were added simply don't have them.

---

## Part 3: Running the system

### Normal operation
1. Plug the ESP32 into the Pi with the USB cable.
2. Power on the Pi. Mosquitto and the bridge start automatically.
3. Check that data is flowing:
```bash
mosquitto_sub -t hydro/sensors -v
```

### Manual run (for testing)
```bash
sudo systemctl stop hydro-bridge      # free the serial port first
python3 ~/hydro/backend/bridge.py
```

### Recommended testing order
```bash
ls -l /dev/esp32                      # 1. port exists
cat /dev/esp32                        # 2. raw JSON arrives (Ctrl+C to stop)
systemctl status hydro-bridge         # 3. bridge running
mosquitto_sub -t hydro/sensors -v     # 4. data published to MQTT
```

---

## Part 4: Calibration

Send commands from the **Arduino Serial Monitor**, or from the **Pi** through MQTT.

On the Pi, watch replies in one terminal:
```bash
mosquitto_sub -t hydro/log -v
```
Send commands from another:
```bash
mosquitto_pub -t hydro/cmd -m "status"
```

### EC calibration (buffers: 1413 µS/cm and 12.88 mS/cm)
| Step | Action | Command |
|---|---|---|
| 1 | Start calibration | `enterec` |
| 2 | Probe in **1413 µS/cm** buffer, wait 20 s | `calec` |
| 3 | Rinse, probe in **12.88 mS/cm** buffer, wait 20 s | `calec` |
| 4 | Save both points | `exitec` |

Expected: ~230 mV in the 1413 buffer, ~2100 mV in the 12.88 buffer. K-values must be between 0.5 and 1.5.

### pH calibration (buffers: pH 7 and pH 4)
**Zero the module first (one time):** unplug the probe, short the BNC centre pin to its outer shell, and turn the **left potentiometer** (next to the BNC) until `po_mv` ≈ **2500**. It is a multi-turn trimmer (~20–25 turns).

| Step | Action | Command |
|---|---|---|
| 1 | Probe in **pH 7** buffer, wait 1–2 min | `ph7` |
| 2 | Rinse, probe in **pH 4** buffer, wait 1–2 min | `ph4` |
| Reset | Back to default values | `phreset` |

Expected slope ≈ **180 mV/pH**. The right potentiometer only sets the red LED (Do alarm) threshold and does not affect readings.

### Tank level calibration (HC-SR04)
Mount the sensor above the tank facing straight down, at least **2 cm** above the highest water level (the HC-SR04's minimum range).

| Step | Action | Command |
|---|---|---|
| 1 | Tank **empty** | `tankempty` |
| 2 | Fill the tank to the **MAX** level | `tankfull` |
| Reset | Back to default values (empty 20 cm, full 5 cm) | `tankreset` |

The difference between empty and full must be at least **3 cm**. Each reading is the median of 5 pings, adjusted for the speed of sound at the DHT22 air temperature.

### Other commands
| Command | Action |
|---|---|
| `status` | Show stored EC K-values, pH and tank calibration, pump state |
| `debug` | Toggle human-readable readings |

All calibration values are stored in the ESP32's EEPROM and survive reboots.

> After use, rinse the pH probe and put the cap back on with its storage solution. The glass bulb must never dry out.

---

## Part 5: Plant camera (Sipeed MaixCAM)

The MaixCAM is its own small Linux computer. Plugged into the Pi by USB-C it shows up as a
**USB network adapter**, and NetworkManager gets an address from it automatically:

| | Address |
|---|---|
| MaixCAM (over USB) | `10.122.173.1` |
| Pi (over USB) | `10.122.173.100` (DHCP from the MaixCAM) |

```
MaixCAM  hydro_cam app ──http://10.122.173.1:8080/snap.jpg──► vision.py (Pi)
                                                                 ├─ data/vision/YYYY-MM-DD/HH-MM-SS.jpg
                                                                 ├─ data/vision/vision_log.csv
                                                                 └─ MQTT hydro/vision, hydro/vision/image, hydro/vision/status
```

### 1. Install the camera app (one time)
The app shows a live preview on the MaixCAM screen (use it to aim at the lettuce) and serves a
fresh 640×480 JPEG to the Pi. It only answers the USB network (`10.122.x.x`), not WiFi.
```bash
scp -r ~/hydro/maixcam/hydro_cam root@10.122.173.1:/maixapp/apps/     # password: root
ssh root@10.122.173.1 'echo hydro_cam > /maixapp/auto_start.txt && reboot'
curl http://10.122.173.1:8080/status                                    # after ~30 s
```
`auto_start.txt` makes the MaixCAM open the app at boot. To go back to the normal menu, delete
that file (or use Settings → Auto start on the MaixCAM).

> ⚠️ Don't run `python3 main.py` over SSH while the MaixCAM menu is running. Both try to use the
> camera and the driver hangs until a reboot. Start it from the menu, from MaixVision, or by auto-start.
>
> ⚠️ Change the MaixCAM's default password (`ssh root@10.122.173.1`, then `passwd`). It is also on WiFi.

### 2. Run the Pi side
`vision.py` runs from the project's Python environment `.venv`, which has ONNX Runtime for the
stage model (set up once, see section 6 below). With plain `python3` it still works, without stage.
```bash
~/hydro/.venv/bin/python ~/hydro/backend/vision.py --once   # test: one photo, prints the result
sudo cp ~/hydro/backend/systemd/hydro-vision.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hydro-vision
```
It takes a **live photo every 10 s** (`HYDRO_VISION_INTERVAL`), checks it and publishes it for
the dashboard. Only every **15 min** (`HYDRO_VISION_SAVE_INTERVAL`) is a photo also saved to disk
and the CSV; saving every 10 s would be ~150 MB a day. To save one now:
`mosquitto_pub -t hydro/vision/cmd -m snap` (or **Save photo now** on the dashboard).

### 3. What it reports
```json
{"ts": 1790161885, "image": "2026-09-23/07-11-25.jpg", "canopy_pct": 34.2,
 "yellow_pct": 3.1, "greenness": 0.41, "health": "healthy", "health_reasons": [],
 "stage": "vegetative", "stage_conf": 0.87, "size": "medium"}
```

| Field | Meaning |
|---|---|
| `canopy_pct` | Share of the photo that is plant (a rough size measure), `null` if no plant |
| `yellow_pct` | Yellow/brown share of the plant area |
| `greenness` | Excess-green index of the plant pixels, -1…1 (higher = greener) |
| `health` | `healthy`, `check` (yellow > 8 %), `unhealthy` (yellow > 20 %), `no_plant` (< 2 % green in view) |
| `stage` | `seedling`, `vegetative`, `matured` from the AI model, or `uncertain` (< 60 % sure). `null` with no plant in view |
| `stage_conf` | The model's confidence, 0…1 |
| `size` | `small`, `medium`, `large`: follows the stage (seedling = small, vegetative = medium, matured = large) |

Health is a **leaf colour rule**. Stage and size come from the **AI model** (section 6 below).
The model only runs when the colour check finds a plant: it knows only the three stages, so it
would call anything (even a keyboard) one of them. Keep the camera
at a fixed spot and take photos under the grow light so results compare day to day. The colour
bands, thresholds and `ROI` (crop to the tray) are at the top of `backend/vision.py`.

`hydro/vision/image` carries the JPEG itself (retained), so the dashboard can show the latest
photo straight from MQTT. `hydro/vision/status` is `online` or `offline: <reason>`.

### 4. Dashboard
The dashboard has three tabs:
- **Overview:** sensor tiles, pump states, raw values, and the live camera photo with health,
  growth stage and size.
- **Graphs:** pH, EC, air temperature and humidity for the last 1 h, 24 h or 7 days, with the
  target band shaded and gaps marked "no data". Hovering on one chart shows the same moment on all
  four. Under the charts: when each pump was ON, and the plant stage over time. **Table** shows the
  numbers, **Download CSV** saves the session log rows for the range.
- **Calibration:** step-by-step EC, pH and tank-level calibration. Each capture button stays
  disabled until the reading is steady, and the ESP32's replies show in the page. Also: the stored
  calibration (`status`) and a hold-to-reset for pH.

Live values come from Mosquitto's websocket listener (port 9001). History comes from
`backend/server.py`, which serves the page (`frontend/`) and reads the session CSVs in `data/logs/`
(standard library only). Everything works offline (`mqtt.js` and uPlot are in `frontend/vendor/`).
```bash
sudo cp ~/hydro/backend/systemd/hydro-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hydro-dashboard
```
Open **http://localhost:8000** on the Pi, or `http://<pi-ip>:8000` from a phone on the same
network. If the browser can't reach MQTT on port 9001 (the header shows "Live link
down"), the camera photo still updates through `frontend/live/` (a link to `data/vision/live/`,
which `vision.py` rewrites every 10 s). Sensor tiles and calibration need the MQTT link.
Design and next steps: `docs/dashboard-design-plan.md`.

> ⚠️ The Calibration tab sends commands on `hydro/cmd`. MQTT has no password, so anyone on your
> network can do the same. Add a Mosquitto password before using the dashboard on a shared network.

### 5. Plant image dataset
`dataset/lettuce_growth_stages/` holds **41 lettuce photos sorted by growth stage**, for training a
growth-stage model later:

| Stage | Photos |
|---|---|
| `seedling/` | 18 |
| `vegetative/` | 6 |
| `matured/` | 17 |

The folder name is the label. `labels.csv` lists each photo with its stage, format, size and original
file name. `dataset/lettuce_224/` has the same 41 photos converted to 224×224 JPEG, with a
`labels.csv` that adds the size (seedling = small, vegetative = medium, matured = large).
See [`dataset/lettuce_growth_stages/README.md`](dataset/lettuce_growth_stages/README.md).

### 6. Growth-stage AI model
`backend/train/train_stage.py` trains a small image model (MobileNetV3-Small) on `dataset/lettuce_224/`,
on the Pi 5 itself, in about 20 minutes. One-time setup of the Python environment:
```bash
cd ~/hydro
python3 -m venv .venv
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r backend/train/requirements.txt
```
Train, then restart the camera service so it loads the new model:
```bash
.venv/bin/python backend/train/train_stage.py
sudo systemctl restart hydro-vision
```
It tests with 5-fold cross-validation (every photo is tested once by a model that never saw it),
writes `backend/models/stage_report.md` (accuracy, MAE/MSE/RMSE/MAPE, per-stage results, confusion matrix)
and `backend/models/stage_training.png`, then exports `backend/models/stage.onnx`.

First result (41 photos): **90 % test accuracy, MAE 0.10 stage**, 19 ms per photo on the Pi 5.
Seedling and matured are recognised well; **vegetative only 3 of 6**. Add more vegetative photos,
and photos from your own camera (`data/vision/`), then retrain. Test on photo files without the
camera: `.venv/bin/python backend/vision.py --stage photo.jpg`.

---

## Important commands (cheat sheet)

### Bridge service
```bash
sudo systemctl status hydro-bridge     # is it running?
sudo systemctl restart hydro-bridge    # restart
sudo systemctl stop hydro-bridge       # stop (frees /dev/esp32)
sudo systemctl start hydro-bridge      # start
journalctl -u hydro-bridge -f          # live log (Ctrl+C to exit)
```

### Mosquitto / MQTT
```bash
sudo systemctl status mosquitto              # broker running?
mosquitto_sub -t hydro/sensors -v            # live sensor data
mosquitto_sub -t hydro/log -v                # ESP32 messages
mosquitto_sub -t 'hydro/#' -v                # everything
mosquitto_pub -t hydro/cmd -m "status"       # send command to ESP32
```

### Session logs (CSV)
```bash
ls -lt ~/hydro/data/logs/ | head             # newest logs first
tail -f "$(ls -t ~/hydro/data/logs/*.csv | head -1)"   # follow the current log
journalctl -u hydro-bridge | grep '\[log\]'  # when each log was started
```
Open a log in LibreOffice Calc / Excel, or preview it with `column -s, -t < data/logs/<file>.csv | less -S`.

### Serial port
```bash
lsusb                                  # find the ESP32 (10c4:ea60)
ls -l /dev/esp32                       # check the symlink
cat /dev/esp32                         # raw output (stop the bridge first)
stty -F /dev/esp32 115200              # set baud if output is garbled
```

### Git
```bash
git add .
git commit -m "Describe what changed"
git push
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `/dev/esp32` missing | Check `lsusb`, re-plug the cable, re-run the udev commands |
| `Permission denied` on the port | `sudo usermod -aG dialout $USER`, then reboot |
| Port busy | Stop the bridge or close the Arduino Serial Monitor |
| No data on `hydro/sensors` | `journalctl -u hydro-bridge -f`, check Mosquitto status |
| `ec_low: true` | Solution below ~0.6 mS/cm, under the ESP32 ADC limit (normal for plain/mineral water) |
| pH stuck at one value | BNC open or pot at its end stop; short the BNC and re-zero |
| `Buffer Solution Error` (EC) | Check `ec_mv` against the expected buffer voltages |
| `Failed, K out of range` (EC) | Re-check wiring/probe; note the K value shown |
| DHT `temp`/`hum` = `null` | Check the DHT22 wiring and pull-up resistor |
| `hydro/vision/status` = `offline: …` | `ping 10.122.173.1`; check the USB-C cable and that the MaixCAM shows the Hydro Cam preview |
| MaixCAM stuck / SSH commands hang | Camera driver hung (two programs used the camera). Reboot the MaixCAM |
| `health: no_plant` | Camera not aimed at the plants, lens out of focus, or grow light off |

---

## Target ranges (lettuce)

| Parameter | Range |
|---|---|
| EC | 1.2 – 1.8 mS/cm (seedlings 0.5 – 1.0) |
| pH | 5.5 – 6.5 |

---

## Roadmap

- [x] ESP32 firmware: DHT22, EC, pH with calibration
- [x] USB serial → MQTT bridge on Pi 5
- [x] HC-SR04 water level sensor (firmware: TRIG GPIO32, ECHO GPIO33)
- [ ] DS18B20 water temperature (EC temperature compensation)
- [x] CSV session logs (new file per ESP32 connection)
- [x] History API (`backend/server.py`: `/api/history`, pump runs, vision, CSV export)
- [x] First dashboard page: live camera photo + sensors + pumps (`frontend/`)
- [x] Dashboard Graphs tab (history charts, pump lanes, stage strip) and Calibration tab (EC, pH, tank)
- [x] Plant camera (MaixCAM over USB): photos + leaf colour health check, publishing to `hydro/vision`
- [x] Lettuce growth-stage image dataset: 41 photos in 3 stages (`dataset/lettuce_growth_stages/`)
- [x] Camera AI model for growth stage + size (`backend/models/stage.onnx`, 90 % test accuracy)
- [ ] More vegetative + own-camera photos, retrain (vegetative recall is 50 %)
- [ ] MQTT password + ACL for `hydro/cmd`
- [x] Relay test: Pump A and Pump B (`firmware/Relay_Test/`)
- [x] Pump A / Pump B auto control: run until EC 1.2–1.8 mS/cm and pH 5.5–6.5, then stop (in `firmware/Full_code`)
- [x] Tank low pump stop (dry-run protection, in `firmware/Full_code`)
- [ ] Grow light control via relay
- [ ] RTC battery for correct offline timestamps
