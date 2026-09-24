# Hydro Dashboard: Design Plan

Mockups: https://claude.ai/artifact/WkQEocQ3YATsaeQA4zAjFX (desktop, phone, EC calibration wizard)
Tab preview (2026-09-24): https://claude.ai/artifact/Ke1uhL6rPhz34KexXA1yyg (Overview, Graphs, Calibration, and what changed in this plan)

> **Status (2026-09-24):** built as a plain HTML page (`frontend/index.html`) with three tabs, served by `backend/server.py`. The growth-stage model is trained and runs in `vision.py`. See section 9 for what's done and what's left.

A dashboard for the lettuce hydroponic system. It shows live readings from `hydro/sensors`, the ON/OFF status of the three pumps (nutrient A, nutrient B, sampling), the lettuce's size, growth stage and health from a camera model running on the Pi 5, history from the session CSV logs in `data/logs/`, the ESP32 message log, and guided calibration over `hydro/cmd`.

Skills used: **emil-design-eng** (motion and feel), **dataviz** (charts, color, status), **design-taste-frontend / minimalist-ui** (visual direction). The original plan used React + shadcn; it was changed to plain HTML on 2026-09-24 (section 8). Run **impeccable** / **web-design-guidelines** as audits once built.

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

**Tank level (added 2026-09-24):** drain to MIN → stability gate → `tankempty` → fill to MAX → stability gate → `tankfull`. The firmware already supports this, and the dry-run stop (`level_low`) only works once the tank is calibrated. The gate for `dist_cm` uses an absolute tolerance (±0.5 cm), because 1 % of a few cm is below the HC-SR04's noise.

As built: the gates are EC 20 s minimum + ≤ max(1 %, 3 mV) over 10 s, pH 60 s + ≤ 5 mV over 10 s (≈ 0.03 pH), tank 10 s + ≤ 0.5 cm. The capture button also needs live ESP32 data. A step advances only on the firmware's success line (`Successful,K`, `pH7 saved`, `tankfull saved`, …); a rejection line or no reply within 10 s shows an error and keeps the step. "Stop" in the middle of EC calibration offers to send `exitec`, since the ESP32 has no cancel command.

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

### History API (`backend/server.py`)
- ✅ **`GET /api/actuators/history?range=24h`** is built (section 8): ON intervals, run count and on-time per pump.
- Not built yet: **`GET /api/latest`** with an `actuators` object, so the page shows pump status right away before MQTT delivers the next reading:
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
- The actuators history is built from the 0→1 and 1→0 changes in the session CSVs. It powers the pump activity lanes. An interval still open at the end of a session file (the ESP32 was unplugged while a pump ran) is closed at the file's last row and flagged `"cut": true`.
- **Live.** The browser takes pump states directly from `hydro/sensors` over MQTT, the same as the sensor values, and keeps `since` per pump by watching for changes.

### Dashboard
- **Pump row.** Three cards between the reading tiles and the history charts: name, role, a large ON/OFF pill, "running 4 m 12 s" or "last ran 04:47 · 3 m", and "today: N runs · total time". A small chip at the end of the row shows the mode (**AUTO** · "stops at EC 1.2–1.8, pH 5.5–6.5", or **MANUAL**) and, when the tank is low, a "Tank low: all pumps stopped" banner. Since A and B always switch together in auto, their cards can share one "Nutrient A + B" header if space is tight.
- **Pump activity lanes.** Under the history charts: three thin ON/OFF lanes on the same time axis and crosshair as the charts, so a dose lines up with the EC rise that follows it.
- Pump runs don't go in the ESP32 log panel unless the firmware prints them to `hydro/log`.

---

## 7. Plant vision: growth stage, size and health (runs on the Pi 5)

> **Status (2026-09-24):** the growth-stage model is trained and runs in `vision.py`. Size comes from the stage. Health is still the leaf-colour rule.

### What exists now
- **Camera:** Sipeed MaixCAM on the Pi's USB (a USB network link, camera at `10.122.173.1`). The `hydro_cam` app on the camera serves `/snap.jpg`. `vision.py` on the Pi fetches a live photo every 10 s and saves one every 15 min (or on `snap` sent to `hydro/vision/cmd`).
- **Dataset:** `dataset/lettuce_growth_stages/`, 41 photos in class folders (seedling 18, vegetative 6, matured 17), plus a 224×224 JPEG copy in `dataset/lettuce_224/` with `labels.csv` (`file, stage, size, source`). Both are in git.
- **Model:** `backend/models/stage.onnx` (MobileNetV3-Small, 6.1 MB), trained on the Pi by `backend/train/train_stage.py`. It runs with ONNX Runtime in `.venv` in **19 ms per photo** on the Pi 5, so it checks every live photo.
- **MQTT:** `hydro/vision` (JSON), `hydro/vision/image` (the JPEG, retained), `hydro/vision/status`.
- **Storage:** `data/vision/YYYY-MM-DD/HH-MM-SS.jpg` plus `data/vision/vision_log.csv`.

### Labels: size follows stage
The dataset is labelled by stage only. Size is taken from the stage, so one model gives both:

| Stage | Size | Photos |
|---|---|---|
| Seedling | Small | 18 |
| Vegetative | Medium | 6 |
| Matured | Large | 17 |

There's **no healthy/unhealthy label**, so health stays a rule (below). A Phase 2 health model needs labelled Healthy/Unhealthy photos from your own rack.

### Training (done on the Pi 5)
`.venv/bin/python backend/train/train_stage.py` (about 20 minutes on the Pi 5's CPU):
1. Starts from MobileNetV3-Small pretrained on ImageNet and fine-tunes it. Augmentation (random crop, flips, ±20° rotation, colour jitter) and class-weighted loss, since vegetative has only 6 photos.
2. **5-fold stratified cross-validation**, so every photo is tested once by a model that never saw it. Two models are compared: A (classifier) and B (regression on the stage number 1–3).
3. Reports train vs test accuracy, **MAE / MSE / RMSE / MAPE** on the stage number (Small = 1, Medium = 2, Large = 3), per-stage precision/recall/F1 and a confusion matrix, against two baselines. Output: `backend/models/stage_report.md`, `stage_training.png`, `stage_predictions.csv`.
4. Trains the better model on all photos and exports `backend/models/stage.onnx` + `stage_labels.json`.

**First result (2026-09-24):**

| Model | Test acc | MAE | MSE | RMSE | MAPE |
|---|---|---|---|---|---|
| Always Small (baseline) | 44 % | 0.98 | 1.80 | 1.34 | 35 % |
| **A: classifier (exported)** | **90 %** | **0.10** | **0.10** | **0.31** | **6 %** |
| B: regression | 63 % | 0.37 | 0.37 | 0.60 | 24 % |

Seedling recall 94 %, matured 100 %, **vegetative 50 %** (3 of 6). It never confuses Small with Large. Train accuracy is 100 %, so it partly memorises the photos.

Acceptance (unchanged in spirit, adjusted to the tiny dataset): test accuracy ≥ 80 %, MAE < 0.3, vegetative recall > 50 %, better than both baselines. **Vegetative recall is the one check that fails.**

### Next for the model
1. **More vegetative photos**, 10–15 at least.
2. **Photos from the MaixCAM itself** (`data/vision/`). All 41 training photos come from the internet; the camera sees one fixed view under your grow light, so the real accuracy may be lower than the test score. Label 20–50 camera photos into the three folders and retrain.
3. Retrain: `.venv/bin/python backend/train/train_stage.py`, then restart `hydro-vision`. The new `stage.onnx` is picked up at start.
4. Optional later: run it on the MaixCAM's NPU instead. It needs converting with TPU-MLIR, which runs on an x86 PC, not on the Pi.

### Camera
- Mount it at a **fixed height and angle** over the rack, so "Large" means the same thing every day.
- Take photos only while the grow light is on.

### `vision.py` (`hydro-vision.service`, runs with `.venv/bin/python`)
Every 10 s (live) and every 15 min (saved), it:
1. Fetches a photo from the MaixCAM.
2. Runs the **leaf-colour check** (canopy %, yellow/brown %, greenness, health).
3. If a plant is in view, runs the **stage model**: `stage` (seedling / vegetative / matured), `stage_conf`, `size` (small / medium / large). Below **60 %** confidence the stage is `"uncertain"` and size is left empty. With no plant in view the model is skipped, because it forces every photo into one of the three stages (a photo of a keyboard came out as "seedling, 95 %").
4. Publishes to `hydro/vision` (retained):
   ```json
   {"ts": 1790154000, "image": "2026-09-24/05-00-00.jpg",
    "canopy_pct": 38.4, "yellow_pct": 1.2, "greenness": 0.41,
    "health": "healthy", "health_reasons": [],
    "stage": "vegetative", "stage_conf": 0.87, "size": "medium"}
   ```
   If ONNX Runtime or the model file is missing, the three stage fields are left out and everything else still works.
5. Saved photos append a row to `vision_log.csv`: `time, image, canopy_pct, yellow_pct, greenness, health, reasons, stage, stage_conf, size`. An older log without the stage columns is upgraded automatically at start.

Test without the camera: `.venv/bin/python backend/vision.py --stage photo1.jpg photo2.jpg`.

### Health check
As built (colour only): **Healthy**, **Check** (yellow/brown > 8 %), **Unhealthy** (> 20 %), **No plant** (< 2 % green in view).

Still planned, now that stage exists:

| Rule | Check | Unhealthy |
|---|---|---|
| Greenness vs 7-day average | drop > 15 % | drop > 30 % |
| Stage is behind for the plant's age (needs the sowing date) | 1 stage behind | 2 stages behind |
| Stage went backwards vs 3 days ago (same camera spot) | yes | — |
| pH or EC out of band for > 6 h in the last 24 h | yes | > 18 h |
| Model uncertain on 3 checks in a row | yes | — |

Placeholder expected ages: Seedling 0–14 days, Vegetative 15–30 days, Matured 31+ days after sowing.

### Dashboard
- **Overview, Plant camera card:** photo, health verdict, **growth stage** (with a colour swatch), **size**, model confidence, then canopy / yellow / greenness. "Uncertain" and "model off" show in muted grey.
- **Graphs, plant stage strip:** a lane under the pump lanes, coloured by stage from `vision_log.csv` (one block per saved check, hatched when uncertain), on the same time axis as the charts.

---

## 7a. File layout for vision
```
dataset/lettuce_growth_stages/   # original photos (in git)
dataset/lettuce_224/             # 224x224 JPEG copy + labels.csv (in git)
backend/train/train_stage.py     # cross-validation, report, ONNX export
backend/train/requirements.txt   # packages for .venv
backend/models/stage.onnx        # exported model (in git, 6 MB)
backend/models/stage_labels.json # classes, sizes, preprocessing
backend/models/stage_report.md   # latest training report
backend/vision.py
backend/systemd/hydro-vision.service   # runs vision.py with .venv/bin/python
data/vision/                     # photos + vision_log.csv (ignored under data/)
```

---

## 8. Architecture

```
Browser ──ws://pi:9001──► Mosquitto  (live: hydro/sensors, hydro/log, hydro/vision*; send: hydro/cmd, hydro/vision/cmd)
                              ▲
MaixCAM (USB) ──► vision.py ─┘ publishes hydro/vision · writes data/vision/ (stage model in .venv)
   │
   └──http://pi:8000────► backend/server.py (standard library) ──read-only──► data/logs/log_NNNN_*.csv
                           ├─ GET /api/history?range=1h|24h|7d       readings on a fixed grid, null = no data
                           ├─ GET /api/actuators/history?range=…     pump ON intervals, runs, on-time
                           ├─ GET /api/vision/history?range=…        rows from vision_log.csv
                           ├─ GET /api/export.csv?range=…            session rows in the range, one CSV
                           └─ serves frontend/ (index.html, vendor/, live/ → data/vision/live)
```

- **Live data** comes straight from Mosquitto's websocket listener (port 9001) using the vendored `mqtt.js`.
- **History** comes from `backend/server.py`, which replaced `python3 -m http.server` (and the planned FastAPI `api.py`: FastAPI isn't installed and isn't needed). For a range it picks the session CSVs whose file name date is before the range end and whose last write is after the range start, reads the rows and averages them into buckets: 1h = 2 s, 24h = 60 s, 7d = 600 s. Empty buckets are `null`, so gaps show as breaks. `ec` is `null` where `ec_low = 1`. Closed files are cached until they change.
- **Pump runs** are rebuilt from the 0→1 and 1→0 changes. A run is closed and marked `cut` when the data stops for more than 10 s or the session file ends.
- The Graphs tab refetches every 10 s (1h), 60 s (24h) or 120 s (7d) while it's open.
- **Security note (still open).** The 9001 websocket listener is LAN-wide and anonymous, and the Calibration tab now publishes to `hydro/cmd`. Anyone on the LAN can already send any ESP32 command. Adding a Mosquitto password and an ACL for `hydro/cmd` was deferred on 2026-09-24.

### Frontend stack (changed 2026-09-24)
| Concern | Choice | Why |
|---|---|---|
| Page | One static `frontend/index.html`, no build step | The live page already worked offline this way; no Node build on the Pi |
| Charts | uPlot 1.6.31, vendored in `frontend/vendor/` (~50 KB) | Fast on the Pi, handles 1800 points per chart, synced crosshair built in |
| Live data | `mqtt.js`, vendored | Offline |
| History | `fetch()` to `backend/server.py` | Standard library only |
| Fonts | System UI + system monospace | Offline, nothing to host |

Performance rules still hold: values swap text with no animation, charts only redraw on a refetch, and only the visible tab does work.

### File layout (repo reorganised 2026-09-24)
```
frontend/
  index.html          # Overview, Graphs, Calibration tabs
  vendor/mqtt.min.js, uPlot.iife.min.js, uPlot.min.css
  live -> ../data/vision/live
backend/
  server.py           # serves frontend/ + /api/* history
  bridge.py, vision.py, models/, train/
  systemd/hydro-dashboard.service   # runs backend/server.py
```

---

## 9. Build order

0. **Firmware + bridge.** ✅ Pump fields, pump columns, `log_id`/`row`. Still open: firmware max-run-time for Pump A/B, and MQTT auth/ACL on `hydro/cmd`.
1. **Overview page.** ✅ Sensor tiles with band meters, pump cards, raw values, camera card (2026-09-23).
2. **Vision.** ✅ MaixCAM + `vision.py` + colour health (2026-09-23). ✅ Dataset, training, `stage.onnx`, stage/size in `vision.py` and on the Plant card (2026-09-24).
3. **History server.** ✅ `backend/server.py` with `/api/history`, `/api/actuators/history`, `/api/vision/history`, `/api/export.csv`.
4. **Graphs tab.** ✅ 1h/24h/7d, four charts with target bands and gap hatching, synced crosshair, table view, CSV download, pump lanes, plant stage strip.
5. **Calibration tab.** ✅ EC, pH and tank wizards with stability gates, stored calibration (`status`), hold-to-reset pH.
6. **Next:** pump "today" totals and "last ran" on the Overview cards (from `/api/actuators/history`), the "Pump ON long" warning, ESP32 message log, health rules that use stage.
7. **Model:** more vegetative photos and MaixCAM photos, then retrain (section 7).
8. **Audit pass** (`web-design-guidelines`, reduced motion, phone width), then MQTT auth.

## 10. Verification
- Unplug the ESP32. Tiles go stale within 10 s, the chart shows a gap, and plugging back in recovers without a reload.
- Put the EC probe in plain water. `ec_low` shows `< 0.6` with an explanation, not a false "Low" alarm.
- Throttle the CPU 4× in DevTools. 2 s updates don't drop frames.
- Switch each relay by hand (or with a test sketch). The matching card turns ON within 2 s, "running" counts up, and OFF shows the right "last ran" duration. Test with the relay board's LED to confirm active-low boards aren't reported inverted.
- Unplug the ESP32 while a pump is ON. The card goes to "—" (unknown) within 10 s, never a frozen ON, and the activity lane marks the run as cut.
- Pull the EC probe out of solution in auto mode. Pumps A and B run, and after the warning time the cards show "ON long".
- Drop the tank below 20 % (after `tankempty`/`tankfull`). All three cards go to "OFF (lock icon) Tank low" within 2 s, and back when refilled.
- Send `pumpaon` on `hydro/cmd`. The mode chip switches to MANUAL; `pumpauto` switches it back.
- Open each tab full-screen on the 1920×1080 display. Nothing is cut off and the page doesn't scroll.
- Vision: run `.venv/bin/python backend/vision.py --stage` on 10 camera photos you've labelled by hand. At least 8 of 10 should match. Cover the camera and confirm the card shows "No plant in view" with no stage, not a guess.
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
- ~~The dataset's format~~: decided (class folders, 41 photos; size follows stage).
- ~~Which camera~~: decided (Sipeed MaixCAM over USB). Still open: where it's mounted.
- The sowing/transplant date per batch, and the expected age for each stage.
- Whether to collect Healthy/Unhealthy photos for a Phase 2 health model.
- ~~Where the model runs~~: decided (Pi 5, ONNX Runtime, 19 ms). The MaixCAM NPU stays an option.
- ~~React or plain HTML~~: decided (plain HTML + vendored uPlot).
- When to add MQTT auth/ACL, now that the Calibration tab sends commands.
- Whether the dashboard should ever control the pumps (a later phase; needs the MQTT auth above first).
