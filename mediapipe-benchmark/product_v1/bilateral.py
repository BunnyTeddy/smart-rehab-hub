"""One shared cycle: both sides must occupy start/target zones together.

Individual counters are never added or paired after the fact. Missing either
side cancels the shared partial cycle. Legacy single-side algorithms stay intact.
"""
from pose_algorithm.core import PoseAlgorithm, finite
from .catalog import EXERCISE_CATALOG, LEGACY_EXERCISES
from .movement import MovementAlgorithm, PRODUCT_PRESETS, algorithm_version


class BilateralAlgorithm(PoseAlgorithm):
    def __init__(self, exercise, *, session_id='offline'):
        if not EXERCISE_CATALOG.get(exercise, {}).get('bilateral', False):
            raise ValueError('bilateral_not_supported')
        config = PRODUCT_PRESETS
        super().__init__(exercise, side='left', session_id=session_id, config=config)
        cls = PoseAlgorithm if exercise in LEGACY_EXERCISES else MovementAlgorithm
        self.children = {s: cls(exercise, side=s, session_id=session_id, config=config) for s in ('left', 'right')}
        self.side = self.requested_side = 'both'

    def _discard_cycle(self):
        super()._discard_cycle()
        self.ranges = {}
        self.combined_zone = 'middle'
        for child in getattr(self, 'children', {}).values():
            child._discard_cycle()

    def _zone(self, _):
        return self.combined_zone

    def update(self, landmarks, width, height, timestamp_ms):
        if not finite(timestamp_ms) or timestamp_ms < 0 or (self.last_timestamp is not None and timestamp_ms <= self.last_timestamp):
            return None
        gap = self.last_timestamp is not None and timestamp_ms - self.last_timestamp > self.config['max_gap_ms']
        if gap:
            self._discard_cycle()
        self.last_timestamp = timestamp_ms
        self.sequence += 1
        results = {s: child.update(landmarks, width, height, timestamp_ms) for s, child in self.children.items()}
        valid = all(r['tracking_status'] == 'tracking' for r in results.values())
        event, reason, raw = None, 'ok', None
        qualities = [r['visibility'] for r in results.values() if finite(r.get('visibility'))]
        angles = {s: r.get('angle') if r['tracking_status'] == 'tracking' else r.get('raw_angle') for s, r in results.items()}
        if not valid:
            failed = next(s for s, r in results.items() if r['tracking_status'] != 'tracking')
            reason = failed + ':' + results[failed]['reason']
            self._discard_cycle()
        else:
            zones = [self.children[s]._zone(r['angle']) for s, r in results.items()]
            self.combined_zone = zones[0] if zones[0] == zones[1] else 'middle'
            self.filtered = sum(r['angle'] for r in results.values()) / 2
            raw = sum(r['raw_angle'] for r in results.values()) / 2
            before = self.phase
            event = self._count(timestamp_ms, self.filtered, raw)
            if before != 'WAIT_START' and (before != 'READY' or self.phase != 'READY'):
                for s, r in results.items():
                    lo, hi = self.ranges.get(s, (r['raw_angle'], r['raw_angle']))
                    self.ranges[s] = min(lo, r['raw_angle']), max(hi, r['raw_angle'])
            if event:
                for s, (lo, hi) in self.ranges.items():
                    event.update({s+'_min_angle_deg': lo, s+'_max_angle_deg': hi, 'rom_'+s+'_deg': hi-lo})
            if self.phase == 'READY':
                self.ranges = {}
            self.last_valid = timestamp_ms
            if gap:
                reason = 'gap_reset'
            elif zones[0] != zones[1]:
                reason = 'both_not_in_same_zone'
        return dict(schema_version=2, algorithm_version=algorithm_version(self.exercise, 'both'),
                    session_id=self.session_id, exercise=self.exercise, sequence=self.sequence,
                    sample_timestamp_ms=timestamp_ms, side='both', joint=self.preset['joint'],
                    angle=self.filtered if valid else None, raw_angle=raw,
                    angle_left=angles['left'], angle_right=angles['right'],
                    visibility=min(qualities) if qualities else None,
                    tracking_status='tracking' if valid else 'lost', reason=reason,
                    form_status='not_evaluated', reps=self.reps, phase=self.phase, rep_event=event)
