#!/bin/bash
set -euo pipefail
REHAB_USER="${1:?pass the dedicated hub user}"
id "$REHAB_USER" >/dev/null
if [ "$(id -u)" != 0 ]; then echo 'This one-time system setup requires root.' >&2; exit 1; fi
REHAB_RFKILL="$(command -v rfkill || true)"
if [ -z "$REHAB_RFKILL" ]; then
  apt-get update
  apt-get install -y rfkill
  REHAB_RFKILL="$(command -v rfkill)"
fi
"$REHAB_RFKILL" unblock bluetooth
systemctl enable --now bluetooth.service
usermod -aG bluetooth,video,audio "$REHAB_USER"
# Narrow permissions: only this local hub account may change Wi-Fi or advertise BLE.
cat > /etc/polkit-1/rules.d/49-smart-rehab-network.rules <<EOF
polkit.addRule(function(action, subject) {
    if (subject.user === "$REHAB_USER" &&
        (action.id === "org.freedesktop.NetworkManager.network-control" ||
         action.id === "org.freedesktop.NetworkManager.settings.modify.system" ||
         action.id === "org.freedesktop.NetworkManager.wifi.scan" ||
         action.id === "org.freedesktop.NetworkManager.enable-disable-wifi")) {
        return polkit.Result.YES;
    }
});
EOF
cat > /etc/dbus-1/system.d/smart-rehab-bluetooth.conf <<EOF
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig><policy user="$REHAB_USER"><allow send_destination="org.bluez"/></policy></busconfig>
EOF
systemctl reload dbus.service
echo 'Bluetooth unblocked and dedicated hub permissions installed.'
