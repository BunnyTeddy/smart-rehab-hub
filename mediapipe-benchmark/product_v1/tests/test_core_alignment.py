"""Compare the added exercises to the working v2 counter, including failures."""
import copy
import math
import unittest
from pose_algorithm.core import PoseAlgorithm
from product_v1.movement import MovementAlgorithm, PRESETS, PRODUCT_PRESETS, create_algorithm
from product_v1.catalog import EXERCISE_CATALOG
from product_v1.voice import TrackingReminder
from product_v1.tests.test_detection_startup import camera_pose, ZONES
from product_v1.tests.test_movement import geometry


def angle_fixture(value):
    # Independent single-joint input for the unmodified baseline algorithm.
    p=[[.5,.5,0,1] for _ in range(33)]
    p[11]=[.47,.5,0,1];p[13]=[.35,.5,0,1]
    a=math.radians(value)
    p[15]=[.35+.12*math.cos(a),.5+.16*math.sin(a),0,1]
    return p


class CoreAlignmentTests(unittest.TestCase):
    def test_added_exercises_use_the_same_counter_as_squat_and_curl(self):
        self.assertIs(MovementAlgorithm._count, PoseAlgorithm._count)
        self.assertIs(MovementAlgorithm._discard_cycle, PoseAlgorithm._discard_cycle)
        # Compare every phase, filtered angle and event against the actual base
        # update, using identical primary angles/timestamps and valid posture.
        # Include partial cycles, long gaps, duplicate frames and lost pose.
        for exercise, (start, target) in ZONES.items():
            with self.subTest(exercise=exercise):
                config=copy.deepcopy(PRODUCT_PRESETS if exercise in EXERCISE_CATALOG else PRESETS)
                preset=config['exercises'][exercise]
                config['exercises'][exercise]={'joint':'elbow','start':preset['start'], 'target':preset['target']}
                base=PoseAlgorithm(exercise,side='left',config=config)
                added=create_algorithm(exercise,side='left') if exercise in EXERCISE_CATALOG else MovementAlgorithm(exercise,side='left')
                ts=0
                values=[start]*5+[(start+target)/2]*3+[start]*5
                values+=([start]*4+[(start+target)/2]*3+[target]*4+[(start+target)/2]*3+[start]*4)*3
                values += [target]*4+[None]+[start]*5+[target]*5+[start]*5
                for i,value in enumerate(values):
                    ts+=400 if i==44 else 0 if i==49 else 200
                    p=None if value is None else camera_pose(exercise,value)
                    a=added.update(p,640,480,ts)
                    b=base.update(None if value is None else angle_fixture(value),640,480,ts)
                    if a is None or b is None:
                        self.assertIs(a,b);continue
                    self.assertEqual(a['phase'],b['phase'],(exercise,i))
                    self.assertEqual(a['reps'],b['reps'])
                    if a['angle'] is not None:self.assertAlmostEqual(a['angle'],b['angle'],places=6)
                    self.assertEqual(bool(a['rep_event']),bool(b['rep_event']))

    def test_shoulder_wrist_is_not_required_and_curl_cannot_substitute(self):
        for exercise in ('shoulder_flexion','shoulder_abduction'):
            for side in ('left','right','both'):
                a=create_algorithm(exercise,side=side)
                for x in [30]*4+[50]*3+[85]*4+[50]*3+[30]*4:
                    p=camera_pose(exercise,x,side)
                    for i in (15,16):p[i]=[.5,1.5,0,0]
                    a.update(p,640,480,(a.last_timestamp or 0)+200)
                self.assertEqual(a.reps,1,(exercise,side))

    def test_secondary_posture_does_not_reset_visible_motion_before_target(self):
        for exercise in ('seated_knee_extension','seated_hip_flexion','standing_hip_abduction'):
            with self.subTest(exercise=exercise):
                start,target=ZONES[exercise];a=MovementAlgorithm(exercise,side='left')
                for _ in range(4):a.update(geometry(exercise,'left',start),100,100,(a.last_timestamp or 0)+200)
                # Tilt the trunk briefly while the limb is in transit; all
                # landmarks remain visible. This is not tracking loss.
                p=geometry(exercise,'left',(start+target)/2);p[11][0]+=.2
                r=a.update(p,100,100,a.last_timestamp+200)
                self.assertEqual(r['tracking_status'],'tracking')
                self.assertNotEqual(r['phase'],'WAIT_START')
                for value in [target]*4+[start]*4:
                    a.update(geometry(exercise,'left',value),100,100,a.last_timestamp+200)
                self.assertEqual(a.reps,1)

    def test_wrong_target_still_cannot_complete_cycle(self):
        for exercise in ('seated_knee_extension','seated_hip_flexion','standing_hip_abduction'):
            start,target=ZONES[exercise];a=MovementAlgorithm(exercise,side='left')
            for value in [start]*4+[target]*6+[start]*4:
                p=geometry(exercise,'left',value)
                if value==target:p[11][0]+=.2
                r=a.update(p,100,100,(a.last_timestamp or 0)+200)
            self.assertEqual(a.reps,0,exercise)
            self.assertEqual(r['phase'],'READY')

    def test_tracking_voice_is_not_repeated_for_flicker_or_prolonged_loss(self):
        r=TrackingReminder()
        self.assertFalse(r.update(False,False,0))
        self.assertFalse(r.update(False,True,1))
        self.assertFalse(r.update(True,True,2))
        self.assertFalse(r.update(False,True,3))
        self.assertTrue(r.update(False,True,6))
        for n in (10,20,40,80):self.assertFalse(r.update(False,True,n))
        self.assertFalse(r.update(True,True,81))
        self.assertFalse(r.update(False,True,82))
        self.assertFalse(r.update(False,True,86))
        r.update(True,True,87);r.update(True,True,90)
        self.assertFalse(r.update(False,True,91))
        self.assertTrue(r.update(False,True,94))
