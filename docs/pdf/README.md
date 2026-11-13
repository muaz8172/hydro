# Project documents (PDF)

| File | Pages | Contents |
|---|---|---|
| `01_Introduction.pdf` | 3 | Background, problem statement, objectives, scope, components, key features, project status |
| `02_ESP32_Pin_Configuration.pdf` | 2 | Pinout diagram, pin table, pH and HC-SR04 voltage dividers, power rails, firmware settings |
| `03_Dataset.pdf` | 3 | Lettuce growth-stage photo dataset, preparation, model results, sensor and camera log columns |
| `04_System_Diagram_and_Flowchart.pdf` | 3 | Block diagram (ESP32 → USB serial → bridge → MQTT → dashboard/logs/camera), MQTT topics, services, firmware and pump flowcharts |
| `05_Dashboard_Overview.pdf` | 3 | Annotated screenshots of the Live Monitoring, Sensor History and Calibration tabs |
| `Hydro_System_Guide.pdf` | | Full technical guide (built by `docs/guide/build_guide.py`) |
| `EC_Sensor_Guide.pdf` | 3 | How the EC sensor works, pins, calibration, target ranges |
| `innovation_fard.pdf` | 8 | Innovation 2026 project paper |

## Editing and rebuilding 01–05

The PDFs are built from the HTML pages in `src/` (one file per document, shared `style.css`,
same fonts and colours as the dashboard). Edit the HTML, then:

```bash
pip install playwright
playwright install chromium            # or on Windows: set HYDRO_PDF_BROWSER=msedge
python docs/pdf/src/render.py          # all five
python docs/pdf/src/render.py 03       # only 03_Dataset
```

Commit both the HTML and the PDF.

## Dashboard screenshots

`screenshots/` holds the dashboard images used in 01 and 05. They were taken on 13 Nov 2026 by
running `backend/server.py` and a local Mosquitto on a PC, with simulated sensor readings and a
dataset photo, so the values are examples, not measurements. To retake them on the Pi with real
data, open `http://localhost:8000` at 1440×900 and save each tab.
