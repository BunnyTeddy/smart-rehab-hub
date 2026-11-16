"""Six additional detectors reuse v2 filtering and cycle FSM without changing baseline files."""
import json
import math
from pathlib import Path
from pose_algorithm.core import PoseAlgorithm, TRIPLES, angle_2d, finite
from .catalog import LEGACY_EXERCISES, EXERCISE_CATALOG

PRESETS = json.loads(Path(__file__).with_name('exercise_presets.json').read_text())
PRODUCT_PRESETS = json.loads(Path(__file__).with_name('detection_presets.json').read_text())
SHOULDERS = {'left': (23, 11, 13), 'right': (24, 12, 14)}


def visible_points(landmarks, indices, width, height, visibility):
    """Validate only landmarks actually used by a measurement/guard."""
    if not finite(width) or not finite(height) or min(width, height) <= 0:
        return None, 'invalid_dimensions'
    if not isinstance(landmarks, (list, tuple)) or len(landmarks) != 33:
        return None, 'missing_pose'
    quality = 1.0
    for i in indices:
        p = landmarks[i]
        if not isinstance(p, (list, tuple)) or len(p) < 4 or not all(finite(n) for n in p[:4]):
            return None, f'landmark_{i}_invalid'
        if not 0 <= p[3] <= 1:
            return None, f'landmark_{i}_invalid'
        if not all(0 <= n <= 1 for n in p[:2]):
            return None, f'landmark_{i}_out_of_frame'
        if p[3] < visibility:
            return None, f'landmark_{i}_low_visibility'
        quality = min(quality, p[3])
    return quality, 'ok'


def measured_angle(landmarks, triple, width, height, visibility):
    quality, reason = visible_points(landmarks, triple, width, height, visibility)
    if quality is None:
        return None, None, reason
    return angle_2d(landmarks, triple, width, height, visibility)


class MovementAlgorithm(PoseAlgorithm):
    def __init__(self, exercise, *, config=None, **kwargs):
        super().__init__(exercise, config=config or PRESETS, **kwargs)
        self.secondary_angle = None
        self.target_guard = 'ok'
        self.observed = {}

    def _zone(self, value):
        zone = super()._zone(value)
        if self.exercise == 'sit_to_stand':
            if zone == 'start' and self.secondary_angle > self.preset['secondary_start_max']:
                return 'middle'
            if zone == 'target' and self.secondary_angle < self.preset['secondary_target_min']:
                return 'middle'
        # Posture checks qualify the target, not the entire stream. A visible
        # joint is still tracked while moving between endpoints. The v2 FSM
        # retains the cycle; it can only confirm a target with valid geometry.
        if zone == 'target' and self.target_guard != 'ok':
            return 'middle'
        return zone

    def _measure(self, landmarks, width, height, side):
        triple = SHOULDERS[side] if self.preset['joint'] == 'shoulder' else TRIPLES[self.preset['joint']][side]
        primary = measured_angle(landmarks, triple, width, height, self.config['tracking_visibility'])
        value, quality, reason = primary
        self.observed[side] = value
        if value is None:
            return value, quality, reason, None
        # Missing required geometry still discards the cycle, exactly as v2.
        # A posture outside a target guard is not a missing landmark.
        secondary = None
        guard = 'ok'
        for joint in ('hip', 'knee', 'elbow'):
            if joint == self.preset.get('secondary') or joint+'_min' in self.preset or joint+'_max' in self.preset:
                a, q, why = measured_angle(landmarks, TRIPLES[joint][side], width, height, self.config['tracking_visibility'])
                if a is None:
                    return None, q, why, None
                quality = min(quality, q)
                if joint == self.preset.get('secondary'):
                    secondary = a
                if a < self.preset.get(joint+'_min', 0) or a > self.preset.get(joint+'_max', 180):
                    guard = joint + '_guard'
        if 'support_knee_min' in self.preset:
            opposite = 'right' if side == 'left' else 'left'
            a, q, why = measured_angle(landmarks, TRIPLES['knee'][opposite], width, height, self.config['tracking_visibility'])
            if a is None:
                return None, q, why, secondary
            if a < self.preset['support_knee_min']:
                guard = 'support_leg_guard'
            quality = min(quality, q)
        if 'trunk_max' in self.preset:
            # Trunk tilt uses shoulder + hip only; requiring a knee here rejects upper-body crops.
            pair = (11, 23) if side == 'left' else (12, 24)
            q, why = visible_points(landmarks, pair, width, height, self.config['tracking_visibility'])
            if q is None:
                return None, q, why, secondary
            quality = min(quality, q)
            shoulder, hip = landmarks[11 if side == 'left' else 12], landmarks[23 if side == 'left' else 24]
            dx, dy = (shoulder[0]-hip[0])*width, (hip[1]-shoulder[1])*height
            if dy <= 0 or math.degrees(math.atan2(abs(dx), dy)) > self.preset['trunk_max']:
                guard = 'trunk_guard'
        if 'outward' in self.preset:
            # Front-view movement must go away from the body's midline; crossing inward is rejected.
            own, opposite = (11, 12) if side == 'left' else (12, 11)
            if self.preset['outward'] == 'leg':
                own, opposite = (23, 24) if side == 'left' else (24, 23)
            end = (13 if side == 'left' else 14) if self.preset['outward'] == 'arm' else (25 if side == 'left' else 26)
            q, why = visible_points(landmarks, (own, opposite, end), width, height, self.config['tracking_visibility'])
            if q is None:
                return None, q, why, secondary
            quality = min(quality, q)
            direction = landmarks[own][0]-landmarks[opposite][0]
            # Too narrow a shoulder/hip projection cannot establish the required frontal view.
            if abs(direction)*width < 8:
                guard = 'camera_view_guard'
            elif (landmarks[end][0]-landmarks[own][0])*direction < -0.002:
                guard = 'inward_movement'
        return value, quality, guard, secondary

    def update(self, landmarks, width, height, timestamp_ms):
        if not finite(timestamp_ms) or timestamp_ms < 0 or (self.last_timestamp is not None and timestamp_ms <= self.last_timestamp):
            return None
        gap = self.last_timestamp is not None and timestamp_ms-self.last_timestamp > self.config['max_gap_ms']
        self.last_timestamp = timestamp_ms
        self.sequence += 1
        if gap:
            self._discard_cycle()
            if self.side is None:
                self.selection_started = None
                self.selection_samples = {'left': [], 'right': []}
        measured = {side: self._measure(landmarks, width, height, side) for side in ('left', 'right')}
        if self.side is None:
            self._select(timestamp_ms, {side: v[:3] for side, v in measured.items()})
        raw, quality, reason, secondary = measured[self.side] if self.side else (None, None, 'selecting_side', None)
        if self.side is None and all(v[0] is None for v in measured.values()):
            # Surface a concrete failure instead of an indefinite "selecting side" message.
            reason = measured['left'][2]
        self.secondary_angle = secondary
        self.target_guard = reason
        event = None
        if raw is None:
            self._discard_cycle()
            status = 'selecting_side' if self.side is None else 'lost'
        else:
            if self.filtered is None:
                self.filtered = raw
            else:
                alpha = -math.expm1(-(timestamp_ms-self.last_valid)/self.config['ema_tau_ms'])
                self.filtered += alpha*(raw-self.filtered)
            event = self._count(timestamp_ms, self.filtered, raw)
            self.last_valid = timestamp_ms
            status = 'tracking'
            if gap:
                reason = 'gap_reset'
            elif super()._zone(self.filtered) != 'target':
                # No coaching about target posture while simply holding rest.
                reason = 'ok'
        return dict(schema_version=2, algorithm_version=self.config['version'], session_id=self.session_id,
                    exercise=self.exercise, sequence=self.sequence, sample_timestamp_ms=timestamp_ms,
                    side=self.side, joint=self.preset['joint'], angle=self.filtered if raw is not None else None,
                    raw_angle=self.observed.get(self.side), visibility=quality, tracking_status=status, reason=reason,
                    form_status='not_evaluated', reps=self.reps, phase=self.phase, rep_event=event)


def create_algorithm(exercise, *, side='auto', session_id='offline'):
    if exercise not in EXERCISE_CATALOG:
        raise ValueError('exercise_not_available')
    if side == 'both':
        from .bilateral import BilateralAlgorithm
        return BilateralAlgorithm(exercise, session_id=session_id)
    cls = PoseAlgorithm if exercise in LEGACY_EXERCISES else MovementAlgorithm
    return cls(exercise, side=side, session_id=session_id, config=PRODUCT_PRESETS)


def algorithm_version(exercise, side):
    version = EXERCISE_CATALOG[exercise]['algorithm_version']
    return version + '+bilateral1' if side == 'both' else version
