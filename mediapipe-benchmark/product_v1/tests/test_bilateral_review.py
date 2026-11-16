"""Regression fixtures, not human motion acceptance."""
import math
import unittest
from product_v1.movement import create_algorithm
from product_v1.tests.test_movement import geometry
from product_v1.protocol import validate_command

SUPPORTED = ('biceps_curl', 'shoulder_flexion', 'shoulder_abduction')
ZONES = {'biceps_curl': (170, 65), 'seated_knee_extension': (90, 170),
         'seated_hip_flexion': (95, 50), 'shoulder_flexion': (5, 85), 'shoulder_abduction': (5, 85)}


def pose(exercise, left, right):
    result = [[.5, .5, 0, 1] for _ in range(33)]
    for side, value, indices in [('left', left, (11,13,15,23,25,27)), ('right', right, (12,14,16,24,26,28))]:
        g = geometry('shoulder_flexion' if exercise == 'biceps_curl' else exercise, side, 0 if exercise == 'biceps_curl' else value)
        if exercise == 'biceps_curl':
            _, elbow, wrist, *_ = indices
            x, y = g[elbow][:2]
            g[wrist] = [x + .15*math.sin(math.radians(value)), y - .15*math.cos(math.radians(value)), 0, 1]
        for i in indices:
            result[i] = g[i]
    return result


class BilateralReviewTests(unittest.TestCase):
    def feed(self, algorithm, left, right, count=5, alter=None):
        result = None
        for _ in range(count):
            p = pose(algorithm.exercise, left, right)
            if alter:
                alter(p)
            result = algorithm.update(p, 100, 100, (algorithm.last_timestamp or 0)+100)
        return result

    def test_shoulder_upper_body_crop_counts_without_any_leg_landmark(self):
        for exercise in ('shoulder_flexion','shoulder_abduction'):
            for side in ('left','right','both'):
                a=create_algorithm(exercise,side=side)
                def crop(p):
                    for i in (25,26,27,28,29,30,31,32): p[i]=[.5,1.5,0,.1]
                for _ in range(5):
                    for x in (5,40,85,40,5): self.feed(a,x,x,alter=crop)
                self.assertEqual(a.reps,5,(exercise,side))

    def test_five_shared_cycles_are_five_not_ten(self):
        for exercise in SUPPORTED:
            a=create_algorithm(exercise,side='both',session_id='both')
            start,target=ZONES[exercise]
            for n in range(1,6):
                for x in (start,(start+target)/2,target,(start+target)/2,start):
                    r=self.feed(a,x,x)
                self.assertEqual(a.reps,n,exercise)
                self.assertEqual(r['side'],'both')
                self.assertIn('angle_left',r)

    def test_alternating_or_one_sided_motion_never_counts(self):
        for exercise in SUPPORTED:
            a=create_algorithm(exercise,side='both');start,target=ZONES[exercise]
            for _ in range(3):
                for left,right in ((start,start),(target,start),(start,start),(start,target),(start,start)):
                    self.feed(a,left,right)
            self.assertEqual(a.reps,0,exercise)

    def test_both_must_reach_target_and_return_and_occlusion_cancels(self):
        for exercise in SUPPORTED:
            a=create_algorithm(exercise,side='both');s,t=ZONES[exercise]
            self.feed(a,s,s);self.feed(a,t,t);self.feed(a,s,t)
            self.assertEqual(a.reps,0)
            events=[]
            for _ in range(5):
                r=self.feed(a,s,s,count=1)
                if r['rep_event']: events.append(r['rep_event'])
            self.assertEqual(a.reps,1)
            self.assertEqual(len(events),1)
            self.assertIn('rom_left_deg',events[0]);self.assertIn('rom_right_deg',events[0])
            self.feed(a,t,t)
            self.feed(a,t,t,count=1,alter=lambda p:p[12].__setitem__(3,0))
            self.feed(a,s,s);self.assertEqual(a.reps,1)
            self.feed(a,t,t)
            a.update(pose(exercise,s,s),100,100,a.last_timestamp+a.config['max_gap_ms']+1)
            self.feed(a,s,s);self.assertEqual(a.reps,1)
            before=a.sequence
            self.assertIsNone(a.update(pose(exercise,s,s),100,100,a.last_timestamp))
            self.assertEqual(a.sequence,before)

    def test_required_joint_still_blocks_and_reports_which_joint(self):
        a=create_algorithm('shoulder_flexion',side='left')
        r=self.feed(a,5,5,alter=lambda p:p[13].__setitem__(1,1.2))
        self.assertEqual(r['reason'],'landmark_13_out_of_frame')
        self.assertEqual(a.reps,0)
        self.assertIsNone(r['angle'])

    def test_both_command_only_on_supported_exercises(self):
        c=dict(action='start',patient_uid='p1',created_at=1000,expires_at=30000,
               exercise='biceps_curl',protocol_version=2,requested_side='both',goal={'mode':'time','duration_s':180})
        for e in SUPPORTED:validate_command({**c,'exercise':e},'p1',2000)
        for e in ('standing_hip_abduction','squat','sit_to_stand'):
            with self.assertRaises(ValueError): validate_command({**c,'exercise':e},'p1',2000)
            with self.assertRaises(ValueError): create_algorithm(e,side='both')

    def test_elbow_curl_alone_never_counts_as_shoulder_raise(self):
        a=create_algorithm('shoulder_flexion',side='left')
        # Keep the upper arm down and move only the forearm through a curl.
        for _ in range(5):
            for x in (170,120,65,120,170):
                p=pose('biceps_curl',x,x)
                for _ in range(5):a.update(p,100,100,(a.last_timestamp or 0)+100)
        self.assertEqual(a.reps,0)
