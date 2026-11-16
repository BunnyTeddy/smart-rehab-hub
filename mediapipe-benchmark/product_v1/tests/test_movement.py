"""Synthetic geometry verifies detection logic, never substitutes for human acceptance."""
import copy
import math
import hashlib
import unittest
from pathlib import Path
from product_v1.movement import MovementAlgorithm, create_algorithm, PRESETS
from pose_algorithm.core import PoseAlgorithm


def geometry(exercise, side, primary, secondary=None):
    p=[[.5,.5,0,1] for _ in range(33)]
    def add(origin, length, deg):
        a=math.radians(deg);return [origin[0]+length*math.cos(a),origin[1]+length*math.sin(a),0,1]
    for s in ('left','right'):
        shoulder,elbow,wrist,hip,knee,ankle=(11,13,15,23,25,27) if s=='left' else (12,14,16,24,26,28)
        x=.35 if s=='left' else .65
        p[shoulder]=[x,.18,0,1];p[hip]=[x,.46,0,1]
        hip_angle=95 if exercise.startswith('seated_') else 100 if exercise=='sit_to_stand' else 180
        knee_angle=90 if exercise.startswith('seated_') or exercise=='sit_to_stand' else 180
        shoulder_angle=0
        if s==side:
            if exercise in ('sit_to_stand','seated_knee_extension'):knee_angle=primary
            if exercise=='sit_to_stand':hip_angle=secondary if secondary is not None else primary
            if exercise in ('seated_hip_flexion','standing_hip_abduction'):hip_angle=primary
            if exercise.startswith('shoulder_'):shoulder_angle=primary
        if exercise=='standing_hip_abduction':
            thigh_angle=90+(180-hip_angle)*(1 if s=='left' else -1)
        else:thigh_angle=-90+hip_angle
        p[knee]=add(p[hip],.16,thigh_angle)
        p[ankle]=add(p[knee],.16,thigh_angle+180-knee_angle)
        arm_angle=90-shoulder_angle if exercise!='shoulder_abduction' or s=='right' else 90+shoulder_angle
        p[elbow]=add(p[shoulder],.15,arm_angle);p[wrist]=add(p[elbow],.15,arm_angle)
    return p


class MovementTests(unittest.TestCase):
    def feed(self,a,angles,side=None,alter=None):
        last=None
        for angle in angles:
            p=geometry(a.exercise,side or a.requested_side,angle)
            if alter:alter(p)
            last=a.update(p,100,100,(a.last_timestamp or 0)+100)
        return last
    def zones(self,id):
        return {'sit_to_stand':(95,170),'seated_knee_extension':(90,170),'seated_hip_flexion':(95,50),
                'shoulder_flexion':(5,85),'shoulder_abduction':(5,85),'standing_hip_abduction':(180,140)}[id]
    def cycle(self,a,side=None):
        start,target=self.zones(a.exercise)
        self.feed(a,[start]*5+[start+(target-start)*.4]*3+[target]*5+[start+(target-start)*.4]*3+[start]*5,side)
    def test_six_full_cycles_on_both_anatomical_sides(self):
        for id in PRESETS['exercises']:
            for side in ('left','right'):
                with self.subTest(exercise=id,side=side):
                    a=MovementAlgorithm(id,side=side,session_id='fixture')
                    for n in range(1,6):self.cycle(a);self.assertEqual(a.reps,n)
    def test_static_incomplete_wrong_side_and_occlusion_do_not_count(self):
        for id in PRESETS['exercises']:
            start,target=self.zones(id)
            with self.subTest(exercise=id):
                a=MovementAlgorithm(id,side='left');self.feed(a,[start]*15);self.assertEqual(a.reps,0)
                self.feed(a,[start]*5+[start+(target-start)*.2]*5+[start]*5);self.assertEqual(a.reps,0)
                if id!='sit_to_stand':self.cycle(a,side='right');self.assertEqual(a.reps,0)
                self.feed(a,[start]*5+[target]*5)
                p=geometry(id,'left',target);p[23][3]=0
                a.update(p,100,100,a.last_timestamp+100)
                self.feed(a,[start]*5);self.assertEqual(a.reps,0)
                self.assertEqual(a.side,'left')
    def test_gap_duplicate_backwards_out_of_frame_and_threshold_noise(self):
        for id in PRESETS['exercises']:
            a=MovementAlgorithm(id,side='left');start,target=self.zones(id)
            self.feed(a,[start]*5+[target]*5)
            self.assertIsNone(a.update(geometry(id,'left',start),100,100,a.last_timestamp))
            self.assertIsNone(a.update(geometry(id,'left',start),100,100,a.last_timestamp-10))
            a.update(geometry(id,'left',start),100,100,a.last_timestamp+351)
            self.feed(a,[start]*5);self.assertEqual(a.reps,0)
            self.feed(a,[target]*5)
            self.feed(a,[start],alter=lambda p:p[23].__setitem__(0,1.1))
            self.feed(a,[start]*5);self.assertEqual(a.reps,0)
            self.feed(a,[target]*30);self.assertEqual(a.reps,0)
    def test_hip_and_knee_must_agree_to_count_stand(self):
        a=MovementAlgorithm('sit_to_stand',side='left')
        self.feed(a,[95]*5)
        for _ in range(8):a.update(geometry(a.exercise,'left',170,secondary=95),100,100,(a.last_timestamp or 0)+100)
        self.feed(a,[95]*6);self.assertEqual(a.reps,0)
    def test_leg_raise_does_not_replace_knee_extension(self):
        a=MovementAlgorithm('seated_knee_extension',side='left')
        self.feed(a,[90]*5)
        for _ in range(8):a.update(geometry('seated_hip_flexion','left',50),100,100,a.last_timestamp+100)
        self.feed(a,[90]*5);self.assertEqual(a.reps,0)
    def test_archived_baseline_files_remain_unchanged(self):
        root=Path(__file__).resolve().parents[2]
        self.assertEqual(hashlib.sha256((root/'pose_algorithm/core.py').read_bytes()).hexdigest(),'9cb85ae35efc00f5431d1867dc6c7b956d7a3e760fa0a99b2c1b2ea5f2ce04b8')
        self.assertEqual(hashlib.sha256((root/'pose_algorithm/presets.json').read_bytes()).hexdigest(),'55f36717ebbc7102f6d29dc49511534b75ea0cf948edcd6164264b9b1c2d90f6')
