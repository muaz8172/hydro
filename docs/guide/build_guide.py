"""Build docs/Hydro_System_Guide.pdf.

Run:  .venv/bin/python docs/guide/build_guide.py
Needs: reportlab (pip install reportlab) and the DejaVu fonts (fonts-dejavu-core).
Edit the text in this file, rebuild, and commit both this file and the PDF.
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "Hydro_System_Guide.pdf")
VERSION = "5"
DATE = "7 October 2026"
MODEL_DATE = "29 September 2026"   # last stage-model retrain

FONTS = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("Sans", f"{FONTS}/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", f"{FONTS}/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Mono", f"{FONTS}/DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans",
                              boldItalic="Sans-Bold")

INK = colors.HexColor("#1f1f1f")
GREY = colors.HexColor("#5a5a5a")
LINE = colors.HexColor("#d6d4cc")
HEAD_BG = colors.HexColor("#f1f0eb")
BLUE = colors.HexColor("#2d5fb4")
BLUE_BG = colors.HexColor("#e7eef9")
GREEN = colors.HexColor("#4a7a2a")
GREEN_BG = colors.HexColor("#edf2e8")
AMBER = colors.HexColor("#b36b12")
AMBER_BG = colors.HexColor("#faf2e1")
CODE_BG = colors.HexColor("#f5f5f2")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
WIDTH = PAGE_W - 2 * MARGIN

body = ParagraphStyle("body", fontName="Sans", fontSize=10, leading=14.2, textColor=INK,
                      spaceAfter=6, alignment=TA_LEFT)
small = ParagraphStyle("small", parent=body, fontSize=8.8, leading=12, spaceAfter=0)
cell = ParagraphStyle("cell", parent=body, fontSize=8.8, leading=11.5, spaceAfter=0)
cell_b = ParagraphStyle("cell_b", parent=cell, fontName="Sans-Bold")
h1 = ParagraphStyle("h1", parent=body, fontName="Sans-Bold", fontSize=18, leading=22,
                    spaceBefore=0, spaceAfter=8, keepWithNext=1)
h2 = ParagraphStyle("h2", parent=body, fontName="Sans-Bold", fontSize=13, leading=17,
                    spaceBefore=8, spaceAfter=4, keepWithNext=1)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=3)
code_style = ParagraphStyle("code", fontName="Mono", fontSize=7.8, leading=10, textColor=INK)
title = ParagraphStyle("title", parent=body, fontName="Sans-Bold", fontSize=32, leading=38,
                       spaceAfter=4)
subtitle = ParagraphStyle("subtitle", parent=body, fontSize=14, leading=18, textColor=GREY,
                          spaceAfter=10)
meta = ParagraphStyle("meta", parent=body, fontSize=8.5, leading=12, textColor=GREY, spaceAfter=0)


def c(text):
    """Inline code."""
    return f'<font face="Mono" size="8.3">{text}</font>'


def P(text, style=body):
    return Paragraph(text, style)


def H1(text):
    return P(text, h1)


def H2(text):
    return P(text, h2)


def bullets(items):
    return [Paragraph(t, bullet, bulletText="•") for t in items]


def code(text):
    lines = text.strip("\n").split("\n")
    html = "<br/>".join(l.replace("&", "&amp;").replace("<", "&lt;").replace(" ", "&nbsp;")
                        for l in lines)
    t = Table([[Paragraph(html, code_style)]], colWidths=[WIDTH])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                           ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([t, Spacer(1, 7)])


def table(rows, widths, shade=None, mono_cols=()):
    """rows[0] is the header. widths are fractions of the page width.
    shade maps a row index to 'blue' or 'amber' to tint that row's last cell."""
    data = []
    for i, r in enumerate(rows):
        out = []
        for j, v in enumerate(r):
            if i == 0:
                out.append(Paragraph(v, cell_b))
            elif j in mono_cols:
                out.append(Paragraph(c(v), cell))
            else:
                out.append(Paragraph(v, cell))
        data.append(out)
    t = Table(data, colWidths=[w * WIDTH for w in widths], repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
          ("BOX", (0, 0), (-1, -1), 0.5, LINE),
          ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
          ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 6),
          ("RIGHTPADDING", (0, 0), (-1, -1), 6),
          ("TOPPADDING", (0, 0), (-1, -1), 5),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
    for i, kind in (shade or {}).items():
        st.append(("BACKGROUND", (-1, i), (-1, i), BLUE_BG if kind == "blue" else AMBER_BG))
    t.setStyle(TableStyle(st))
    return [t, Spacer(1, 8)]


def callout(text, kind="blue"):
    bar, bg = (BLUE, BLUE_BG) if kind == "blue" else (AMBER, AMBER_BG)
    t = Table([[Paragraph(text, small)]], colWidths=[WIDTH])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg),
                           ("LINEBEFORE", (0, 0), (0, -1), 2.5, bar),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                           ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return [Spacer(1, 4), t, Spacer(1, 8)]


# ---------------------------------------------------------------- diagrams

class Diagram(Flowable):
    """Boxes and arrows drawn with top-left coordinates in points."""

    def __init__(self, height, draw_fn):
        super().__init__()
        self.width, self.height, self.draw_fn = WIDTH, height, draw_fn

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        self.draw_fn(self)

    def y(self, top):
        return self.height - top

    def box(self, x, top, w, h, head, lines=(), style="white", mono_lines=False, line_gap=9.6):
        cv = self.canv
        stroke, fill = {"white": (LINE, colors.white), "green": (GREEN, GREEN_BG),
                        "blue": (BLUE, BLUE_BG), "grey": (LINE, HEAD_BG),
                        "blueline": (BLUE, colors.white)}[style]
        cv.setStrokeColor(stroke)
        cv.setFillColor(fill)
        cv.setLineWidth(0.8)
        cv.roundRect(x, self.y(top + h), w, h, 4, stroke=1, fill=1)
        cv.setFillColor(INK)
        cv.setFont("Sans-Bold", 8.5)
        cv.drawString(x + 7, self.y(top + 13), head)
        cv.setFillColor(GREY)
        cv.setFont("Mono" if mono_lines else "Sans", 7.3)
        for i, line in enumerate(lines):
            cv.drawString(x + 7, self.y(top + 25 + i * line_gap), line)

    def text(self, x, top, s, font="Sans", size=7.3, color=GREY, anchor="left"):
        cv = self.canv
        cv.setFont(font, size)
        cv.setFillColor(color)
        draw = {"left": cv.drawString, "right": cv.drawRightString}[anchor]
        draw(x, self.y(top), s)

    def line(self, x1, t1, x2, t2, arrow=False, dashed=False):
        cv = self.canv
        cv.setStrokeColor(GREY)
        cv.setLineWidth(0.7)
        cv.setDash(2, 2) if dashed else cv.setDash()
        cv.line(x1, self.y(t1), x2, self.y(t2))
        cv.setDash()
        if arrow:
            import math
            a = math.atan2(self.y(t2) - self.y(t1), x2 - x1)
            p = cv.beginPath()
            p.moveTo(x2, self.y(t2))
            for da in (2.7, -2.7):
                p.lineTo(x2 + 5 * math.cos(a + da), self.y(t2) + 5 * math.sin(a + da))
            p.close()
            cv.setFillColor(GREY)
            cv.drawPath(p, stroke=0, fill=1)


def draw_overview(d):
    d.box(0, 0, 134, 122, "ESP32 (Full_code.ino)",
          ["DHT22 air temp/humidity", "EC probe · pH probe", "HC-SR04 water level",
           "Relay 1 (2ch): Pump A + B", "Relay 2 (2ch): sampling", "Auto dosing to EC/pH",
           "Tank-low stop"], "green")
    d.box(174, 12, 134, 62, "backend/bridge.py",
          ["serial → MQTT", "CSV log per connection", "hydro-bridge.service"])
    d.box(348, 12, 134, 60, "data/logs/",
          ["log_NNNN_date_time.csv", "one file per ESP32", "connection"])
    d.box(174, 98, 134, 40, "Mosquitto (MQTT)", ["1883 local · 9001 websocket"], "grey")
    d.box(348, 86, 134, 60, "Dashboard :8000",
          ["server.py + frontend/", "Live Monitoring ·", "History · Calibration"], "blue")
    d.box(0, 162, 134, 72, "Sipeed MaixCAM",
          ["hydro_cam app (auto-start)", "live preview on its screen", "GET /snap.jpg 640×480",
           "USB network: 10.122.173.1"], "green")
    d.box(174, 162, 134, 80, "backend/vision.py",
          ["photo every 10 s", "leaf colour health check", "growth-stage model (ONNX)",
           "save every 15 min", "hydro-vision.service"])
    d.box(348, 162, 134, 60, "data/vision/",
          ["YYYY-MM-DD/*.jpg", "vision_log.csv", "live/latest.jpg + .json"])
    d.line(134, 41, 174, 41, arrow=True)
    d.text(138, 37, "USB serial", color=BLUE)
    d.line(308, 41, 348, 41, arrow=True)
    d.line(241, 74, 241, 98, arrow=True)
    d.line(241, 162, 241, 138, arrow=True)
    d.line(308, 118, 348, 118, arrow=True)
    d.text(313, 114, "live data", color=BLUE)
    d.line(134, 195, 174, 195, arrow=True)
    d.text(139, 191, "USB", color=BLUE)
    d.line(308, 195, 348, 195, arrow=True)
    d.line(415, 162, 415, 146, arrow=True)
    d.text(420, 158, "HTTP fallback", color=BLUE)


def draw_relays(d):
    d.box(0, 0, 118, 185, "ESP32 (Full_code.ino)",
          ["RELAY_ACTIVE_LOW = true", "(LOW = relay ON)"], "green")
    d.text(9, 169, "5V  → VCC of both relays")
    d.text(9, 179, "GND → GND of both relays")
    d.box(178, 0, 122, 85, "Relay 1 (2-channel)", ["Nutrient dosing"], "blueline")
    d.box(178, 100, 122, 85, "Relay 2 (2-channel)", ["Sampling pump + spare"], "blueline")
    for top, pin in ((47, "GPIO18"), (69, "GPIO19"), (142, "GPIO21")):
        d.text(112, top + 3, pin, font="Mono", size=7, color=INK, anchor="right")
        d.line(118, top, 178, top)
    for base in (0, 100):
        for k, top in enumerate((47, 69)):
            d.text(185, base + top + 3, f"IN{k + 1}", font="Mono", size=7, color=INK)
            d.text(293, base + top + 3, f"CH{k + 1}", font="Mono", size=7, color=INK,
                   anchor="right")
    d.box(357, 21, 125, 26, "Pump In (Pump A)")
    d.box(357, 57, 125, 26, "Pump Out (Pump B)")
    d.box(357, 116, 125, 26, "Pump N (sampling)")
    d.box(357, 152, 125, 26, "Spare (not connected)", style="grey")
    d.line(300, 47, 357, 34)
    d.line(300, 69, 357, 70)
    d.line(300, 147, 357, 129)
    d.line(300, 169, 357, 165, dashed=True)


# ---------------------------------------------------------------- page frame

def footer(canv, doc):
    canv.saveState()
    canv.setStrokeColor(LINE)
    canv.setLineWidth(0.5)
    canv.line(MARGIN, 16 * mm, PAGE_W - MARGIN, 16 * mm)
    canv.setFont("Sans", 7.5)
    canv.setFillColor(GREY)
    canv.drawString(MARGIN, 12 * mm, f"Hydro · Lettuce hydroponic system · System guide v{VERSION}")
    canv.drawRightString(PAGE_W - MARGIN, 12 * mm, f"Page {doc.page}")
    canv.restoreState()


# ---------------------------------------------------------------- content

# Growth-stage model results (from backend/models/stage_report.md)
M = {
    "photos": 88, "per_stage": (30, 29, 29),
    "acc": "86 %", "mae": "0.16", "rmse": "0.45",
    "recall": ("97 %", "79 %", "83 %"), "veg_hits": "79 % (23 of 29): target met",
    "base_acc": "34 % and 33 %", "ms": "10", "minutes": "40",
    "chosen": "A: classifier (B, regression, reached 76 %)",
    "train_acc": "100 % (train–test gap 13 %: acceptable)",
    "old_fresh": "Old: 60 %, vegetative 29 %. New: 81 %, vegetative 79 %",
}


def cover():
    s = [Spacer(1, 40 * mm), P("Hydro", title),
         P("Lettuce hydroponic system: how it works, what has been built, and how to run it",
           subtitle),
         P("Raspberry Pi 5 · ESP32 · Sipeed MaixCAM · MQTT · Python", meta),
         P(f"Version {VERSION} · Status as of {DATE} · Repository: github.com/muaz8172/hydro "
           "(private)", meta), Spacer(1, 12)]
    s += table([["Contents", ""],
                ["1. System overview", "What each part does and how data flows"],
                ["2. Hardware and wiring", "Pins, dividers, the two 2-channel relays, camera link"],
                ["3. How it works", "Sensors, pump control, logging, camera, AI model, dashboard, "
                                    "dataset"],
                ["4. What has been done", "Progress, commits and current status"],
                ["5. How to run the system", "First-time setup, daily use, commands"],
                ["6. Calibration", "EC, pH and tank level; target ranges"],
                ["7. Troubleshooting", "Common problems and fixes"],
                ["8. Known issues and next steps", "Safety items and roadmap"]], [0.42, 0.58])
    s += [Spacer(1, 8)]
    s += callout(
        f"<b>What's new in version {VERSION}</b><br/>"
        "• <b>New ESP32 pin layout:</b> Pump In (Pump A) D18, Pump Out (Pump B) D19, "
        "Pump N (sampling pump) D21, DHT22 D4, EC D32, pH D33 (both ADC1), HC-SR04 TRIG D16 / "
        "ECHO D17 (via its divider). No strapping or flash pins are used. Pump logic, commands "
        "and JSON fields are the same. Rewire before re-flashing.<br/>"
        "• Version 4: <b>Minimalist dashboard</b> titled Hydroponic System Monitoring, with tabs Live "
        "Monitoring, Sensor History and Calibration, and DM Sans + Fraunces fonts (stored "
        "offline). The camera frame is square and shows the same centre crop the stage model "
        "sees (the dataset is 224×224). Sensor tiles show a green dot or a short tag (LOW, "
        "HIGH, DRIFT); raw values move to hover tooltips. New Plant vision card (canopy with "
        "change vs yesterday, yellowing, green index) and an animated water tank driven by the "
        "ultrasonic level sensor. Sensor History has area charts with value tags, time-in-target rings, pump and "
        "water-level bars, and a paged table. See section 3.6.<br/>"
        "• <b>Pump start delay:</b> after every ESP32 boot (Pi reboot or USB replug) the "
        "sampling pump waits 30 s and Pump A/B wait 60 s before auto control turns them on. "
        "See section 3.2.<br/>"
        f"• Version 3: <b>New plant dataset:</b> {M['photos']} lettuce photos, balanced across the three "
        f"stages (seedling {M['per_stage'][0]}, vegetative {M['per_stage'][1]}, matured "
        f"{M['per_stage'][2]}), all resized to 224×224 for training. Before: 41 photos with only "
        "6 vegetative.<br/>"
        f"• <b>Growth-stage model retrained</b> ({c('backend/models/stage.onnx')}): "
        f"{M['acc']} test accuracy, vegetative recall {M['recall'][1]} "
        "(target raised from 50 % to 70 %). See section 3.5.<br/>"
        "• Version 2 changes are still in place: two 2-channel relays (section 2.1), air "
        f"temperature target 25–36 °C ({c('temp_ok')}), the three dashboard tabs, and "
        f"the {c('frontend/')}, {c('backend/')}, {c('firmware/')} layout.")
    return s + [PageBreak()]


def overview():
    s = [H1("1. System overview"),
         P("The system grows lettuce in a hydroponic tank and watches it all day without internet. "
           "An <b>ESP32</b> reads the water and air sensors and switches the pumps through two "
           "2-channel relays. A <b>Raspberry Pi 5</b> collects everything, stores it, and serves a "
           "dashboard. A <b>Sipeed MaixCAM</b> camera photographs the plants so their health, "
           "growth stage and size can be checked."),
         Spacer(1, 8), Diagram(245, draw_overview), Spacer(1, 12),
         P("Everything talks through <b>MQTT</b> (the Mosquitto broker on the Pi). Each program "
           "publishes on its own topic, and the dashboard listens to all of them live.")]
    s += table([["MQTT topic", "Sent by", "Contents"],
                ["hydro/sensors", "bridge.py", f"One JSON reading every 2 s from the ESP32, plus "
                                               f"{c('log_id')} and {c('row')} that match the CSV line"],
                ["hydro/log", "bridge.py", "Text messages from the ESP32 (calibration, pump ON/OFF, "
                                           "tank low)"],
                ["hydro/cmd", "you / dashboard", f"Commands forwarded to the ESP32 (e.g. {c('status')}, "
                                                 f"{c('ph7')}, {c('pumpauto')}, {c('sampleoff')})"],
                ["hydro/vision", "vision.py", "Plant result (JSON) every 10 s: health, stage, size"],
                ["hydro/vision/image", "vision.py", "The latest camera photo (JPEG, retained)"],
                ["hydro/vision/status", "vision.py", f"{c('online')} or {c('offline: reason')}"],
                ["hydro/vision/cmd", "dashboard", f"{c('snap')} = save a photo to disk now"]],
               [0.26, 0.17, 0.57], mono_cols=(0,))
    return s + [PageBreak()]


def hardware():
    s = [H1("2. Hardware and wiring")]
    s += table([["Part", "Pins", "ESP32 / Pi", "Notes"],
                ["DHT22 (air temp / humidity)", "DATA / VCC / GND", "GPIO4 (D4) / 3.3 V / GND",
                 "10 k pull-up if the module has none"],
                ["EC sensor (EC V2.1)", "A0 / VCC / GND", "GPIO32 (D32, ADC1) / 3.3 V / GND",
                 "T1 unconnected; EC maths built into the firmware"],
                ["pH sensor (PH-4502C)", "Po / V+ / G", "GPIO33 (D33, ADC1) via divider / 5 V / GND",
                 "10 k / 20 k divider is required"],
                ["HC-SR04 (water level)", "TRIG / ECHO / VCC / GND",
                 "GPIO16 (D16) / GPIO17 (D17) via divider / 5 V / GND",
                 "1 k / 2 k divider on ECHO; mounted above the tank, facing down"],
                ["Relay 1 (2-channel)", "IN1 / IN2 / VCC / GND",
                 "GPIO18 (Pump In) / GPIO19 (Pump Out) / 5 V / GND",
                 "Active LOW; GND shared with the ESP32"],
                ["Relay 2 (2-channel)", "IN1 / IN2 / VCC / GND",
                 "GPIO21 (Pump N, sampling) / not connected / 5 V / GND",
                 "Active LOW; IN2 is a spare channel; GND shared with the ESP32"],
                ["ESP32 → Pi", "USB", "/dev/esp32 (udev rule)", "115200 baud, one JSON line every 2 s"],
                ["MaixCAM → Pi", "USB-C", "10.122.173.1 (camera), 10.122.173.100 (Pi)",
                 "Appears as a USB network adapter; the Pi gets its address automatically"]],
               [0.22, 0.2, 0.3, 0.28])
    s += [P("Never put more than 3.3 V on an ESP32 pin. The pH module and the HC-SR04 run on 5 V, "
            "which is why their outputs go through voltage dividers. Keep the pH and EC probes in "
            "separate containers when testing; they interfere with each other.", small),
          Spacer(1, 6),
          P("<b>Safe pins only.</b> No boot strapping pins (0, 2, 5, 12, 15) or flash pins (6–11) "
            "are used. EC and pH are on ADC1 (GPIO32/33), which keeps working if Wi-Fi is ever "
            "turned on; ADC2 pins stop reading analog while Wi-Fi is on.", small),
          PageBreak()]

    s += [H2("2.1 Relays: two 2-channel modules"),
          P("The pumps are switched by <b>two identical 2-channel relay modules</b>. The old "
            "1-channel relay for the sampling pump has been removed. Relay 1 doses the nutrients; "
            "relay 2 runs the sampling pump and keeps one channel free."),
          Spacer(1, 8), Diagram(188, draw_relays), Spacer(1, 10)]
    s += table([["Relay", "Channel", "ESP32 pin", "Drives", "Firmware name", "JSON field"],
                ["Relay 1", "IN1", "GPIO18", "Pump In (Pump A)", c("PUMP_A_PIN"), c("pump_a")],
                ["Relay 1", "IN2", "GPIO19", "Pump Out (Pump B)", c("PUMP_B_PIN"), c("pump_b")],
                ["Relay 2", "IN1", "GPIO21", "Pump N (sampling pump)", c("SAMPLE_PIN"), c("pump_sample")],
                ["Relay 2", "IN2", "—", "Spare, not connected", "—", "—"]],
               [0.12, 0.11, 0.13, 0.24, 0.2, 0.2])
    s += bullets([
        f"Both modules share one setting in {c('Full_code.ino')}: {c('RELAY_ACTIVE_LOW true')} "
        f"(LOW = relay ON). If your modules turn ON with HIGH, set it to {c('false')}. The old "
        f"separate {c('SAMPLE_ACTIVE_LOW')} setting is gone.",
        "Relay VCC goes to the ESP32's 5 V, and relay GND must be shared with the ESP32 GND, "
        "otherwise the IN signals have no reference.",
        "At boot every relay pin is set to OFF before it becomes an output, so no pump kicks on "
        "while the ESP32 starts. The sampling pump switches on 30 s after start-up and Pump A/B "
        "auto control starts after 60 s (see 3.2).",
        "The spare channel (relay 2 IN2) is free for a future grow-light relay (see section 8). "
        "It is not used by the firmware yet."])
    s += callout("<b>Mains safety.</b> If a pump or a future grow light runs on mains voltage, keep "
                 "the relay contacts and mains wiring in a closed box, away from the water, and "
                 "use a fused supply.", "amber")
    return s + [PageBreak()]


def how_it_works():
    s = [H1("3. How it works"), H2("3.1 Sensors (ESP32)"),
         P("Every 2 seconds the ESP32 reads all sensors and prints one JSON line over USB:"),
         code('{"temp":28.1,"hum":70.2,"ec":1.45,"ec_low":false,"ph":6.20,"level":9.8,"level_pct":72,\n'
              ' "level_low":false,"ec_mv":237,"po_mv":2650,"dist_cm":10.2,\n'
              ' "pump_a":true,"pump_b":true,"pump_auto":true,"pump_sample":true,"temp_ok":true}')]
    s += table([["Field", "Meaning"],
                ["temp, hum", "Air temperature (°C) and humidity (%) from the DHT22"],
                ["ec", "Electrical conductivity (mS/cm): how much nutrient is in the water"],
                ["ec_low", "true = below the ESP32's measuring floor (about 0.6 mS/cm), e.g. plain water"],
                ["ph", "pH value of the nutrient solution"],
                ["level, level_pct", "Water height (cm) and tank level (%) from the HC-SR04, after "
                                     "tank calibration"],
                ["level_low", "true = tank below 20 %"],
                ["pump_a, pump_b", "Relay 1 IN1 / IN2 state (true = running)"],
                ["pump_sample", "Relay 2 IN1 state: the sampling pump (true = running)"],
                ["pump_auto", "true = automatic EC/pH control, false = manual commands"],
                ["temp_ok", "true = air temperature inside 25–36 °C, null = no DHT22 reading. Only "
                            "reported; nothing heats or cools"],
                ["ec_mv, po_mv, dist_cm", "Raw sensor values, used for calibration and debugging"]],
               [0.3, 0.7], mono_cols=(0,))

    s += [H2("3.2 Pump control (ESP32)"),
          P("The firmware keeps the nutrient solution inside the lettuce target: EC 1.2–1.8 mS/cm "
            "and pH 5.5–6.5.")]
    s += bullets([
        "<b>Auto mode</b> (on at boot): Pump A and Pump B (relay 1) run together while EC or pH is "
        "outside the target, and stop when both are inside. They start again if either drifts out. "
        f"{c('ec_low')} counts as under target.",
        f"<b>Sampling pump</b> (relay 2 IN1): runs all the time to move water past the sensors. It "
        f"is not affected by EC/pH. {c('sampleoff')} stops it (e.g. for maintenance), "
        f"{c('sampleon')} starts it again.",
        "<b>Tank-low protection</b>: when the tank is below 20 % (after tank calibration) all three "
        "pumps, on both relays, are forced OFF, in auto and manual, so they never run dry. "
        f"{c('pumpaon')}, {c('pumpbon')} and {c('sampleon')} are refused until the tank is refilled.",
        f"<b>Manual</b>: {c('pumpaon')}, {c('pumpaoff')}, {c('pumpbon')}, {c('pumpboff')} switch to "
        f"manual; {c('pumpauto')} goes back to auto.",
        "A pH reading that is not a number stops Pumps A and B for safety.",
        f"<b>Start delay</b>: after every ESP32 boot (Pi reboot, bridge restart or USB replug) the "
        f"sampling pump waits 30 s ({c('SAMPLE_START_DELAY')}) and Pump A/B wait 60 s "
        f"({c('PUMP_START_DELAY')}) before auto turns them on. Manual commands are not delayed.",
        f"Air temperature is only checked against 25–36 °C and reported as {c('temp_ok')}. No "
        "relay acts on it."])
    s += table([["Situation", "Pump A + Pump B (relay 1)", "Sampling pump (relay 2)"],
                ["EC or pH outside target (auto)", "ON", "ON"],
                ["EC 1.2–1.8 and pH 5.5–6.5 (auto)", "OFF (target reached)", "ON"],
                ["pH reading invalid (auto)", "OFF (safety)", "ON"],
                ["Tank low (calibrated tank)", "OFF, also in manual", "OFF"],
                [f"{c('sampleoff')} sent", "unchanged", f"OFF until {c('sampleon')}"]],
               [0.4, 0.3, 0.3])

    s += [H2("3.3 Data logging (Raspberry Pi, backend/bridge.py)"),
          P(f"{c('bridge.py')} reads the ESP32's serial port, publishes each reading to MQTT and "
            "writes it to a CSV file. Each time the ESP32 connects (plugged in, Pi reboot, bridge "
            "restart) a new file starts:"),
          code("data/logs/log_0007_2026-09-23_07-28-38.csv\n"
               "log_id,row,time,temp,hum,ec,ec_low,ph,level,level_pct,level_low,dist_cm,\n"
               "ec_mv,po_mv,pump_a,pump_b,pump_auto,pump_sample"),
          P(f"True/false values are stored as 1/0 and missing values as empty cells. The files open "
            f"directly in Excel or LibreOffice Calc. {c('temp_ok')} is not a CSV column; it can be "
            f"worked out from {c('temp')}. The {c('data/')} folder is not uploaded to GitHub.")]

    s += [H2("3.4 Plant camera (MaixCAM + backend/vision.py)"),
          P(f"The MaixCAM is a small computer with its own camera and screen. Its {c('hydro_cam')} "
            "app starts at boot, shows a live preview (to aim the camera) and hands a fresh photo "
            "to the Pi over the USB cable.")]
    s += bullets([
        f"Every <b>10 s</b> {c('vision.py')} takes a photo, checks it and publishes it to the dashboard.",
        f"Every <b>15 min</b> (or with <b>Save photo now</b>) it also saves the photo to "
        f"{c('data/vision/&lt;date&gt;/')} and adds a row to {c('vision_log.csv')}. Photos older than "
        "30 days are deleted, except one per day.",
        f"It also writes {c('data/vision/live/latest.jpg')} so the dashboard can still show the "
        "photo if the live MQTT link is blocked.",
        f"When a plant is in view it runs the growth-stage model (section 3.5) and adds "
        f"{c('stage')}, {c('stage_conf')} and {c('size')} to the result."])
    s += table([["Health result", "Rule (leaf colour check)"],
                ["Healthy", "Yellow/brown share of the leaf area is 8 % or less"],
                ["Check leaves", "Yellow/brown share above 8 %"],
                ["Unhealthy", "Yellow/brown share above 20 %"],
                ["No plant in view", "Less than 2 % of the photo is green (camera aim, focus or "
                                     "grow light)"]], [0.3, 0.7])
    s += [code('{"ts": 1790161885, "image": "2026-09-23/07-11-25.jpg", "canopy_pct": 34.2,\n'
               ' "yellow_pct": 3.1, "greenness": 0.41, "health": "healthy", "health_reasons": [],\n'
               ' "stage": "vegetative", "stage_conf": 0.87, "size": "medium"}')]

    s += [H2("3.5 Growth-stage AI model"),
          P(f"{c('backend/train/train_stage.py')} trains a small image model (MobileNetV3-Small, "
            f"pretrained on ImageNet) on {c('dataset/lettuce_224/')}, on the Pi 5 itself, in about "
            f"{M['minutes']} minutes. It compares two versions, a classifier and a regression "
            "model, with 5-fold cross-validation: the photos are split into 5 groups, and each "
            "group is tested by a model trained on the other four, so every photo is tested once "
            f"by a model that never saw it. The better one is retrained on all photos and exported "
            f"to {c('backend/models/stage.onnx')}, which {c('vision.py')} runs with ONNX Runtime "
            f"from the {c('.venv')} environment. The full report is "
            f"{c('backend/models/stage_report.md')}.")]
    s += table([[f"Result ({M['photos']} photos, retrained {MODEL_DATE})", "Value"],
                ["Model chosen", M["chosen"]],
                ["Test accuracy", f"{M['acc']} (always-guess-one-stage baselines: {M['base_acc']})"],
                ["Train accuracy", M["train_acc"]],
                ["Mean absolute error", f"{M['mae']} stage (RMSE {M['rmse']})"],
                ["Seedling / matured recall", f"{M['recall'][0]} / {M['recall'][2]}"],
                ["Vegetative recall (target 70 %)", M["veg_hits"]],
                ["Old model (41 photos) on the 48 new photos it never saw", M["old_fresh"]],
                ["Speed on the Pi 5", f"about {M['ms']} ms per photo"]], [0.55, 0.45])
    s += [P(f"{c('stage')} is seedling, vegetative, matured, or uncertain below 60 % confidence. "
            f"{c('size')} follows the stage (seedling = small, vegetative = medium, matured = "
            "large). The model only runs when the colour check finds a plant, because it knows "
            "only the three stages and would label anything as one of them.", small),
          Spacer(1, 6)]

    s += [H2("3.6 Dashboard"),
          P(f"A web page served by {c('backend/server.py')} on port 8000 (page files in "
            f"{c('frontend/')}). Live values come from Mosquitto's websocket (port 9001); history "
            f"comes from the session CSVs. Everything works offline (mqtt.js, uPlot and the DM Sans "
            f"and Fraunces fonts are in {c('frontend/vendor/')}).")]
    s += table([["Tab", "What it shows"],
                ["Live Monitoring", "Header: Live dot, ESP32 and Camera shown as Connected (green) or "
                             "Disconnected/Offline (red). Left: the camera photo in a square frame, "
                             "the same centre crop the stage model sees, with health, growth stage, "
                             "size, confidence and Save photo. Right: tiles for pH, EC, Air Temperature "
                             "25–36 °C (Cold / Stable / Hot, Stable turns amber near the edges) "
                             "and humidity with a meter and a green dot or LOW/HIGH/DRIFT tag, plus "
                             "pump mode + tank state; pump rows; Plant vision (canopy % with change vs "
                             "yesterday, yellowing % with Normal under 8 %, green index 0–1); an "
                             "animated water tank filled to the ultrasonic level, with the 20 % "
                             "dry-run line, an OK/LOW tag, water height and distance to the surface. "
                             "Hover for details and raw values; click a tile for Sensor History"],
                ["Sensor History", "Four area charts (pH purple, EC teal, air magenta, humidity blue) "
                                   "for 1 h, 24 h or 7 days, with dot markers and a tag on the highest "
                                   "value; hover shows values on all four. Below: time in target as ring "
                                   "gauges, nutrient pump minutes per slot as bars, the average of each "
                                   "sensor, water level as capsule bars and plant stage over time. Table "
                                   "view shows every reading, newest first, one page at a time (as many "
                                   "rows as fit the screen); CSV downloads the range"],
                ["Calibration", "Step-by-step EC, pH and tank wizards. Capture buttons stay "
                                "disabled until the reading is steady; the ESP32's replies show in "
                                "the page; stored calibration and a hold-to-reset for pH"]],
               [0.2, 0.8])
    s += table([["History API (server.py)", "Returns"],
                ["/api/history?range=1h|24h|7d", "Readings on a fixed time grid (null = no data)"],
                ["/api/actuators/history?range=...", "Pump ON intervals, runs and on-time per pump"],
                ["/api/vision/history?range=...", f"Rows from {c('data/vision/vision_log.csv')}"],
                ["/api/export.csv?range=...", "Every session CSV row in the range, one file"]],
               [0.48, 0.52], mono_cols=(0,))

    s += [H2("3.7 Plant image dataset"),
          P(f"{c('dataset/lettuce_growth_stages/')} holds {M['photos']} lettuce photos sorted by "
            "growth stage (the folder name is the label). The originals come in different sizes "
            f"and formats. {c('dataset/lettuce_224/')} has the same photos all converted to the "
            f"same size, <b>224×224 JPEG</b> (rotated upright, centre-cropped to a square, "
            f"resized), with a {c('labels.csv')} that adds the size. This copy is what the model "
            "trains on.")]
    s += table([["Stage", "Folder", "Photos", "Size label"],
                ["Seedling", "seedling/", str(M["per_stage"][0]), "small"],
                ["Vegetative", "vegetative/", str(M["per_stage"][1]), "medium"],
                ["Matured (ready to harvest)", "matured/", str(M["per_stage"][2]), "large"],
                ["<b>Total</b>", "", f"<b>{M['photos']}</b>", ""]],
               [0.4, 0.25, 0.15, 0.2], mono_cols=(1,))
    s += [P("The 28 September update added 48 new photos to the 40 kept from the first set, so "
            "the classes are now balanced. One photo was in the dataset twice, once as vegetative "
            f"({c('vegetative_012.jpg')}) and once as matured ({c('matured_022.jpg')}); both copies "
            "were removed because its stage is unclear. All photos are still from the internet: "
            f"add labelled photos from the Hydro camera ({c('data/vision/')}), then retrain.", small)]
    return s + [PageBreak()]


def done():
    rows = [["Area", "Work", "Status"],
            ["ESP32 firmware", "DHT22, EC and pH with calibration stored in EEPROM", "Done"],
            ["ESP32 firmware", "HC-SR04 water level with tank calibration", "Done"],
            ["ESP32 firmware", "Pump A/B auto control to EC 1.2–1.8 and pH 5.5–6.5; manual commands",
             "Done"],
            ["ESP32 firmware", "Always-on sampling pump (GPIO21) and tank-low stop for all pumps",
             "Done"],
            ["ESP32 firmware", f"Air temperature target 25–36 °C, reported as {c('temp_ok')}", "Done"],
            ["ESP32 firmware", "Start delay after boot: sampling pump 30 s, Pump A/B auto 60 s", "Done"],
            ["Hardware", "1-channel relay replaced by a second 2-channel relay (sampling pump on "
                         f"relay 2 IN1; IN2 spare); one shared {c('RELAY_ACTIVE_LOW')}", "Done"],
            ["Hardware", "New pin layout: pumps D18 / D19 / D21, DHT22 D4, EC D32, pH D33, "
                         "HC-SR04 TRIG D16 / ECHO D17; firmware, test sketches and docs updated", "Done"],
            ["Testing", "Relay test sketch: relay 1 switched Pump A and Pump B correctly (old pins)",
             "Done"],
            ["Testing", "Rewire to the new pins, re-flash, check every sensor and relay; re-check "
                        "EC and pH against the buffers", "To do"],
            ["Testing", f"Sampling pump on relay 2: check with {c('sampleoff')} / {c('sampleon')}",
             "To do"],
            ["Raspberry Pi", "Serial → MQTT bridge with auto-reconnect and fixed /dev/esp32 name",
             "Done"],
            ["Raspberry Pi", "Bridge runs only while the ESP32 is plugged in, and resets the ESP32 "
                             "when it opens the port", "Done"],
            ["Raspberry Pi", "Mosquitto broker (local TCP + websocket for the dashboard)", "Done"],
            ["Data logging", "CSV log per ESP32 connection, including pump columns", "Done"],
            ["Camera", "MaixCAM app: auto-start, preview, photo server over USB", "Done"],
            ["Camera", "vision.py: live photos, leaf colour health check, photo archive", "Done"],
            ["Camera AI", f"Growth-stage dataset: {M['photos']} photos, balanced (30 / 29 / 29), "
                          "plus a 224×224 copy with size labels", "Done"],
            ["Camera AI", f"Growth-stage + size model retrained on {M['photos']} photos "
                          f"({M['acc']} test accuracy, vegetative recall {M['recall'][1]})", "Done"],
            ["Dashboard", "Live Monitoring, Sensor History and Calibration tabs; history API and CSV export", "Done"],
            ["Repository", f"Reorganised into {c('frontend/')}, {c('backend/')}, {c('firmware/')}",
             "Done"],
            ["Camera AI", "Label photos from the Hydro camera and add them to the dataset, then "
                          "retrain", "To do"],
            ["Sensors", "DS18B20 water temperature for EC compensation", "To do"],
            ["Safety", "Password/ACL on MQTT; maximum run time for Pumps A/B", "To do"]]
    s = [H1("4. What has been done")]
    s += table(rows, [0.18, 0.67, 0.15],
               shade={i: "amber" for i, r in enumerate(rows) if r[2] == "To do"})
    s += [H2("Development history (GitHub commits)")]
    s += table([["Commit", "What changed"],
                ["6214b11", "Initial commit: ESP32 firmware, serial bridge, README"],
                ["5b9a0b8 · 97d15b4", "Full README (wiring, calibration, troubleshooting); systemd, "
                                      "Mosquitto and udev configs"],
                ["9de0bf0 · 27b1f4d", "Sensor prototyping sketches, circuit diagram, relay test, "
                                      "HC-SR04 in the firmware"],
                ["07c09f3 → 6a15904", "Pump A/B relay control, tank-low stop, EC/pH target control, "
                                      "always-on sampling pump"],
                ["bd111f6", "CSV session logs with pump state"],
                ["68434be", "Dashboard design plan"],
                ["2856219", "MaixCAM plant camera with leaf colour health check"],
                ["3272c0d · a066e70", "First live dashboard page, with an HTTP fallback for the "
                                      "camera photo"],
                ["02f4b24 · 8e573f3", "System guide (PDF), version 1"],
                ["24d1ede · 84a2ea7", "Lettuce growth-stage dataset (41 photos) and its 224×224 "
                                      "copy with size labels"],
                ["761e8d3", "Growth-stage model, Graphs and Calibration tabs, history server"],
                ["5094bcc · d537789", f"Repository reorganised into frontend/, backend/ and firmware/"],
                ["ff034c4", f"Air temperature target 25–36 °C ({c('temp_ok')})"],
                ["e59755a", "1-channel relay replaced by a second 2-channel relay"],
                ["d131785", "New lettuce dataset: 90 photos (30 per stage)"],
                ["f962ca6", "System guide version 2"],
                ["5dfbf3f", "Duplicate photo removed (88 photos), growth-stage model "
                            "retrained, system guide version 3"],
                ["827a7ce", "Out-of-range pH readings ignored in history; graph axes capped"],
                ["42c3365", "Minimalist dashboard: new header and tab names, square camera "
                            "frame, Plant vision card, coloured sensor graphs, DM Sans + Fraunces"],
                ["f90c27b", "Charts leave empty time before/after the data blank"],
                ["be3eed7", "Sensor History: area charts with value tags, time-in-target rings, "
                            "pump and water-level bars, paged table"],
                ["b79f89d", "Live MQTT readings fed straight into the charts (no reload lag)"],
                ["ee15e07", "Animated water tank on Live Monitoring; Water tile removed"],
                ["989ff9d", "EC read on the 11 dB ADC range (millivolts were 3x too high)"],
                ["6b7d698", "Calibration tab saves each EC buffer separately"],
                ["b89f97e", "EC conversion and calibration built into the firmware; DFRobot_EC "
                            "removed (its calibration() crashed every EC save)"],
                ["d63ccb6", "Crash probes removed; EC calibration verified to survive a replug"],
                ["27a3ecb", "Docs: EC calibration is built into the firmware"],
                ["f8898e1 · 4b692ae", "Bridge starts when the ESP32 is plugged in and stops when it "
                                      "is unplugged; it resets the ESP32 on connect"],
                ["aa305f1", "Pump start delay after ESP32 boot (sampling 30 s, Pump A/B 60 s)"],
                ["98d2714", "System guide version 4"],
                ["9680cb3", "ESP32 pins moved: pumps D18/D19/D21, DHT22 D12, HC-SR04 TRIG D33 / "
                            "ECHO D32"],
                ["(this version)", "System guide version 5: safe pin layout (no strapping pins; "
                                   "EC/pH on ADC1 GPIO32/33, DHT22 GPIO4, HC-SR04 GPIO16/17)"]], [0.26, 0.74])
    s += [H2("Current status")]
    status = [["Part", "State"],
              ["ESP32 + bridge", "Running · started by itself after a Pi reboot (log #0043, 29 Sep)"],
              ["Firmware", f"Updated · new pin layout (7 Oct). Rewire, re-flash "
                           f"{c('Full_code.ino')}, then check every sensor and pump"],
              ["Mosquitto", "Running"],
              ["MaixCAM", "Running · photos reach the Pi; aim the camera at the plants"],
              ["Stage model", f"Updated {MODEL_DATE} · retrained on {M['photos']} photos; restart "
                              f"{c('hydro-vision')} to load it"],
              ["vision.py / dashboard", "Running · services enabled, start at every boot"],
              ["pH probe", "Check · still reads 19.71 on 29 Sep: disconnected or not in solution"],
              ["Water level", "Check · still no echo from the HC-SR04 on 29 Sep (level empty)"],
              ["EC", f"Check · 0.0 with {c('ec_low')} on 29 Sep (probe dry or not connected); "
                     "Pumps A/B dose nonstop while it reads this"]]
    s += table(status, [0.26, 0.74],
               shade={i: ("blue" if r[1].startswith("Updated") else "amber")
                      for i, r in enumerate(status)
                      if r[1].startswith(("Updated", "Check"))})
    return s + [PageBreak()]


def run():
    s = [H1("5. How to run the system"), H2("5.1 First-time setup"),
         P(f"Upload {c('firmware/Full_code/Full_code.ino')} to the ESP32 with the Arduino IDE "
           "(board: ESP32 Dev Module; libraries: DHT sensor library and Adafruit Unified Sensor; no EC "
           "library is needed, the EC maths and calibration are built into the sketch). Then on the Pi:"),
         code("sudo apt install mosquitto mosquitto-clients python3-serial python3-paho-mqtt python3-pil\n"
              "cd ~/hydro\n"
              "sudo cp backend/mosquitto/local.conf /etc/mosquitto/conf.d/\n"
              "sudo cp backend/udev/99-esp32.rules /etc/udev/rules.d/\n"
              "sudo udevadm control --reload-rules && sudo udevadm trigger\n"
              "sudo usermod -aG dialout $USER            # then reboot\n"
              "sudo systemctl restart mosquitto"),
         P("Python environment for the growth-stage model (one time):"),
         code("cd ~/hydro\n"
              "python3 -m venv .venv\n"
              ".venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu\n"
              ".venv/bin/pip install -r backend/train/requirements.txt"),
         P("Install the camera app on the MaixCAM (one time):"),
         code("scp -r ~/hydro/maixcam/hydro_cam root@10.122.173.1:/maixapp/apps/\n"
              "ssh root@10.122.173.1 'echo hydro_cam > /maixapp/auto_start.txt && reboot'\n"
              "ssh root@10.122.173.1 passwd          # change the factory password"),
         H2("5.2 Install the three services"),
         code("cd ~/hydro\n"
              "sudo cp backend/systemd/hydro-bridge.service backend/systemd/hydro-vision.service \\\n"
              "        backend/systemd/hydro-dashboard.service /etc/systemd/system/\n"
              "sudo systemctl daemon-reload\n"
              "sudo systemctl disable hydro-bridge     # drop the old start-at-boot link, if any\n"
              "sudo systemctl enable --now hydro-bridge hydro-vision hydro-dashboard"),
         P("hydro-vision and hydro-dashboard start at every boot. hydro-bridge is tied to the ESP32 "
           "(dev-esp32.device from the udev rule): plugging the ESP32 in, or booting with it attached, "
           "starts the bridge, and unplugging it stops the bridge. When the bridge opens the port it "
           "resets the ESP32, so every connect starts a new CSV log and a new pump start delay.", small),
         P(f"If vision.py or the dashboard are still running from a manual start, stop them first: "
           f"{c('pkill -f vision.py; pkill -f server.py')}", small),
         H2("5.3 Daily use")]
    s += bullets([
        "Power on the Pi with the ESP32 and the MaixCAM plugged in by USB. All services start by "
        "themselves.",
        f"Open the dashboard: {c('http://localhost:8000')} on the Pi, or "
        f"{c('http://&lt;pi-ip&gt;:8000')} from a phone on the same WiFi (find the IP with "
        f"{c('hostname -I')}).",
        "Check the header at the top right: Live, ESP32 and Camera should be green.",
        f"Check the pump cards: Sampling should show ON (relay 2) from 30 s after start-up, unless "
        f"the tank is low or {c('sampleoff')} was sent. Pumps A/B follow EC/pH from 60 s after start-up.",
        "Aim the camera at the lettuce using the preview on the MaixCAM screen. Take photos under "
        "the grow light."])
    s += [PageBreak(), H2("5.4 Useful commands")]
    s += table([["Command", "What it does"],
                ["systemctl status hydro-bridge hydro-vision hydro-dashboard", "Are the services running?"],
                ["journalctl -u hydro-bridge -f", "Follow the bridge log (ESP32 messages, new CSV files)"],
                ["journalctl -u hydro-vision -f", "Follow the camera log (saved photos, health and "
                                                  "stage results)"],
                ["mosquitto_sub -t 'hydro/#' -v", "Watch everything on MQTT (the image topic prints binary)"],
                ["mosquitto_pub -t hydro/cmd -m status", "Ask the ESP32 for its calibration, pump and "
                                                         "sampling pump state"],
                ["mosquitto_pub -t hydro/cmd -m pumpauto", "Put Pumps A and B back in automatic mode"],
                ["mosquitto_pub -t hydro/cmd -m sampleoff", f"Stop the sampling pump (relay 2); "
                                                            f"{c('sampleon')} starts it"],
                ["mosquitto_pub -t hydro/vision/cmd -m snap", "Save a camera photo now"],
                ["~/hydro/.venv/bin/python ~/hydro/backend/vision.py --once",
                 "Test the camera: one photo, print the result"],
                [".venv/bin/python backend/vision.py --stage photo.jpg", "Run the stage model on a photo file"],
                [".venv/bin/python backend/train/train_stage.py",
                 f"Retrain the stage model (about {M['minutes']} min), then restart hydro-vision"],
                [".venv/bin/python docs/guide/build_guide.py", "Rebuild this guide (PDF)"],
                ["ls -lt ~/hydro/data/logs | head", "Newest sensor CSV logs"],
                ["curl http://10.122.173.1:8080/status", "Is the camera app answering?"],
                ["sudo systemctl restart hydro-bridge", "Restart the bridge (starts a new CSV log)"]],
               [0.52, 0.48], mono_cols=(0,))
    return s + [PageBreak()]


def calibration():
    s = [H1("6. Calibration"),
         P(f"Use the dashboard's Calibration tab, the Arduino Serial Monitor (115200, Newline) or "
           f"{c('mosquitto_pub -t hydro/cmd -m &lt;command&gt;')}. All values are stored in the ESP32 "
           f"and survive reboots. Check them with {c('status')}.")]
    s += table([["Sensor", "Steps", "Expected"],
                ["EC", f"{c('enterec')} → probe in 1413 µS/cm buffer → {c('calec')} → {c('exitec')}, then "
                       f"{c('enterec')} → 12.88 mS/cm buffer → {c('calec')} → {c('exitec')}. Each save "
                       f"prints \"EC K values written to flash\". With nothing saved, the firmware uses a built-in "
                       f"1413 K of 0.79 (measured 285 mV at 23.5 °C); {c('status')} shows the K in use",
                 "~230 mV in 1413 (148–311 accepted), ~2100 mV in 12.88 (1476–2755); K 0.5–1.5"],
                ["pH", f"Probe in pH 7 buffer, wait 1–2 min → {c('ph7')} → rinse → pH 4 buffer, "
                       f"wait → {c('ph4')} ({c('phreset')} = defaults)", "Slope about 144 mV/pH (this probe)"],
                ["Tank level", f"Tank empty → {c('tankempty')} → fill to MAX → {c('tankfull')} "
                               f"({c('tankreset')} = defaults)",
                 "Empty and full at least 3 cm apart; sensor at least 2 cm above MAX"]],
               [0.15, 0.53, 0.32])
    s += [P(f"The tank-low pump stop (all pumps on both relays) only works after the tank is "
            f"calibrated. Before the first pH calibration, zero the module: short the BNC and turn "
            f"the left potentiometer until {c('po_mv')} ≈ 2500. After use, rinse the pH probe and "
            "put the cap back on with its storage solution; the glass bulb must never dry out.",
            small), H2("Lettuce target ranges")]
    s += table([["Parameter", "Target", "Set in"],
                ["EC", "1.2–1.8 mS/cm (seedlings 0.5–1.0)", f"{c('EC_MIN')} / {c('EC_MAX')}: pumps act on it"],
                ["pH", "5.5–6.5", f"{c('PH_MIN')} / {c('PH_MAX')}: pumps act on it"],
                ["Air temperature", "25–36 °C", f"{c('TEMP_MIN')} / {c('TEMP_MAX')}: reported only "
                                                f"({c('temp_ok')})"],
                ["Humidity", "50–75 % (placeholder)", "Dashboard band only"],
                ["Water level", "above 20 %", f"{c('LOW_LEVEL_PCT')}: all pumps stop below it"]],
               [0.22, 0.38, 0.4])
    s += [P(f"The dashboard bands must match the firmware values; both are listed at the top of "
            f"{c('Full_code.ino')} and in {c('frontend/index.html')}.", small), Spacer(1, 6)]

    s += [H1("7. Troubleshooting")]
    s += table([["Problem", "Fix"],
                [f"{c('/dev/esp32')} missing", f"Check {c('lsusb')}, re-plug the cable, reload the udev rules"],
                [f"No data on {c('hydro/sensors')}", f"{c('journalctl -u hydro-bridge -f')}; close the "
                                                    "Arduino Serial Monitor (only one program can use "
                                                    "the port)"],
                ["Sampling pump does not run", f"Check {c('pump_sample')} in the JSON. If it is true "
                 "but the pump is off: relay 2 IN1 on GPIO21 (D21), relay 2 VCC on 5 V, GND shared with the "
                 "ESP32, pump on the CH1 contacts (not CH2). If it is false: less than 30 s since the "
                 f"ESP32 started (start delay), tank low, or {c('sampleoff')} was sent (send {c('sampleon')})"],
                ["A relay is ON when it should be OFF", f"The module is active HIGH: set "
                 f"{c('RELAY_ACTIVE_LOW')} to {c('false')} and re-upload (it applies to both relays)"],
                ["Pumps A/B never switch", f"Relay 1 IN1/IN2 on GPIO18/19 (D18/D19); test with "
                                           f"{c('firmware/Relay_Test/')}; check the tank is not low and that 60 s "
                                           "have passed since the ESP32 started"],
                ["pH stuck (e.g. 19.71)", "Probe/BNC disconnected or not calibrated; check wiring, "
                                          "then calibrate"],
                [f"{c('ec_low: true')}", "Solution below about 0.6 mS/cm (normal for plain water)"],
                ["Water level empty", "HC-SR04 gets no echo: check wiring, the ECHO divider, and "
                                      "that it faces the water"],
                [f"{c('temp_ok: null')}", "No DHT22 reading: check the DHT22 wiring (DATA on D4) and pull-up resistor"],
                ["Dashboard shows old data", "Hard refresh (Ctrl+Shift+R). If the header says \"Live "
                 "link down\", the browser can't reach MQTT on port 9001: restart the browser or turn "
                 "off HTTPS-Only for the site. The camera photo still updates via HTTP"],
                ["Stage always empty", f"vision.py is running without ONNX Runtime: start it from "
                 f"{c('.venv')} (the service does this), and check {c('backend/models/stage.onnx')} exists"],
                ["Stage looks wrong after retraining", f"Restart {c('hydro-vision')} so it loads the new "
                 f"model; the old one is kept as {c('backend/models/stage_old.onnx')}"],
                [f"{c('hydro/vision/status')} offline", f"{c('ping 10.122.173.1')}; check the USB-C "
                 "cable and that the MaixCAM shows the Hydro Cam preview"],
                ["MaixCAM freezes / SSH hangs", "Two programs used the camera. Reboot the MaixCAM. "
                 "Never run camera scripts over SSH while its menu is running"],
                ["Health says \"No plant in view\"", "Aim the camera at the plants, check focus, "
                                                     "switch on the grow light"]], [0.3, 0.7])
    return s + [PageBreak()]


def next_steps():
    s = [H1("8. Known issues and next steps"), H2("Safety items first")]
    s += bullets([
        "<b>Pumps can dose without limit.</b> With a bad pH reading (such as 19.71) or a dry EC "
        "probe, the firmware sees \"out of target\" and runs Pumps A and B continuously. Add a "
        "maximum run time, or dose in short pulses (e.g. 2 s ON, wait 30–60 s, re-check). Until "
        "then, keep the nutrient pumps unplugged when the probes are not in solution.",
        f"<b>MQTT has no password.</b> Anyone on the WiFi can send pump or reset commands to "
        f"{c('hydro/cmd')} (the dashboard's Calibration tab uses the same topic). Add a Mosquitto "
        "password and an access list before using the dashboard from other devices.",
        f"<b>MaixCAM factory password.</b> Change it with {c('passwd')} (section 5.1).",
        "<b>Relay wiring.</b> Keep relay contacts and any mains wiring in a closed box away from "
        "water."])
    s += [H2("Roadmap")]
    s += bullets([
        "Confirm the sampling pump on relay 2 after re-flashing the firmware.",
        "Grow-light control on the spare relay channel (relay 2 IN2): pick a free GPIO, add a "
        f"schedule in the firmware and a {c('light')} field in the JSON.",
        f"Add labelled photos from the Hydro camera ({c('data/vision/')}) to the growth-stage "
        "dataset and retrain, so the model learns the real rack view, not only internet photos.",
        "DS18B20 water temperature for EC temperature compensation.",
        "RTC battery for correct offline time."])
    return s


def build():
    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=18 * mm, bottomMargin=22 * mm, title="Hydro System Guide",
                            author="Muaz",
                            subject="How the hydroponic system works and how to run it")
    story = (cover() + overview() + hardware() + how_it_works() + done() + run()
             + calibration() + next_steps())
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == "__main__":
    build()
