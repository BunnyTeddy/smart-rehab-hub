#!/bin/sh
# Prefer a supported 720p HDMI mode to reduce Pi composition and scanout load.
# Leave other displays/headless preview untouched if that mode is unavailable.
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    /usr/bin/timeout 1 /usr/bin/wlr-randr --output HDMI-A-1 --mode 1280x720 >/dev/null 2>&1 && exit 0
    /usr/bin/timeout 1 /usr/bin/wlr-randr --output HDMI-A-2 --mode 1280x720 >/dev/null 2>&1 && exit 0
    sleep 0.3
done
exit 0
