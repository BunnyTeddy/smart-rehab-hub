"""Fail-closed RAM storage guard; never repairs, remounts or modifies the SD card."""
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

MIB = 1024 * 1024
RESERVE_BYTES = 256 * MIB
MAX_ARCHIVE_BYTES = 500 * MIB
FAULT_PATTERN = re.compile(r'EXT4-fs (?:error|.*shutdown)|I/O error|Buffer I/O|mmc.*(?:timeout|error)|Remounting filesystem read-only', re.I)


class RamSafetyError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def mount_for(path, text=None):
    resolved = Path(path).resolve()
    text = Path('/proc/mounts').read_text() if text is None else text
    candidates = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        point = Path(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), fields[1])).resolve()
        if resolved == point or point in resolved.parents:
            candidates.append((len(point.parts), {'source': fields[0], 'mount': str(point),
                                                  'fstype': fields[2], 'options': fields[3].split(',')}))
    if not candidates:
        raise RamSafetyError('ram_mount_unavailable')
    return max(candidates, key=lambda row: row[0])[1]


def require_tmpfs(path):
    mount = mount_for(path)
    if mount['fstype'] != 'tmpfs' or 'rw' not in mount['options']:
        raise RamSafetyError('output_must_be_writable_tmpfs')
    return mount


def mem_available(text=None):
    text = Path('/proc/meminfo').read_text() if text is None else text
    match = re.search(r'^MemAvailable:\s+(\d+) kB$', text, re.M)
    if not match:
        raise RamSafetyError('mem_available_unavailable')
    return int(match[1]) * 1024


def kernel_snapshot(text=None):
    if text is None:
        try:
            text = subprocess.check_output(['dmesg', '--color=never', '--time-format=raw'],
                                           text=True, stderr=subprocess.DEVNULL, timeout=2)
        except (OSError, subprocess.SubprocessError):
            raise RamSafetyError('kernel_monitor_unavailable') from None
    cursor, faults = -1., []
    for line in text.splitlines():
        match = re.search(r'\[\s*(\d+(?:\.\d+)?)\]', line)
        if match:
            at = float(match[1]); cursor = max(cursor, at)
            if FAULT_PATTERN.search(line):
                faults.append({'at_boot_s': at, 'message': line})
    if cursor < 0:
        raise RamSafetyError('kernel_timestamps_unavailable')
    return cursor, faults


def capacity_estimate(reference_bytes, reference_seconds, duration, tmpfs_free, memory_free):
    if reference_seconds < 25 or reference_bytes <= 0 or duration <= 0:
        raise RamSafetyError('invalid_capacity_reference')
    # The short clip includes warm-up recording; keep a further 10% margin.
    raw = int(reference_bytes / reference_seconds * duration * 1.10) + 10 * MIB
    archive = int(raw * 1.02) + MIB  # conservative gzip overhead, not a promised size
    required = raw + archive + RESERVE_BYTES
    reasons = []
    if archive > MAX_ARCHIVE_BYTES: reasons.append('archive_limit')
    if min(tmpfs_free, memory_free) < required: reasons.append('insufficient_ram_capacity')
    return {'allowed': not reasons, 'reasons': reasons, 'reference_bytes': reference_bytes,
            'reference_seconds': reference_seconds, 'duration_s': duration,
            'projected_raw_bytes': raw, 'projected_archive_bytes': archive,
            'required_available_bytes': required, 'tmpfs_free_bytes': tmpfs_free,
            'memory_available_bytes': memory_free, 'reserve_bytes': RESERVE_BYTES,
            'archive_limit_bytes': MAX_ARCHIVE_BYTES}


def estimate_from_run(reference, duration, output):
    reference = Path(reference)
    summary = json.loads((reference/'summary.json').read_text())
    if summary.get('source') != 'camera' or summary.get('status') != 'completed' or summary.get('error'):
        raise RamSafetyError('capacity_reference_must_be_completed_camera')
    size = sum(p.stat().st_size for p in reference.rglob('*') if p.is_file())
    parent = Path(output).resolve()
    while not parent.exists(): parent = parent.parent
    return capacity_estimate(size, summary['elapsed_s'], duration,
                             shutil.disk_usage(parent).free, mem_available())


class RamGuard:
    """Separate 1 Hz safety worker; old EXT4 errors remain explicitly unverified."""
    def __init__(self, output, interval=1):
        self.output = Path(output)
        self.mount = require_tmpfs(output)
        self.cursor, self.baseline_faults = kernel_snapshot()
        self.last_kernel_check = time.monotonic()
        self.interval = interval
        self.fault = None
        self.latest = {}
        self.stop = threading.Event()
        self.thread = None
        self.poll()
        self.raise_if_fault()

    def poll(self):
        try:
            current_mount = require_tmpfs(self.output)
            root = mount_for('/')
            free = shutil.disk_usage(self.mount['mount']).free
            memory = mem_available()
            new_faults = []
            if time.monotonic() - self.last_kernel_check >= 5:
                cursor, faults = kernel_snapshot()
                new_faults = [r for r in faults if r['at_boot_s'] > self.cursor]
                self.cursor = max(cursor, self.cursor)
                self.last_kernel_check = time.monotonic()
            size = sum(p.stat().st_size for p in self.output.rglob('*') if p.is_file()) if self.output.exists() else 0
            self.latest = {'epoch_ms': time.time_ns()//1_000_000, 'tmpfs_free_bytes': free,
                           'memory_available_bytes': memory, 'run_bytes': size,
                           'root_options': root['options'], 'tmpfs_mount': current_mount['mount'],
                           'new_kernel_faults': new_faults, 'old_ext4_errors_remain_unrepaired': bool(self.baseline_faults)}
            if 'rw' not in root['options'] or 'shutdown' in root['options']:
                raise RamSafetyError('root_filesystem_error_state')
            if min(free, memory) < RESERVE_BYTES:
                raise RamSafetyError('ram_reserve_exhausted')
            if size * 1.02 + MIB > MAX_ARCHIVE_BYTES:
                raise RamSafetyError('archive_capacity_limit')
            if new_faults:
                raise RamSafetyError('new_kernel_storage_error')
        except RamSafetyError as error:
            self.fault = self.fault or error.code
        except (OSError, ValueError):
            self.fault = self.fault or 'ram_monitor_unavailable'
        return {**self.latest, 'safety_fault': self.fault}

    def raise_if_fault(self):
        if self.fault:
            raise RamSafetyError(self.fault)

    def start(self):
        def worker():
            try:
                with (self.output/'ram_safety.jsonl').open('x') as stream:
                    while not self.stop.is_set():
                        stream.write(json.dumps(self.poll(), allow_nan=False)+'\n'); stream.flush()
                        self.stop.wait(self.interval)
            except OSError:
                self.fault = self.fault or 'ram_monitor_log_failed'
        self.thread = threading.Thread(target=worker, name='ram-safety-telemetry', daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread: self.thread.join(4)
        return not self.thread or not self.thread.is_alive()
