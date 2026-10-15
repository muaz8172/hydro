#!/bin/bash
# Install the HDMI dashboard kiosk for the logged-in desktop user (no sudo needed).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$DIR/kiosk-run.sh" "$DIR/hydro-kiosk"

mkdir -p ~/.config/systemd/user ~/.config/autostart ~/.local/bin
ln -sf "$DIR/hydro-kiosk.service" ~/.config/systemd/user/hydro-kiosk.service
ln -sf "$DIR/hydro-kiosk.desktop" ~/.config/autostart/hydro-kiosk.desktop
ln -sf "$DIR/hydro-kiosk" ~/.local/bin/hydro-kiosk

# Stop update / Ubuntu Pro popups from appearing over the dashboard.
for app in update-notifier ubuntu-advantage-notification; do
    printf '[Desktop Entry]\nType=Application\nName=%s\nHidden=true\n' "$app" > ~/.config/autostart/$app.desktop
done

# The Pi power-supply popup (pemmican) waits for a mouse click; with no mouse it
# never finishes and blocks graphical-session.target, which stalls Firefox for minutes.
mkdir -p ~/.config/pemmican
touch ~/.config/pemmican/max_current.inhibit ~/.config/pemmican/brownout.inhibit

systemctl --user daemon-reload
echo "Installed. Starting kiosk..."
systemctl --user start hydro-kiosk.service
