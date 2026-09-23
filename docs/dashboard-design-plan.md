# Hydro Dashboard: Design Plan

Mockups: https://claude.ai/artifact/WkQEocQ3YATsaeQA4zAjFX (desktop, phone, EC calibration wizard)

A React dashboard for the lettuce hydroponic system. It shows live readings from `hydro/sensors`, the ON/OFF status of the three pumps (nutrient A, nutrient B, sampling), the lettuce's size, growth stage and health from a camera model running on the Pi 5, history from the session CSV logs in `data/logs/`, the ESP32 message log, and guided calibration over `hydro/cmd`.

Skills used: **emil-design-eng** (motion and feel), **dataviz** (charts, color, status), **design-taste-frontend / minimalist-ui** (visual direction), **shadcn** (components), **vercel-react-best-practices** (live-data performance). Run **impeccable** / **web-design-guidelines** as audits once built.

---

## 1. What the dashboard must do

| Job | Frequency | Priority |
|---|---|---|
| "Is my system healthy right now?" | Every glance | Primary. Must be answered in under 1 s |
| "Which pumps are running?" | Every glance | Primary. Pump A, pump B and the sampling pump each show ON or OFF |
| "How often did the pumps dose today?" | Daily | Secondary |
| "Is my lettuce healthy, and how big is it?" | A few ×/day | Primary. Size, stage and health on the main page |
| "How did pH/EC drift today?" | Daily | Secondary |
| "What did the ESP32 say?" | When debugging | Tertiary |
| Calibrate EC / pH | Every few weeks | Rare, but must be foolproof |
| Export CSV | Occasionally | Utility |

Constraints from the project:
- **Offline.** No CDNs or Google Fonts at runtime. Everything is bundled, and fonts are self-hosted via `@fontsource`.
- **Runs on the Pi 5.** The main screen is the Pi's own **1920×1080 HDMI display**, in a full-screen browser. Every page fits that screen with **no page scrolling**. A phone on the LAN is a secondary viewer.
- **Data every 2 s.** Anything that reacts to a new reading is seen ~1800 times an hour, so motion on it must be close to zero.

---

## 2. Visual direction

**"Lab instrument, not SaaS."** The dashboard should be calm, precise and legible from a distance. It should look like a well-made measuring device, not a marketing page.

- **Palette.** A warm neutral monochrome surface, with one muted leaf-green accent used only for brand and focus. Color is otherwise reserved for **status** (dataviz rule: status colors are never reused for series).
- **Theme.** Light mode only. There is no dark theme and no theme switch. The surface is a warm off-white (`#f6f5f1`) with white cards, so it reads well in a bright grow room.
- **Type.** Geist (UI) plus Geist Mono or `font-variant-numeric: tabular-nums` for every number, so digits don't jitter when values update every 2 s.
- **Hierarchy.** Compact cards. The Overview page shows everything that needs a glance, and charts live on their own tab. No gradients, no glassmorphism, no emoji. Shadows are replaced by 1 px hairline borders (minimalist-ui).
- **Density.** Generous on the hero tiles, compact in the log and tables.

### Status system (dataviz status palette + icon + label, never color alone)

| State | Rule | Visual |
|---|---|---|
| In range | Inside the target band | Good color, `check` icon, "In range" |
| Drifting | Inside the band but within 10 % of an edge | Warning color, `arrow` icon, "Drifting high/low" |
| Out of range | Outside the band | Critical color, `alert` icon, "High"/"Low" |
| Below sensor floor | `ec_low: true` | Neutral, value shown as `< 0.6`, tooltip explains the ADC floor |
| Stale | Last reading older than 10 s | Whole tile desaturates, "No data for 42 s" |
| No echo | `level: null` (HC-SR04 installed but no echo) | Dashed tile, "Water level: no echo, check sensor". Pumps keep following EC/pH in this state |
| Tank low | `level_low: true` | Critical color on the Water tile, "Tank low: pumps stopped". Every pump card shows the lock too (below) |
| Tank not calibrated | `status` reports tank NOT calibrated | Water tile shows "Not calibrated" instead of a %; the dry-run stop is inactive until `tankempty` → `tankfull` |
| Pump ON | Relay reported on | Filled blue pill "ON" plus "running 8 s". Blue is an *activity* color, not a health color, so it never collides with good/warning/critical |
| Pump OFF | Relay reported off | Outlined grey pill "OFF" plus "last ran 04:47 · 6 s" |
| Pump unknown | No reading for 10 s, or the field is missing | Dashed pill "—", "No status from ESP32". Never show a stale ON as if it were live |
| Pump locked | `level_low: true` (tank calibrated) | Grey pill "OFF" with a `lock` icon, "Tank low: refill" |
| Pump A/B ON long | Pump A or B ON longer than the dashboard warning time (placeholder 10 min) | Warning color, `alert` icon, "Running 12 min: EC/pH not reaching target". Not used for the sampling pump, which is meant to run all the time |
| Sampling pump OFF | `pump_sample: false` while the tank is OK | Warning color, "Sampling pump off (sampleoff?)", since it should always run |

Target bands live in one config file (`src/config/targets.ts`), seeded from the README: pH 5.5–6.5, EC 1.2–1.8 mS/cm (seedling preset 0.5–1.0). These must match `EC_MIN/EC_MAX/PH_MIN/PH_MAX` in `Full_code.ino`, since the firmware runs the pumps against the same band. Air temperature and humidity bands should be confirmed for your grow room. Place a preset switch ("Seedling / Growing") in settings.

---

## 3. Layout

The dashboard is **three tabs**, each exactly one screen (1920×1080, `100vh`, `overflow: hidden`). Nothing on a page scrolls except the ESP32 log list inside its own card.

| Tab | Contents |
|---|---|
| **Overview** (default) | Sensor readings, pump status, plant status, a small JSON data log, sensors & session |
| **Graphs** | 24 h / 7 d history charts, pump activity lanes, plant stage timeline |
| **Calibration** | EC and pH wizards (section 5) |

### Overview (1920×1080, no scroll)
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Hydro · Lettuce rack   [Overview] [Graphs] [Calibration]   ● Live 2 s · log #0007│ 64 px
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────────────────┤
│ pH       │ EC       │ Air temp │ Humidity │ Water    │ Plant                    │
│ 6.12     │ 1.38     │ 25.7 °C  │ 58.9 %   │ 72 %     │ ┌──────────┐ Healthy ✓   │ sensor row
│ ▕░█▓░▏   │ ▕░█▓░▏   │ ▕░▓█░▏   │ ▕▓█░░▏   │ ▕▓▓▓█░▏  │ │ snapshot │ Size Medium │ ~200 px
│ ✓ In rng │ ✓ In rng │ ↗ Drift  │ ✓ In rng │ ✓ OK     │ │  05:00   │ Stage Veget.│
├──────────┴───┬──────┴──────┬───┴──────────┴──────────┤ └──────────┘ 94 % · 92 % │
│ Pump A  (ON) │ Pump B (ON) │ Sampling (ON)          │ next check 05:15          │ pump row
│ running 4 s  │ running 4 s │ running 2 h 10 m       │ Mode AUTO · target EC/pH  │ ~110 px
├──────────────┴────────┬────┴────────────────────────┴──────────────────────────┤
│ Data log (JSON)       │ Sensors & session                                       │
│ 05:10:22 {"log_id":7, │ SESSION        │ CONNECTIONS        │ RAW SENSORS       │ fills the
│  "row":1204,"ts":…,   │ #0007 · 04:50  │ ESP32 ● connected  │ ec_mv 237         │ rest
│  "ph":6.12,…}         │ rows 1,204     │ MQTT  ● connected  │ po_mv 2,650       │
│ 05:10:20 {…}          │ 7 today        │ Camera ○ not set up│ dist_cm 14.2      │
└───────────────────────┴────────────────────────────────────────────────────────┘
```
- CSS grid: `grid-template-columns: repeat(5, minmax(0,1fr)) 1.6fr`, rows `auto auto 1fr`. The bottom row takes whatever height is left, so the page never grows past the screen.
- Sensor cards are compact: label, value, band meter and status only. The sparkline moves to the Graphs tab.
- The water level becomes a fifth sensor card.
- **Data log card (small, JSON only).** It shows the newest session log rows as raw JSON, one record per entry, newest first, with the time in a narrow column on the left. Example record:
  `{"log_id":7,"row":1204,"ts":1790154622,"temp":25.7,"hum":58.9,"ec":1.38,"ec_low":false,"ph":6.12,"level":9.8,"level_pct":72,"level_low":false,"dist_cm":14.2,"ec_mv":237,"po_mv":2650,"pump_a":true,"pump_b":true,"pump_auto":true,"pump_sample":true}`
  Keys are muted and values stand out; booleans use the ON blue. The records come from `hydro/sensors` over MQTT. `bridge.py` adds `log_id` and `row` to each message before publishing, so the JSON on screen matches the session CSV row exactly (done). The card keeps the last 50 in memory, shows as many as fit, and never scrolls the page. ESP32 text messages (`hydro/log`) are not shown here.

### Graphs tab (1920×1080, no scroll)
- Range tabs (1h / 24h / 7d) plus Table and Download CSV in one row.
- A 2×2 grid of charts (pH, EC, air temp, humidity) sized to fill the space.
- Pump activity lanes under the charts, on the same time axis.
- A plant stage strip: a thin timeline coloured by the detected stage (Seedling → Vegetative → Matured), so growth can be compared with EC and pH.

### Other screens
- **Phone (<640 px):** here the page may scroll. The cards stack in one column, and the tabs become a bottom bar.
- **No dual-axis chart.** Temperature and humidity get separate charts, per dataviz's non-negotiable.

### Sensor card anatomy (compact)
1. Label (muted), plus the unit after the value, not in the label
2. Value: 36 px tabular numerals, 2 decimals for pH/EC and 1 for temp/humidity
3. **Band meter**: a horizontal track with the target zone shaded and a 2 px marker at the current value. This answers "how close to the edge?" better than any number.
4. Status row (icon + label)
5. Clicking a card opens the Graphs tab on that chart.

### History charts (dataviz)
- Line charts, 2 px strokes, and one series per chart (the title names it, so no legend is needed).
- Target band drawn as a recessive filled rectangle behind the line. Out-of-band segments get no extra color, because the band already shows it.
- A crosshair plus tooltip is synced across all four charts: hovering at 14:00 shows pH, EC, temp and humidity at 14:00.
- Gaps in data (bridge down, cable unplugged) render as **breaks in the line**, not interpolated, and a gap marker notes "no data 13:10–13:24".
- A table view toggle for accessibility. "Download CSV" serves the session log files directly (the current session, or every log that overlaps the chosen range).
- Server-side downsampling: 1 h = raw (1800 pts), 24 h = 1-minute buckets (1440), 7 d = 10-minute buckets (1008). Each bucket carries min/avg/max, and a faint min–max band can come later.

---

## 4. Motion plan (emil-design-eng)

The frequency rule decides everything. Live values update every 2 s, so **they do not animate**.

| Element | Seen | Decision |
|---|---|---|
| Value change every 2 s | ~1800×/h | **No animation.** Swap the text instantly; tabular numerals keep it stable. No count-up tickers. |
| Sparkline / chart new point | ~1800×/h | Append without an entrance animation. No re-drawing sweep. |
| Status change (In range → Drifting) | A few ×/day | 200 ms `ease` on color and background only. Meaningful, rare, and it deserves a soft transition. |
| Pump ON ↔ OFF | Tens ×/hour | 150 ms `ease` on the pill's color and background only. No pulsing or spinning "running" icon: the "running 8 s" counter already shows it's live. |
| "Live" dot | Constant | Static dot. At most a single 150 ms opacity blink per received message, and removed under reduced motion. No infinite pulse. |
| Stale state | Rare | 300 ms fade to desaturated. Recovery is instant (fast where the system responds). |
| Range tabs 1h/24h/7d | Tens/day | Sliding pill indicator, 200 ms `cubic-bezier(0.23,1,0.32,1)`. Chart data swaps with no animation. |
| Buttons | Often | `:active { transform: scale(0.97) }`, 160 ms ease-out |
| Calibration drawer/sheet | Rare | 300 ms `cubic-bezier(0.32,0.72,0,1)` (Vaul curve). Exit is faster than entry. |
| Toasts (command sent/reply) | Occasional | Sonner defaults. Pause timers when the tab is hidden. |
| Popovers/tooltips | Often | 125–150 ms, origin-aware (`--transform-origin`), instant on subsequent hovers |
| First page load | Once | 40 ms stagger on hero tiles (opacity + 8 px translate), never blocking interaction |

Global rules:
- Animate `transform` and `opacity` only, and never use `transition: all`.
- Tokens are `--ease-out: cubic-bezier(0.23,1,0.32,1)`, `--ease-in-out: cubic-bezier(0.77,0,0.175,1)` and `--ease-drawer: cubic-bezier(0.32,0.72,0,1)`.
- Honor `prefers-reduced-motion`: keep the color and opacity transitions and drop the translate/scale.
- Gate hover effects behind `@media (hover: hover) and (pointer: fine)`, because the kiosk is touch.
- Prefer CSS transitions and WAAPI. Motion (Framer) is only for the calibration flow if needed, which keeps the bundle small for the Pi.

---

## 5. Calibration wizard (the high-stakes flow)

Calibration is the one place where a mistake costs something (bad K-values, wasted buffer). It gets a dedicated sheet with the README steps turned into UI:

**EC:** `enterec` → "Probe in 1413 µS/cm buffer" → **stability gate** → `calec` → "Rinse, probe in 12.88 mS/cm" → stability gate → `calec` → `exitec` → show the result from `hydro/log`.

**pH:** optional zero-check (`po_mv` ≈ 2500 with a live readout) → pH 7 → stability gate → `ph7` → rinse → pH 4 → stability gate → `ph4` → show the slope (expect ≈ 180 mV/pH).

- **Stability gate.** The step shows a live `ec_mv`/`po_mv` readout with a countdown (20 s EC, 60–120 s pH). The "Capture" button stays disabled until the reading has varied < 1 % over the last 10 s. This replaces the "wait 20 s" instruction with something that can't be skipped by accident.
- **Expected-value hints.** The screen shows ~230 mV (1413 buffer) and ~2100 mV (12.88 buffer), and warns in-line if the reading is far off, before the user sends `calec`.
- **Replies.** `hydro/log` lines received during the wizard appear inline in the step. Errors such as `Buffer Solution Error` and `K out of range` turn the step critical and offer retry.
- Closing mid-flow asks for confirmation. A "Reset pH calibration" (`phreset`) button sits behind a hold-to-confirm (2 s linear clip-path fill, 200 ms release; Emil's hold-to-delete pattern).
- The `status` command is available as a "Show stored calibration" button.

---

## 6. Actuators: dosing and sampling pumps

Three pumps, each switched by its own relay on the ESP32:

| Pump | Job | JSON field | CSV column |
|---|---|---|---|
| Pump | Relay / GPIO | Job | JSON field | CSV column |
|---|---|---|---|---|
| Nutrient pump A | 2-ch relay IN1 / GPIO25 (active LOW) | Doses nutrient A | `pump_a` | `pump_a` |
| Nutrient pump B | 2-ch relay IN2 / GPIO26 (active LOW) | Doses nutrient B | `pump_b` | `pump_b` |
| Sampling pump | 1-ch relay IN / GPIO27 (active LOW) | Moves water for sampling, **always on** | `pump_sample` | `pump_sample` |
| Mode | n/a | `true` = AUTO (EC/pH target), `false` = MANUAL | `pump_auto` | `pump_auto` |

The dashboard **only displays** pump status in this phase. It has no ON/OFF buttons. The ESP32 decides when pumps run.

### How the firmware runs the pumps (`Full_code.ino`, as built)
- **Auto (default at boot).** Pump A and Pump B run *together* until EC is 1.2–1.8 mS/cm **and** pH is 5.5–6.5, then stop. They start again when either leaves the band. `ec_low` counts as under target (run); an invalid pH reading stops them.
- **Manual.** `pumpaon/pumpaoff/pumpbon/pumpboff` switch to manual; `pumpauto` goes back.
- **Sampling pump** runs all the time from the first reading, unless `sampleoff`.
- **Tank low** (`level_low`, only once the tank is calibrated) forces **all three** pumps OFF in auto and manual, and refuses ON commands.
- On every relay change the firmware prints `# Pump A ON` / `# Pump B OFF` / `# Sampling pump ON` to `hydro/log`, and `# Tank LOW - pumps stopped` / `# Tank OK - pumps allowed`.

So A and B are not short timed doses: in auto they can run for minutes. The cards and lanes must handle long runs, and "running 8 s" becomes "running 4 m 12 s".

### Where the status comes from
- **ESP32 firmware (done).** Every 2 s JSON line carries `pump_a`, `pump_b`, `pump_auto`, `pump_sample` as `true`/`false`:
  `{"temp":27.1, …, "dist_cm":14.2, "pump_a":true, "pump_b":true, "pump_auto":true, "pump_sample":true}`
  The values are the firmware's relay state after active-LOW conversion, so `true` always means running.
- **Change timing.** Pumps change at most once per reading (the auto logic runs right before each JSON line), so the 2 s JSON already catches every change. The `# Pump … ON/OFF` lines on `hydro/log` give the exact moment if needed.
- **`bridge.py` (done).** The fields travel on `hydro/sensors` as they are. `pump_a`, `pump_b`, `pump_auto` and `pump_sample` are in `LOG_FIELDS`, so every new session CSV records them as `1`/`0`. Logs from before this change have no pump columns.
- **Safety (firmware, not dashboard).** Relays start OFF at boot, and the tank-low stop protects against dry running. There is **no maximum run time** in the firmware yet: if a sensor fails in a way that still reads valid (e.g. EC probe out of the water reading 0), A and B would dose forever. Recommended: add a max continuous run (or timed pulses: 2 s ON, 30–60 s wait, re-check, as the README suggests). The dashboard only warns ("Pump A/B ON long") and doesn't act.

### `api.py` additions
- **`GET /api/latest`** gains an `actuators` object, so the page shows pump status right away before MQTT delivers the next reading:
  ```json
  "actuators": {
    "mode": "auto",
    "tank_lock": false,
    "pump_a":      {"state": "on",  "since": "2026-09-23T04:50:08", "runs_today": 3, "on_seconds_today": 540},
    "pump_b":      {"state": "on",  "since": "2026-09-23T04:50:08", "runs_today": 3, "on_seconds_today": 540},
    "pump_sample": {"state": "on",  "since": "2026-09-23T02:40:10", "runs_today": 1, "on_seconds_today": 7810}
  }
  ```
  `state` is `"on"`, `"off"` or `"unknown"`. It's `"unknown"` when the newest row is older than 10 s, or when a session log was written before the pump columns existed. `since` is the time of the last change, which the page uses for "running 8 s" and "last ran 04:47".
- **`GET /api/actuators/history?range=24h`** returns ON intervals per pump, `[{"pump":"pump_a","start":…,"end":…}]`, built from the 0→1 and 1→0 changes in the session CSVs. It powers the pump activity lanes. An interval still open at the end of a session file (the ESP32 was unplugged while a pump ran) is closed at the file's last row and flagged `"cut": true`.
- **Live.** The browser takes pump states directly from `hydro/sensors` over MQTT, the same as the sensor values. `useHydroLive()` keeps `since` per pump by watching for changes.

### Dashboard
- **Pump row.** Three cards between the reading tiles and the history charts: name, role, a large ON/OFF pill, "running 4 m 12 s" or "last ran 04:47 · 3 m", and "today: N runs · total time". A small chip at the end of the row shows the mode (**AUTO** · "stops at EC 1.2–1.8, pH 5.5–6.5", or **MANUAL**) and, when the tank is low, a "Tank low: all pumps stopped" banner. Since A and B always switch together in auto, their cards can share one "Nutrient A + B" header if space is tight.
- **Pump activity lanes.** Under the history charts: three thin ON/OFF lanes on the same time axis and crosshair as the charts, so a dose lines up with the EC rise that follows it.
- Pump runs don't go in the ESP32 log panel unless the firmware prints them to `hydro/log`.

---

## 7. Plant vision: size, growth stage and health (runs on the Pi 5)

> **Status: later phase.** No dataset has been collected yet (2026-09-23). Build the rest of the dashboard first. Until `vision.py` exists, the Plant card shows a "Camera not set up" empty state and the Graphs tab hides the stage strip, so nothing breaks while vision is missing.

### What the dataset gives, and what it doesn't
The dataset has two labels per image:

| Label | Classes |
|---|---|
| **Size** | Small, Medium, Large |
| **Stage** | Seedling Stage, Vegetative Stage, Matured Stage |

It has **no healthy/unhealthy label**, so a model trained on it can't learn health directly. The plan handles this in two phases:
- **Phase 1:** train size and stage models on the dataset. "Health" is a rule-based check built from the model results, leaf colour and the sensor data (below). It's labelled "Health check" in the UI, not "AI health".
- **Phase 2 (optional):** collect and label Healthy / Unhealthy photos (for example yellowing, tip burn, wilting, rot) from your own rack, then train a third model the same way as the other two.

### Step 0: check the dataset format
The training method depends on how the dataset is labelled:

| Dataset looks like | Meaning | Model |
|---|---|---|
| Folders per class, one plant per image (`Small/…jpg`, `Seedling Stage/…jpg`) | **Classification** | Two YOLO11n-cls models: `size.pt` and `stage.pt` |
| Whole-tray photos plus `.txt` / JSON bounding boxes (YOLO, COCO, Roboflow export) | **Detection** | One YOLO11n detect model that finds each plant. Each box is then classified for size and stage by the two cls models, or the detector's classes combine both (`Medium_Vegetative`, 9 classes) |

Classification is simpler and faster. If the camera sees several plants, detection is needed to report per-plant results.

### Training (on a PC or Google Colab, not the Pi)
1. Put the dataset in `ml/dataset/` using the Ultralytics layout (`train/`, `val/`, `test/`, one folder per class for cls).
2. **Split by plant or by date, not by random image**: photos of the same plant in both train and test inflate the accuracy. Use 70 / 20 / 10.
3. Check the class balance. If one class has less than half of the others' images, add augmentation (flip, rotate, brightness ±20 %) or more photos.
4. Train: `yolo classify train model=yolo11n-cls.pt data=ml/dataset/size imgsz=224 epochs=60` (and the same for `stage`).
5. **Add 50–100 photos from your own Pi camera** under your grow light to the training set, split across the classes. A model trained only on internet or lab photos often fails on a new camera and new light.
6. Accept a model when test top-1 accuracy is ≥ 90 % and no class falls below 80 % in the confusion matrix.
7. Export for the Pi: `yolo export model=best.pt format=ncnn`. NCNN is the fastest CPU runtime on the Pi 5. Copy the exported folder to `ml/models/size_ncnn_model/` and `ml/models/stage_ncnn_model/`.

Rough Pi 5 speed (CPU, NCNN): a 224 px classifier ≈ 10–30 ms, and a 640 px nano detector ≈ 100–250 ms. At one check every 15 minutes, the load is negligible.

### Camera
- **Pi Camera Module 3** on the CSI port (via `picamera2`), or a USB webcam (via OpenCV). Mount it at a **fixed height and angle** over the rack, so "Large" means the same thing every day.
- Take photos only while the grow light is on. Lock the white balance and exposure in `vision.py` so colour stays comparable over time.

### `vision.py` (new systemd service, `hydro-vision.service`)
Every 15 minutes (configurable), and on demand when the dashboard sends `snap` on `hydro/vision/cmd`, it:
1. Captures a photo and saves it to `data/vision/YYYY-MM-DD/HH-MM-SS.jpg`. Photos older than 30 days are deleted automatically, but one photo per day is kept for a growth timeline.
2. Runs the size and stage models and takes the top class and confidence of each. A result below 60 % confidence is reported as **"Uncertain"** instead of a guess.
3. Computes **leaf greenness**: an Excess Green index (ExG = 2G − R − B) over the plant pixels, plus the share of yellow/brown pixels.
4. Runs the **health check** (below).
5. Publishes to MQTT `hydro/vision` (retained, so a reloaded dashboard sees the last result at once):
   ```json
   {"ts": 1790154000, "image": "2026-09-23/05-00-00.jpg",
    "size": "Medium", "size_conf": 0.94,
    "stage": "Vegetative Stage", "stage_conf": 0.92,
    "greenness": 0.41, "yellow_pct": 2.1,
    "health": "healthy", "health_reasons": []}
   ```
6. Appends one row to `data/vision/vision_log.csv` (time, image, size, conf, stage, conf, greenness, yellow %, health, reasons).

### Health check (Phase 1 rules)
Three levels: **Healthy**, **Check**, **Unhealthy**. Each rule that fires adds a plain-language reason, which the card shows.

| Rule | Check | Unhealthy |
|---|---|---|
| Yellow/brown leaf area | > 8 % | > 20 % |
| Greenness vs 7-day average | drop > 15 % | drop > 30 % |
| Stage is behind for the plant's age (needs the transplant date) | 1 stage behind | 2 stages behind |
| Size shrank vs 3 days ago (same camera spot) | 1 class smaller | — |
| pH or EC out of band for > 6 h in the last 24 h | yes | > 18 h |
| Model uncertain on 3 checks in a row | yes | — |

Placeholder expected ages: Seedling 0–14 days, Vegetative 15–30 days, Matured 31+ days after sowing. Confirm these for your variety. The thresholds live in `ml/health_rules.yaml`, so they can be tuned without code changes.

### `api.py` additions
- `GET /api/vision/latest`: the last result, as above.
- `GET /api/vision/history?range=7d`: rows from `vision_log.csv`, for the stage strip on the Graphs tab.
- `GET /api/vision/image/{path}`: serves a saved photo, read-only and limited to `data/vision/`.

### Dashboard: Plant card (Overview)
- The latest snapshot (thumbnail), plus the time it was taken and when the next check is due.
- **Health** as the largest line: `check` Healthy / `arrow` Check / `alert` Unhealthy, using the same status colours and icons as the sensors. The reasons are listed under it, e.g. "Yellow leaf area 11 %".
- **Size** and **Stage** with their confidence (e.g. "Medium · 94 %"). "Uncertain" is shown in muted grey.
- A "Check now" button sends `snap`.

---

## 7a. File layout for vision
```
ml/
  dataset/                 # not in git (add to .gitignore)
  train.md                 # the exact training + export commands used
  models/size_ncnn_model/  # exported models (not in git; copied to the Pi)
  models/stage_ncnn_model/
  health_rules.yaml
vision.py
hydro-vision.service
data/vision/               # photos + vision_log.csv (already ignored under data/)
```

---

## 8. Architecture

```
Browser ──ws://pi:9001──► Mosquitto  (live: hydro/sensors incl. pump states, hydro/log, hydro/vision; send: hydro/cmd)
                              ▲
Pi camera ──► vision.py ──────┘ publishes hydro/vision · writes data/vision/
   │
   └──http://pi:8000────► FastAPI api.py ──read-only──► data/logs/log_NNNN_*.csv
                           ├─ GET /api/latest               (readings + actuators)
                           ├─ GET /api/actuators/history?range=24h  (pump ON intervals)
                           ├─ GET /api/history?range=24h   (bucketed)
                           ├─ GET /api/sessions             (list of log files)
                           ├─ GET /api/vision/latest | /history | /image/{path}
                           ├─ GET /api/sessions/{log_id}.csv (download one log)
                           └─ serves web/dist (built dashboard)
```

- **Live data** comes straight from Mosquitto's existing websocket listener (`mosquitto/local.conf`, port 9001) using `mqtt.js`. No new backend code is needed for realtime.
- **History** comes from a new `api.py` (FastAPI, from the README roadmap). It reads the session logs that `bridge.py` writes (one CSV per ESP32 connection, `log_id` + `row` + `time` columns). For a range it picks the files whose name date is inside or before the range, reads the rows in time order and buckets them. The gap between two session files becomes a gap in the chart. The file currently being written is read to its last complete line. Cache parsed closed files in memory, since only the newest one changes.
- A header chip shows the current session (`log #0007 · since 04:50`), from the newest file in `data/logs/`.
- The ESP32 log panel shows `hydro/log` messages live over MQTT and keeps the last 200 in memory. Nothing stores them on disk since the SQLite logger was removed, so the panel starts empty after a page reload. If older messages are needed, have `bridge.py` write them to a small `events` file next to each session log.
- On load, the dashboard fetches `/api/latest` so the page isn't empty for 2 s, then MQTT takes over.
- A single systemd unit, `hydro-api.service`, serves both API and static files. Use the full nvm node path only for building. At runtime it is Python only.
- **Security note (now urgent).** The 9001 websocket listener is LAN-wide and anonymous, so anyone on the network can publish to `hydro/cmd`. The firmware **now accepts** `pumpaon`, `pumpbon`, `sampleoff`, `pumpauto`, `tankreset`, `phreset` etc., and `bridge.py` forwards everything on `hydro/cmd` to the ESP32. So anyone on the LAN can already run a dosing pump or wipe calibration. Add a Mosquitto password and an ACL that lets only local clients (the bridge, the API) publish to `hydro/cmd` before exposing the dashboard. Displaying status (this plan) is read-only and safe.

### Frontend stack
| Concern | Choice | Why |
|---|---|---|
| Build | Vite + React + TypeScript | Fast, static output served by FastAPI |
| Styling | Tailwind v4 + CSS variables tokens | shadcn-compatible, themeable |
| Components | shadcn/ui: Card, Tabs, Sheet, Button, Tooltip, Table, Toggle Group, Dialog, Sonner | Accessible primitives |
| Charts | shadcn Chart (Recharts), data capped to ≤ 1500 pts per chart | Matches shadcn theming. Switch to uPlot if the Pi's browser struggles. |
| Live data | `mqtt.js` in one `useHydroLive()` hook with an external store (`useSyncExternalStore`) | Only subscribed components re-render every 2 s (vercel-react-best-practices) |
| History | TanStack Query, `staleTime` 60 s | Caching, refetch on range change |
| Fonts | `@fontsource-variable/geist` + `geist-mono` | Offline |

Performance rules for 2 s updates:
- Keep the live reading in an external store, not in top-level React state, and never re-render the whole page per message.
- Memoize the chart components. The live point is appended to the 1 h series only.
- Keep a ring buffer of the last 30 min in memory for the sparklines. Don't refetch.

### Proposed file layout
```
web/
  src/
    config/targets.ts        # bands + presets
    lib/mqtt.ts              # connection, reconnect, external store
    lib/api.ts               # /api/* fetchers
    hooks/useHydroLive.ts
    components/
      StatusHeader.tsx
      ReadingTile.tsx        # value, BandMeter, StatusBadge, Sparkline
      BandMeter.tsx
      PumpCard.tsx           # ON/OFF pill, running/last-ran, today's totals
      PumpLanes.tsx          # ON intervals on the history time axis
      PlantCard.tsx          # snapshot, health, size, stage
      StageStrip.tsx         # stage timeline on the Graphs tab
    pages/Overview.tsx, Graphs.tsx, Calibration.tsx   # one screen each, no scroll
      HistoryCharts.tsx      # synced small multiples
      EventLog.tsx
      calibration/EcWizard.tsx, PhWizard.tsx, StabilityGate.tsx
    styles/tokens.css        # light-mode colors, easing, durations
api.py
hydro-api.service
```

---

## 9. Build order

0. **Firmware + bridge.** ✅ Pump fields in the ESP32 JSON, pump columns in `LOG_FIELDS`, `log_id`/`row` in each `hydro/sensors` message. Still open: firmware max-run-time for Pump A/B, and MQTT auth/ACL on `hydro/cmd`.
1. **Tokens.** Light-mode colors (validated with dataviz `validate_palette.js`), type scale, easing and durations.
2. **`api.py`.** `/api/latest` (with `actuators`), `/api/history` with bucketing, `/api/actuators/history`, `/api/sessions`. Test with `curl`.
3. **Live hook.** MQTT over websocket with a connection/stale indicator.
4. **Hero tiles.** Value, band meter, status, sparkline, stale and not-installed states.
5. **Pump cards.** ON/OFF/unknown, running and last-ran timers, today's totals.
5a. **Vision (later, once the dataset exists).** Check the dataset format, train and export the size and stage models, mount the camera, write `vision.py` + `hydro-vision.service`, then build the Plant card.
6. **History charts + pump lanes.** Range tabs, synced crosshair, gaps, table view, CSV.
7. **Event log.**
8. **Calibration wizards** with stability gates.
9. **Audit pass.** `/impeccable audit`, `web-design-guidelines`, and `review-animations`, then fix.
10. `hydro-api.service` + README section. Tick "FastAPI" and "React dashboard" in the Roadmap.

## 10. Verification
- Unplug the ESP32. Tiles go stale within 10 s, the chart shows a gap, and plugging back in recovers without a reload.
- Put the EC probe in plain water. `ec_low` shows `< 0.6` with an explanation, not a false "Low" alarm.
- Throttle the CPU 4× in DevTools. 2 s updates don't drop frames, and React Profiler shows only the tiles re-render.
- Switch each relay by hand (or with a test sketch). The matching card turns ON within 2 s, "running" counts up, and OFF shows the right "last ran" duration. Test with the relay board's LED to confirm active-low boards aren't reported inverted.
- Unplug the ESP32 while a pump is ON. The card goes to "—" (unknown) within 10 s, never a frozen ON, and the activity lane marks the run as cut.
- Pull the EC probe out of solution in auto mode. Pumps A and B run, and after the warning time the cards show "ON long".
- Drop the tank below 20 % (after `tankempty`/`tankfull`). All three cards go to "OFF (lock icon) Tank low" within 2 s, and back when refilled.
- Send `pumpaon` on `hydro/cmd`. The mode chip switches to MANUAL; `pumpauto` switches it back.
- Open each tab full-screen on the 1920×1080 display. Nothing is cut off and the page doesn't scroll.
- Vision: run `vision.py --once` on 10 plants you've labelled by hand. At least 9 of 10 match for size and stage. Cover the camera and confirm the card shows "Uncertain", not a guess.
- Health: hold a yellowed leaf in view. The card goes to Check with a yellow-area reason.
- Test on a phone and with reduced motion.
- Run a full EC calibration with real buffers through the wizard and confirm `status` shows the new K-values.

## Open decisions
- Air temperature and humidity target bands for your room (placeholder: 18–26 °C, 50–75 %).
- Whether the Pi drives a touchscreen kiosk (this affects the default layout and touch sizing).
- ~~Which GPIO pins drive the relays~~: decided (GPIO25/26/27, active LOW).
- Maximum continuous run for Pump A/B in the firmware, and the dashboard "ON long" warning time (placeholder 10 min).
- Whether A and B should dose in timed pulses instead of running until target (avoids overshoot while sensors settle).
- What the sampling pump feeds (sensor chamber? tank loop?), for its card's subtitle.
- The dataset's format (class folders or bounding boxes) and number of images per class.
- Which camera (Pi Camera Module 3 or USB), and where it's mounted.
- The sowing/transplant date per batch, and the expected age for each stage.
- Whether to collect Healthy/Unhealthy photos for a Phase 2 health model.
- What the README's MaixVision camera plan becomes. This plan runs vision on the Pi 5 instead.
- Whether the dashboard should ever control the pumps (a later phase; needs the MQTT auth above first).
