"""Small device probes, independent of demonstration and recording tools."""
import subprocess
from pathlib import Path


def resources():
    try:
        temperature = float(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
    except (OSError, ValueError):
        temperature = None
    try:
        throttled = subprocess.check_output(['vcgencmd', 'get_throttled'], timeout=2,
                                            stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.SubprocessError):
        throttled = 'unknown'
    return {'temperature_c': temperature, 'throttled': throttled}
