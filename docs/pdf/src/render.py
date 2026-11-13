"""Render the docs/pdf/src/*.html pages to docs/pdf/*.pdf (A4).

Run:  python docs/pdf/src/render.py            (all documents)
      python docs/pdf/src/render.py 03          (only files starting with 03)
Needs: pip install playwright, then `playwright install chromium`
       (on Windows it can use Microsoft Edge instead: set HYDRO_PDF_BROWSER=msedge).
Edit the HTML, re-run, and commit both the HTML and the PDF.
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SRC = Path(__file__).resolve().parent
OUT = SRC.parent
DOCS = {
    "01_introduction.html": "01_Introduction.pdf",
    "02_esp32_pins.html": "02_ESP32_Pin_Configuration.pdf",
    "03_dataset.html": "03_Dataset.pdf",
    "04_system_diagram.html": "04_System_Diagram_and_Flowchart.pdf",
    "05_dashboard.html": "05_Dashboard_Overview.pdf",
}

only = sys.argv[1] if len(sys.argv) > 1 else ""
channel = os.environ.get("HYDRO_PDF_BROWSER") or None
with sync_playwright() as p:
    browser = p.chromium.launch(channel=channel)
    page = browser.new_page()
    for html, pdf in DOCS.items():
        if not html.startswith(only):
            continue
        page.goto((SRC / html).as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")
        page.pdf(path=str(OUT / pdf), format="A4", print_background=True,
                 margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                 prefer_css_page_size=True)
        print("wrote", OUT / pdf)
    browser.close()
