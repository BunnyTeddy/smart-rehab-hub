"""Reduced-ROM and sparse-frame regressions; fixtures are not human acceptance."""
import unittest

from product_v1.catalog import CAPABILITIES, EXERCISE_CATALOG
from product_v1.movement import PRODUCT_PRESETS, create_algorithm
from product_v1.protocol import validate_command
from product_v1.tests.test_detection_startup import camera_pose


MOTION = {
    'squat': (147, 133),
    'biceps_curl': (142, 113),
    'shoulder_flexion': (38, 57),
    'shoulder_abduction': (38, 57),
}
RETIRED = ('sit_to_stand', 'seated_knee_extension', 'seated_hip_flexion', 'standing_hip_abduction')


class LowRomTests(unittest.TestCase):
    def feed(self, algorithm, values, intervals=(100,), events=None):
        for i, value in enumerate(values):
            result = algorithm.update(
                None if value is None else camera_pose(algorithm.exercise, value, algorithm.requested_side),
                640, 480, (algorithm.last_timestamp or 0) + intervals[i % len(intervals)])
            if events is not None and result and result.get('rep_event'):
                events.append(result['rep_event'])
        return result

    def new(self, exercise, side='left'):
        return create_algorithm(exercise, side=side, session_id='low_rom_fixture')

    def test_reduced_movements_count_five_cycles_on_single_and_both_sides_with_lag(self):
        for exercise, (start, target) in MOTION.items():
            sides = ('left', 'right', 'both') if EXERCISE_CATALOG[exercise]['bilateral'] else ('left', 'right')
            for side in sides:
                with self.subTest(exercise=exercise, side=side):
                    a = self.new(exercise, side)
                    self.assertEqual(a.config['version'], PRODUCT_PRESETS['version'])
                    self.assertEqual(a.config['max_gap_ms'], 800)
                    events = []
                    mid = (start + target) / 2
                    for n in range(1, 6):
                        self.feed(a, [start]*4+[mid]*3+[target]*4+[mid]*3+[start]*4,
                                  (100, 220, 450, 700), events)
                        self.assertEqual(a.reps, n)
                    self.assertEqual(len(events), 5)
                    self.assertTrue(all(e['duration_ms'] >= 500 for e in events))
                    self.assertTrue(all(0 < e['rom_deg'] < 35 for e in events))

    def test_static_jitter_and_partial_cycles_still_do_not_count(self):
        for exercise, (start, target) in MOTION.items():
            for side in ('left', 'both') if EXERCISE_CATALOG[exercise]['bilateral'] else ('left',):
                with self.subTest(exercise=exercise, side=side):
                    a = self.new(exercise, side)
                    self.feed(a, [start-1, start, start+1]*20, (100, 400))
                    mid = (start + target) / 2
                    for _ in range(5):
                        self.feed(a, [start]*4+[mid]*4+[start]*4)
                    self.assertEqual(a.reps, 0)

    def test_long_gap_or_lost_pose_cancels_partial_cycle_without_erasing_completed_reps(self):
        for exercise, (start, target) in MOTION.items():
            for side in ('left', 'both') if EXERCISE_CATALOG[exercise]['bilateral'] else ('left',):
                for failure in ('long_gap', 'lost_pose'):
                    with self.subTest(exercise=exercise, side=side, failure=failure):
                        a = self.new(exercise, side)
                        self.feed(a, [start]*4+[target]*4+[start]*4)
                        self.assertEqual(a.reps, 1)
                        self.feed(a, [target]*4)
                        self.feed(a, [start] if failure == 'long_gap' else [None],
                                  (801,) if failure == 'long_gap' else (100,))
                        self.feed(a, [start]*4)
                        self.assertEqual(a.reps, 1)
                        self.feed(a, [target]*4+[start]*4)
                        self.assertEqual(a.reps, 2)

    def test_only_four_exercises_are_advertised_and_retired_commands_cannot_open_engine(self):
        self.assertEqual(set(EXERCISE_CATALOG), set(MOTION))
        self.assertEqual(set(CAPABILITIES['exercises']), set(MOTION))
        self.assertEqual(set(PRODUCT_PRESETS['exercises']), set(MOTION))
        for exercise in RETIRED:
            self.assertNotIn(exercise, CAPABILITIES['bilateral'])
            for side in ('auto', 'left', 'right', 'both'):
                with self.subTest(exercise=exercise, side=side):
                    with self.assertRaises(ValueError):
                        self.new(exercise, side)
                    command = dict(action='start', patient_uid='p1', created_at=1000,
                                   expires_at=30000, protocol_version=2, exercise=exercise,
                                   requested_side=side, goal={'mode':'time', 'duration_s':60})
                    with self.assertRaises(ValueError):
                        validate_command(command, 'p1', 2000)


if __name__ == '__main__':
    unittest.main()
