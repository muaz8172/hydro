#!/bin/bash
# Show the dashboard full screen on the HDMI monitor (run by hydro-kiosk.service).
# Keeps the screen awake, waits for the dashboard, then runs Firefox in kiosk mode.
URL="http://localhost:8000/"
PROFILE="$HOME/snap/firefox/common/hydro-kiosk"

# Screen on 24/7: no blanking, no lock, no sleep, no notification banners.
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false
gsettings set org.gnome.desktop.screensaver idle-activation-enabled false
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
gsettings set org.gnome.settings-daemon.plugins.power idle-dim false
gsettings set org.gnome.desktop.notifications show-banners false

# Own Firefox profile so no restore / welcome / update prompts get stuck on screen.
mkdir -p "$PROFILE"
cat > "$PROFILE/user.js" <<'EOF'
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.startup.upgradeDialog.enabled", false);
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.translations.automaticallyPopup", false);
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("datareporting.policy.firstRunURL", "");
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("app.update.auto", false);
user_pref("layout.css.devPixelsPerPx", "-1.0");
EOF

# Wait (up to 2 min) for the dashboard server so the page doesn't load blank.
for _ in $(seq 60); do
    curl -fs -o /dev/null "$URL" && break
    sleep 2
done

exec /snap/bin/firefox --kiosk --no-remote --profile "$PROFILE" "$URL"
