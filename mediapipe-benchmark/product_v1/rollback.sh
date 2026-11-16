#!/bin/bash
set -euo pipefail
REHAB_BASE="$HOME/.local/share/smart-rehab"
REHAB_PREVIOUS="$(cat "$REHAB_BASE/previous-release")"
case "$REHAB_PREVIOUS" in 'pre-product') ;; "$REHAB_BASE"/releases/*) test -x "$REHAB_PREVIOUS/venv/bin/python" ;; *) echo 'Invalid previous release path' >&2; exit 1 ;; esac
if [ -e "$REHAB_BASE/state/hub.sqlite3" ]; then
  "$REHAB_BASE/current/venv/bin/python" - "$REHAB_BASE/state/hub.sqlite3" <<'PY'
import json,sqlite3,sys
db=sqlite3.connect(sys.argv[1]); row=db.execute("SELECT value FROM kv WHERE key='active'").fetchone()
if row and json.loads(row[0]): raise SystemExit('Stop the active session from the app before rollback')
if db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]: raise SystemExit('Wait for the current release to flush the outbox before rollback')
PY
fi
systemctl --user stop smart-rehab-hub.service
# A command may have arrived since the preflight. Verify again before switching.
"$REHAB_BASE/current/venv/bin/python" - "$REHAB_BASE/state/hub.sqlite3" <<'PY'
import json,sqlite3,sys
from pathlib import Path
if Path(sys.argv[1]).exists():
 db=sqlite3.connect(sys.argv[1]);row=db.execute("SELECT value FROM kv WHERE key='active'").fetchone()
 if (row and json.loads(row[0])) or db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]:
  raise SystemExit('Rollback preflight changed. Restart current service and flush its session/outbox.')
PY
if [ "$REHAB_PREVIOUS" = 'pre-product' ]; then
  systemctl --user disable smart-rehab-hub.service
  "$REHAB_BASE/current/venv/bin/python" - "$HOME/.config/labwc/autostart" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); text=p.read_text(); start=text.find('# SMART-REHAB-BEGIN'); end=text.find('# SMART-REHAB-END')
if start >= 0 and end >= start: p.write_text(text[:start]+text[end+len('# SMART-REHAB-END'):])
PY
  echo 'Automatic product startup disabled. Original benchmark installation, recordings, pairing and patient data are retained.'
  exit 0
fi
ln -s "$REHAB_PREVIOUS" "$REHAB_BASE/current.rollback"
mv -Tf "$REHAB_BASE/current.rollback" "$REHAB_BASE/current"
systemctl --user start smart-rehab-hub.service
echo 'Previous release restored. Patient data and pairing have been retained.'
