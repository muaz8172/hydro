"""
Hydro Cam - MaixPy app for the Sipeed MaixCAM (runs ON the camera, not the Pi)
- Shows a live preview on the MaixCAM screen (for aiming the camera at the lettuce)
- Serves a fresh photo to the Pi over the USB network link:
    GET http://10.122.173.1:8080/snap.jpg   -> JPEG
    GET http://10.122.173.1:8080/status     -> JSON
- Only answers the Pi's USB subnets (10.122.x.x), not the WiFi network
The Pi side is vision.py (fetches a photo every 15 min, checks leaf colour, publishes to MQTT).
"""

import json
import select
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from maix import app, camera, display, image, time

WIDTH, HEIGHT = 640, 480        # larger sizes can run out of camera memory
PORT          = 8080
JPEG_QUALITY  = 90
ALLOWED_NET   = "10.122."       # USB network to the Pi (usb0/usb1)

cam  = camera.Camera(WIDTH, HEIGHT)
disp = display.Display()
start_ms  = time.ticks_ms()
snaps     = 0
last_snap = "never"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global snaps, last_snap
        if not self.client_address[0].startswith(ALLOWED_NET):
            self.send_error(403)
            return
        if self.path.startswith("/snap.jpg"):
            img = cam.read()
            for _ in range(3):              # drop buffered frames, get a current one
                img = cam.read()
            body = bytes(img.to_jpeg(JPEG_QUALITY).to_bytes())
            snaps += 1
            last_snap = datetime.now().strftime("%H:%M:%S")
            self.reply(200, "image/jpeg", body)
        elif self.path.startswith("/status"):
            body = json.dumps({"ok": True, "width": WIDTH, "height": HEIGHT, "snaps": snaps,
                               "uptime_s": (time.ticks_ms() - start_ms) // 1000}).encode()
            self.reply(200, "application/json", body)
        else:
            self.send_error(404)

    def reply(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[http]", self.client_address[0], fmt % args)


server = HTTPServer(("0.0.0.0", PORT), Handler)
server.timeout = 5                  # a stuck client can't freeze the preview for long
print(f"[hydro_cam] serving on port {PORT}")

while not app.need_exit():
    # serve any waiting request without blocking the preview
    if select.select([server.socket], [], [], 0)[0]:
        server.handle_request()

    img = cam.read()
    img.draw_string(6, 6, f"Hydro Cam  :{PORT}  snaps {snaps}  last {last_snap}",
                    image.COLOR_WHITE, 1.2)
    disp.show(img)

server.server_close()
