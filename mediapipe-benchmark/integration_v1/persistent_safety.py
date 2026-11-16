"""Fail-closed guard for durable EXT4 deployment. Never repairs or remounts."""
import json
import shutil
import threading
import time
from pathlib import Path
from .ram_safety import RamSafetyError, kernel_snapshot, mount_for

RESERVE_BYTES = 1024 ** 3


def ext4_errors(mount):
    if mount['fstype'] != 'ext4':
        raise RamSafetyError('durable_output_requires_ext4')
    device = Path(mount['source']).resolve().name
    try:
        return int((Path('/sys/fs/ext4') / device / 'errors_count').read_text())
    except (OSError, ValueError):
        raise RamSafetyError('ext4_error_counter_unavailable') from None


class PersistentGuard:
    def __init__(self, output, interval=1):
        self.output, self.interval = Path(output), interval
        self.mount = mount_for(output)
        self.cursor, self.baseline_faults = kernel_snapshot()
        if self.baseline_faults:
            raise RamSafetyError('storage_fault_in_current_boot')
        self.fault, self.latest = None, {}
        self.stop, self.thread = threading.Event(), None
        self.last_kernel_check = -float('inf')
        self.poll()
        self.raise_if_fault()

    def poll(self):
        try:
            current, root = mount_for(self.output), mount_for('/')
            if any('rw' not in m['options'] or 'shutdown' in m['options'] for m in (current, root)):
                raise RamSafetyError('filesystem_readonly_or_shutdown')
            if any(current[k] != self.mount[k] for k in ('source', 'mount', 'fstype')):
                raise RamSafetyError('output_mount_changed')
            counts = {m['source']: ext4_errors(m) for m in (current, root)}
            free = shutil.disk_usage(current['mount']).free
            faults = []
            if time.monotonic() - self.last_kernel_check >= 5:
                cursor, rows = kernel_snapshot()
                faults = [r for r in rows if r['at_boot_s'] > self.cursor]
                self.cursor = max(cursor, self.cursor)
                self.last_kernel_check = time.monotonic()
            self.latest = {'epoch_ms': time.time_ns() // 1_000_000,
                           'storage_backend': 'ext4', 'free_bytes': free,
                           'reserve_bytes': RESERVE_BYTES, 'ext4_errors': counts,
                           'root_options': root['options'], 'new_kernel_faults': faults}
            if any(counts.values()):
                raise RamSafetyError('ext4_error_counter_nonzero')
            if faults:
                raise RamSafetyError('new_kernel_storage_error')
            if free < RESERVE_BYTES:
                raise RamSafetyError('disk_reserve_exhausted')
        except RamSafetyError as error:
            self.fault = self.fault or error.code
        except (OSError, ValueError):
            self.fault = self.fault or 'storage_monitor_unavailable'
        return {**self.latest, 'safety_fault': self.fault}

    def raise_if_fault(self):
        if self.fault:
            raise RamSafetyError(self.fault)

    def start(self):
        def worker():
            try:
                with (self.output / 'storage_safety.jsonl').open('x') as stream:
                    while not self.stop.is_set():
                        stream.write(json.dumps(self.poll(), allow_nan=False) + '\n')
                        stream.flush()
                        self.stop.wait(self.interval)
            except OSError:
                self.fault = self.fault or 'storage_monitor_log_failed'
        self.thread = threading.Thread(target=worker, name='storage-safety', daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(4)
        self.poll()
        return not self.thread or not self.thread.is_alive()
