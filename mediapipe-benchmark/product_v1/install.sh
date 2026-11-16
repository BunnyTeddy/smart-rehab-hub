#!/bin/bash
# One-time technician installation on this Raspberry Pi. Daily users need no shell.
set -euo pipefail
REHAB_PACKAGE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REHAB_VERSION="1.2.1-rc3"
REHAB_BASE="$HOME/.local/share/smart-rehab"
REHAB_RELEASE="$REHAB_BASE/releases/$REHAB_VERSION"
REHAB_BASELINE="$HOME/mediapipe-benchmark"
if [ -d "$REHAB_PACKAGE_DIR/device-assets/runtime" ]; then
  REHAB_BASELINE="$REHAB_PACKAGE_DIR/device-assets"
fi
mkdir -p "$REHAB_BASE/releases" "$REHAB_BASE/state" "$REHAB_BASE/audio" "$HOME/.config/smart-rehab" "$HOME/.config/systemd/user" "$HOME/.config/labwc"
chmod 700 "$REHAB_BASE/state" "$HOME/.config/smart-rehab"
if [ -e "$REHAB_RELEASE/.installed" ]; then
  echo 'This release already exists. Choose a new version; existing releases are never overwritten.' >&2
  exit 1
fi
mkdir -p "$REHAB_RELEASE"
cp -a "$REHAB_PACKAGE_DIR/product_v1" "$REHAB_PACKAGE_DIR/pose_algorithm" "$REHAB_PACKAGE_DIR/integration_v1" "$REHAB_RELEASE/"
cp -a "$REHAB_BASELINE/runtime" "$REHAB_RELEASE/"
mkdir -p "$REHAB_RELEASE/models"
cp "$REHAB_BASELINE/models/pose_landmarker_lite.task" "$REHAB_RELEASE/models/"
cp "$REHAB_BASELINE/requirements.lock.txt" "$REHAB_RELEASE/baseline-requirements.lock.txt"
"$REHAB_RELEASE/runtime/python/bin/python3.12" -m venv "$REHAB_RELEASE/venv"
"$REHAB_RELEASE/venv/bin/pip" install --no-index --find-links "$REHAB_BASELINE/wheelhouse" -r "$REHAB_RELEASE/baseline-requirements.lock.txt"
"$REHAB_RELEASE/venv/bin/pip" install --no-index --find-links "$REHAB_PACKAGE_DIR/product_v1/wheels" --require-hashes -r "$REHAB_PACKAGE_DIR/product_v1/requirements.lock.txt"
"$REHAB_RELEASE/venv/bin/pip" check
PYTHONPATH="$REHAB_RELEASE" "$REHAB_RELEASE/venv/bin/python" -m product_v1.voice_pack "$REHAB_RELEASE/product_v1/audio"
PYTHONPATH="$REHAB_RELEASE" "$REHAB_RELEASE/venv/bin/python" -m unittest discover -s "$REHAB_RELEASE/product_v1/tests" -q
if [ -e "$REHAB_BASE/state/hub.sqlite3" ]; then
  "$REHAB_RELEASE/venv/bin/python" - "$REHAB_BASE/state/hub.sqlite3" <<'PY'
import json, sqlite3, sys
db = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True)
row = db.execute("SELECT value FROM kv WHERE key='active'").fetchone()
if row and json.loads(row[0]): raise SystemExit('Stop the active session from the app before updating')
PY
fi
systemctl --user stop smart-rehab-hub.service 2>/dev/null || true
# Recheck after stopping to close a start/update race; never strand a new active session.
"$REHAB_RELEASE/venv/bin/python" - "$REHAB_BASE/state/hub.sqlite3" <<'PY'
import json, sqlite3, sys
from pathlib import Path
p=Path(sys.argv[1])
if p.exists():
 db=sqlite3.connect(str(p)); row=db.execute("SELECT value FROM kv WHERE key='active'").fetchone()
 if row and json.loads(row[0]): raise SystemExit('Active session detected. Keep current release and restart its service.')
PY
touch "$REHAB_RELEASE/.installed"
if [ -L "$REHAB_BASE/current" ]; then
  readlink "$REHAB_BASE/current" > "$REHAB_BASE/previous-release"
else
  echo 'pre-product' > "$REHAB_BASE/previous-release"
fi
ln -s "$REHAB_RELEASE" "$REHAB_BASE/current.next"
mv -Tf "$REHAB_BASE/current.next" "$REHAB_BASE/current"
cat > "$HOME/.config/systemd/user/smart-rehab-hub.service" <<'UNIT'
[Unit]
Description=SMART REHAB hub: BLE, cloud and HDMI
After=graphical-session-pre.target
StartLimitIntervalSec=120
StartLimitBurst=10

[Service]
Type=simple
WorkingDirectory=%h/.local/share/smart-rehab/current
ExecStart=%h/.local/share/smart-rehab/current/venv/bin/python -B -m product_v1.hub
Environment=DISPLAY=:0
Environment=WAYLAND_DISPLAY=wayland-0
Environment=QT_QPA_PLATFORM=xcb
Environment=PYTHONUNBUFFERED=1
UMask=0077
Restart=on-failure
RestartSec=5
TimeoutStopSec=25
NoNewPrivileges=true

[Install]
WantedBy=default.target
UNIT
REHAB_AUTOSTART="$HOME/.config/labwc/autostart"
if [ ! -e "$REHAB_AUTOSTART" ]; then
  touch "$REHAB_BASE/labwc-originally-absent"
  cp /etc/xdg/labwc/autostart "$REHAB_AUTOSTART"
elif ! grep -q 'SMART-REHAB-BEGIN' "$REHAB_AUTOSTART"; then
  cp "$REHAB_AUTOSTART" "$REHAB_BASE/labwc-autostart-before-$REHAB_VERSION"
fi
if ! grep -q 'SMART-REHAB-BEGIN' "$REHAB_AUTOSTART"; then
  cat >> "$REHAB_AUTOSTART" <<'AUTOSTART'

# SMART-REHAB-BEGIN
systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XDG_RUNTIME_DIR
systemctl --user start smart-rehab-hub.service
# SMART-REHAB-END
AUTOSTART
fi
systemctl --user daemon-reload
systemctl --user enable smart-rehab-hub.service
echo 'Installed release. Run install-system.sh once as root, then start smart-rehab-hub.service.'
