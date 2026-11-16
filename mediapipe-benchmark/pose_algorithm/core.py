"""Pure processing: no camera, model runtime, audio, clock or network imports.

Landmarks are 33 sequences [normalized_x, normalized_y, z, visibility].
Time is source/monotonic sample time in milliseconds, never transport time.
An invalid sample discards a partial cycle, not completed repetitions.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

PRESETS = json.loads(Path(__file__).with_name("presets.json").read_text())
PRESET_VERSION = PRESETS["version"]
TRIPLES = {
    "knee": {"left": (23, 25, 27), "right": (24, 26, 28)},
    "elbow": {"left": (11, 13, 15), "right": (12, 14, 16)},
    "hip": {"left": (11, 23, 25), "right": (12, 24, 26)},
}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def angle_2d(points, triple, width, height, min_visibility=0.5):
    """Return (angle or None, minimum visibility, reason). z is not mixed into 2D."""
    if not finite(width) or not finite(height) or width <= 0 or height <= 0:
        return None, None, "invalid_dimensions"
    if not isinstance(points, (list, tuple)) or len(points) != 33:
        return None, None, "missing_pose"
    selected = [points[i] for i in triple]
    if any(not isinstance(p, (list, tuple)) or len(p) < 4 or
           not all(finite(v) for v in p[:4]) for p in selected):
        return None, None, "invalid_landmark"
    visibility = min(p[3] for p in selected)
    if any(not 0 <= p[3] <= 1 for p in selected):
        return None, None, "invalid_visibility"
    if any(not 0 <= v <= 1 for p in selected for v in p[:2]):
        return None, visibility, "out_of_frame"
    if visibility < min_visibility:
        return None, visibility, "low_visibility"
    a, b, c = selected
    u = ((a[0] - b[0]) * width, (a[1] - b[1]) * height)
    v = ((c[0] - b[0]) * width, (c[1] - b[1]) * height)
    nu, nv = math.hypot(*u), math.hypot(*v)
    if min(nu, nv) < 1e-6:
        return None, visibility, "degenerate_segment"
    cosine = max(-1.0, min(1.0, (u[0]*v[0] + u[1]*v[1]) / (nu*nv)))
    return math.degrees(math.acos(cosine)), visibility, "ok"


class PoseAlgorithm:
    def __init__(self, exercise, *, side="auto", session_id="offline", config=None):
        self.config = json.loads(json.dumps(config or PRESETS))
        if exercise not in self.config["exercises"]:
            raise ValueError(f"Unsupported exercise: {exercise}")
        if side not in ("auto", "left", "right") or not session_id:
            raise ValueError("Invalid side or session id")
        self.exercise, self.requested_side, self.session_id = exercise, side, session_id
        self.preset = self.config["exercises"][exercise]
        if self.preset["start"] == self.preset["target"]:
            raise ValueError("Start and target zones must be distinct")
        self.reset()

    def reset(self):
        self.side = None if self.requested_side == "auto" else self.requested_side
        self.sequence = 0
        self.reps = 0
        self.last_timestamp = None
        self.selection_started = None
        self.selection_samples = {"left": [], "right": []}
        self._discard_cycle()

    def _discard_cycle(self):
        self.phase = "WAIT_START"
        self.filtered = None
        self.last_valid = None
        self.dwell_zone = None
        self.dwell_started = None
        self.cycle_start = None
        self.target_time = None
        self.minimum = None
        self.maximum = None

    def _select(self, timestamp, sides):
        if self.selection_started is None:
            self.selection_started = timestamp
        for side, (value, quality, _) in sides.items():
            samples = self.selection_samples[side]
            samples.append((timestamp, quality if value is not None else 0.0))
            cutoff = timestamp - self.config["selection_window_ms"]
            self.selection_samples[side] = [(t, q) for t, q in samples if t >= cutoff]
        if timestamp - self.selection_started < self.config["selection_window_ms"]:
            return
        scores = {side: statistics.median(q for _, q in samples)
                  for side, samples in self.selection_samples.items()}
        candidate = max(scores, key=scores.get)  # left wins a deterministic tie
        value, quality, _ = sides[candidate]
        if (scores[candidate] >= self.config["selection_visibility"] and value is not None
                and quality >= self.config["selection_visibility"]):
            self.side = candidate

    def _zone(self, value):
        start, target = self.preset["start"], self.preset["target"]
        if start > target:
            return "start" if value >= start else "target" if value <= target else "middle"
        return "start" if value <= start else "target" if value >= target else "middle"

    def _count(self, timestamp, value, raw):
        zone = self._zone(value)
        if zone != self.dwell_zone:
            self.dwell_zone, self.dwell_started = zone, timestamp
        stable = timestamp - self.dwell_started >= self.config["dwell_ms"]
        if self.phase == "WAIT_START":
            if zone == "start" and stable:
                self.phase = "READY"
            return None
        if self.phase == "READY":
            if zone == "start":
                return None
            self.phase = "OUTBOUND"
            self.cycle_start = self.last_valid  # last observed start posture
            self.minimum = self.maximum = raw
        self.minimum = min(self.minimum, raw)
        self.maximum = max(self.maximum, raw)
        if self.phase == "OUTBOUND":
            if zone == "target" and stable:
                self.target_time = self.dwell_started
                self.phase = "AT_TARGET"
            elif zone == "start" and stable:
                # Returned before a confirmed target: incomplete, never a rep.
                self.phase = "READY"
                self.cycle_start = None
            return None
        if self.phase == "AT_TARGET" and zone != "target":
            self.phase = "RETURNING"
        if self.phase == "RETURNING" and zone == "start" and stable:
            duration = timestamp - self.cycle_start
            event = None
            if duration >= self.config["min_rep_ms"]:
                self.reps += 1
                event = {
                    "id": f"{self.session_id}:rep:{self.reps}", "rep": self.reps,
                    "start_ms": self.cycle_start, "target_ms": self.target_time,
                    "end_ms": timestamp, "duration_ms": duration,
                    "min_angle_deg": self.minimum, "max_angle_deg": self.maximum,
                    "rom_deg": self.maximum - self.minimum,
                }
            self.phase = "READY"
            self.cycle_start = None
            return event
        return None

    def update(self, landmarks, width, height, timestamp_ms):
        """Return a fresh result; None for duplicate/out-of-order/invalid timestamps.

        Invalid timestamps leave *all* state unchanged. Invalid pose samples are
        published as missing values and cancel any partial cycle immediately.
        """
        if (not finite(timestamp_ms) or timestamp_ms < 0 or
                (self.last_timestamp is not None and timestamp_ms <= self.last_timestamp)):
            return None
        gap = self.last_timestamp is not None and timestamp_ms-self.last_timestamp > self.config["max_gap_ms"]
        self.last_timestamp = timestamp_ms
        self.sequence += 1
        if gap:
            self._discard_cycle()
            if self.side is None:
                self.selection_started = None
                self.selection_samples = {"left": [], "right": []}
        triples = TRIPLES[self.preset["joint"]]
        sides = {side: angle_2d(landmarks, triple, width, height, self.config["tracking_visibility"])
                 for side, triple in triples.items()}
        if self.side is None:
            self._select(timestamp_ms, sides)
        raw, quality, reason = sides[self.side] if self.side else (None, None, "selecting_side")
        rep_event = None
        if raw is None:
            self._discard_cycle()
            status = "selecting_side" if self.side is None else "lost"
        else:
            if self.filtered is None:
                self.filtered = raw
            else:
                alpha = -math.expm1(-(timestamp_ms-self.last_valid)/self.config["ema_tau_ms"])
                self.filtered += alpha * (raw-self.filtered)
            rep_event = self._count(timestamp_ms, self.filtered, raw)
            self.last_valid = timestamp_ms
            status = "tracking"
            if gap:
                reason = "gap_reset"
        return {
            "schema_version": 2, "algorithm_version": self.config["version"],
            "session_id": self.session_id, "exercise": self.exercise,
            "sequence": self.sequence, "sample_timestamp_ms": timestamp_ms,
            "side": self.side, "joint": self.preset["joint"],
            "angle": self.filtered if raw is not None else None, "raw_angle": raw,
            "visibility": quality, "tracking_status": status, "reason": reason,
            "form_status": "not_evaluated", "reps": self.reps,
            "phase": self.phase, "rep_event": rep_event,
        }
