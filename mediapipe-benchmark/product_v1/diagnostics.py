"""Bounded, local numeric evidence for startup/detection failures; no images."""
from collections import Counter, deque
import logging
import sqlite3
from pose_algorithm.core import finite


class DetectionDiagnostics:
    def __init__(self, meta):
        self.meta = {k: meta.get(k) for k in
                     ('exercise', 'requested_side', 'algorithm_version', 'created_at')}
        self.frames = 0
        self.reasons, self.phases, self.intervals = Counter(), Counter(), Counter()
        self.last_timestamp = None
        self.max_gap_ms = 0
        self.long_gaps = 0
        self.trace = deque(maxlen=1000)
        self.started_ms = None
        self.ready_since = None
        self.longest_ready_ms = 0
        self.countdown_resets = 0
        self.last_countdown = None

    def sample(self, result, *, preparing, countdown):
        ts = result['sample_timestamp_ms']
        if not finite(ts) or (self.last_timestamp is not None and ts <= self.last_timestamp):
            return
        if self.last_timestamp is not None:
            gap = ts - self.last_timestamp
            self.max_gap_ms = max(self.max_gap_ms, gap)
            self.long_gaps += gap > 350
            bucket = 'over350' if gap > 350 else '251to350' if gap > 250 else '151to250' if gap > 150 else 'upTo150'
            self.intervals[bucket] += 1
        self.last_timestamp = ts
        self.frames += 1
        reason = 'preparing_audio' if preparing else result.get('reason', 'unknown')
        self.reasons[reason] += 1
        self.phases[result.get('phase', 'unknown')] += 1
        if not preparing and result.get('phase') == 'READY' and result.get('tracking_status') == 'tracking':
            if self.ready_since is None:
                self.ready_since = ts
            self.longest_ready_ms = max(self.longest_ready_ms, ts-self.ready_since)
        else:
            self.ready_since = None
        working = result.get('workload_phase') == 'working'
        if working and self.started_ms is None:
            self.started_ms = ts
        if self.last_countdown is not None and countdown is None and not working:
            self.countdown_resets += 1
        self.last_countdown = countdown
        self.trace.append({k: result[k] for k in (
            'sample_timestamp_ms', 'angle', 'raw_angle', 'angle_left', 'angle_right',
            'visibility', 'tracking_status', 'phase', 'reason', 'workload_phase') if k in result}
                         | {'preparing': preparing, 'countdown': countdown})

    def report(self):
        return dict(**self.meta, frames=self.frames, reasons=dict(self.reasons),
                    phases=dict(self.phases), frame_intervals=dict(self.intervals),
                    max_gap_ms=self.max_gap_ms, gaps_over_350_ms=self.long_gaps,
                    started_ms=self.started_ms, longest_ready_ms=self.longest_ready_ms,
                    countdown_resets=self.countdown_resets, trace=list(self.trace))

    def save(self, store):
        try:
            old = store.get('detection_diagnostics', [])
            store.set('detection_diagnostics', [*old[-11:], self.report()])
        except (sqlite3.Error, OSError):
            # Diagnostic retention must not mask camera cleanup or prevent the
            # existing durable session-finalization path from running.
            logging.getLogger('smart-rehab').warning('Detection diagnostics could not be saved')
