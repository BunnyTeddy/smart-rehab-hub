"""Regression cases for the observed startup failures; not human acceptance."""
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from product_v1.diagnostics import DetectionDiagnostics
from product_v1.display import Display
from product_v1.engine import run_session
from product_v1.movement import create_algorithm, PRESETS, MovementAlgorithm
from product_v1.catalog import EXERCISE_CATALOG
from product_v1.session import Session
from product_v1.state import Store
from product_v1.tests.test_movement import geometry
from product_v1.tests.test_bilateral_review import pose


ZONES = dict(sit_to_stand=(95,170), seated_knee_extension=(90,170),
             seated_hip_flexion=(95,50), shoulder_flexion=(30,85),
             shoulder_abduction=(30,85), standing_hip_abduction=(180,140))


def camera_pose(exercise, angle, side='left', visibility=1):
    points = (pose(exercise,angle,angle) if side == 'both' or exercise == 'biceps_curl'
              else geometry('sit_to_stand',side,angle,secondary=180) if exercise == 'squat'
              else geometry(exercise,side,angle))
    # Convert the fixture's square coordinates to a real 4:3 camera without
    # accidentally distorting the intended physical angles.
    return [[.5+(x-.5)*480/640,y,z,visibility] for x,y,z,_ in points]


class DetectionStartupTests(unittest.TestCase):
    def test_natural_inward_arm_at_rest_can_start_but_cross_body_raise_cannot_count(self):
        a=create_algorithm('shoulder_abduction',side='left')
        def inward(angle):
            p=camera_pose('shoulder_abduction',angle)
            for i in (13,15):p[i][0]=2*p[11][0]-p[i][0]
            return p
        for _ in range(5):r=a.update(inward(28),640,480,(a.last_timestamp or 0)+200)
        self.assertEqual(r['phase'],'READY')
        for angle in (50,85,85,50,28,28):
            r=a.update(inward(angle),640,480,a.last_timestamp+200)
            if angle==85:self.assertEqual(r['reason'],'inward_movement')
        self.assertEqual(a.reps,0)
        # A valid outward raise can then finish at the same relaxed rest pose.
        for angle in (50,85,85,50):a.update(camera_pose('shoulder_abduction',angle),640,480,a.last_timestamp+200)
        for _ in range(4):a.update(inward(28),640,480,a.last_timestamp+200)
        self.assertEqual(a.reps,1)

    def test_observed_shoulder_rest_angles_can_reach_ready_and_finish(self):
        for exercise in ('shoulder_flexion','shoulder_abduction'):
            for side in ('left','right','both'):
                a=create_algorithm(exercise,side=side)
                for n in range(1,6):
                    for value in (28,30,27,31,30,50,85,85,85,50,30,28,30):
                        result=a.update(camera_pose(exercise,value,side),640,480,(a.last_timestamp or 0)+200)
                    self.assertEqual(a.reps,n,(exercise,side))
                    self.assertEqual(result['phase'],'READY')

    def test_shoulder_raise_counts_even_with_bent_elbow(self):
        for exercise in ('shoulder_flexion','shoulder_abduction'):
            a=create_algorithm(exercise,side='left')
            for value in (30,30,30,50,85,85,50,30,30):
                p=camera_pose(exercise,value)
                # Fold the forearm back toward the shoulder (elbow near zero).
                p[15]=[(p[13][0]+p[11][0])/2,(p[13][1]+p[11][1])/2,0,1]
                r=a.update(p,640,480,(a.last_timestamp or 0)+200)
            self.assertEqual(r['phase'],'READY');self.assertEqual(a.reps,1)

    def test_small_shoulder_motion_static_and_gap_never_make_a_rep(self):
        for exercise in ('shoulder_flexion','shoulder_abduction'):
            a=create_algorithm(exercise,side='left')
            for value in [30]*30+([30,40,45,45,40,30]*5):
                a.update(camera_pose(exercise,value),640,480,(a.last_timestamp or 0)+200)
            self.assertEqual(a.reps,0)
            for value in (30,30,85,85):
                a.update(camera_pose(exercise,value),640,480,a.last_timestamp+200)
            a.update(camera_pose(exercise,30),640,480,a.last_timestamp+a.config['max_gap_ms']+1)
            a.update(camera_pose(exercise,30),640,480,a.last_timestamp+200)
            self.assertEqual(a.reps,0)

    def test_auto_side_selection_uses_tracking_quality_and_keeps_selected_side(self):
        a=MovementAlgorithm('sit_to_stand',side='auto')
        for _ in range(8):
            r=a.update(camera_pose('sit_to_stand',95,visibility=.6),640,480,(a.last_timestamp or 0)+200)
        self.assertEqual(r['phase'],'READY');self.assertEqual(a.side,'left')
        for _ in range(8):
            p=camera_pose('sit_to_stand',95)
            for i in (11,23,25,27):p[i][3]=.1
            r=a.update(p,640,480,a.last_timestamp+200)
        self.assertEqual(r['tracking_status'],'lost');self.assertEqual(a.side,'left')
        b=MovementAlgorithm('sit_to_stand',side='auto')
        for _ in range(8):
            r=b.update(camera_pose('sit_to_stand',95,visibility=.49),640,480,(b.last_timestamp or 0)+200)
        self.assertIsNone(b.side);self.assertEqual(b.reps,0)

    def test_all_four_active_detectors_pass_engine_countdown_and_five_cycles(self):
        """Do not mock the detector as permanently READY: drive actual geometry."""
        import cv2  # Load native extension before patch.dict(sys.modules).
        import numpy as np
        from product_v1 import device_health
        for exercise,(start,target) in {'squat':(170,120),'biceps_curl':(170,110),**{e:z for e,z in ZONES.items() if e in EXERCISE_CATALOG}}.items():
            for side in (('left','right','both') if exercise in ('biceps_curl','shoulder_flexion','shoulder_abduction') else ('left','right')):
                with self.subTest(exercise=exercise,side=side), tempfile.TemporaryDirectory() as tmp:
                    clock=[0.0];store=Store(Path(tmp)/'state.db')
                    requested='auto' if exercise=='squat' else side
                    meta=dict(session_id='test',hub_id='test',patient_uid='test',exercise=exercise,
                              algorithm_version=PRESETS['version'],created_at=0,requested_side=requested,
                              goal=dict(mode='sets',sets=1,reps_per_set=5,rest_s=15))
                    s=Session(store,meta,monotonic=lambda:clock[0])
                    display=Display(clock=lambda:clock[0]);display.ready=True;display.begin(meta)
                    voice=SimpleNamespace(ready=True,until=0);messages=[];counts=[]
                    def say(key):
                        messages.append((key,clock[0],s.workload_phase));voice.until=clock[0]+1
                    voice.say=say;voice.idle=lambda:clock[0]>=voice.until;voice.count=counts.append
                    cloud=SimpleNamespace(last_success=0)
                    class Camera:
                        def __init__(self,*_):self.n=0
                        def next(self,after):
                            clock[0]+=.2;cloud.last_success=clock[0];self.n+=1
                            assert self.n<700,'No start/count: '+exercise
                            return self.n,clock[0],round(clock[0]*1000),np.zeros((480,640,3),np.uint8)
                        def close(self):pass
                    motion=[0]
                    def predict(*_):
                        angle=start
                        if s.workload_phase=='working' and voice.idle():
                            sequence=[start]*3+[(start+target)/2]*3+[target]*3+[(start+target)/2]*3+[start]*3
                            angle=sequence[motion[0]%len(sequence)];motion[0]+=1
                        pts=camera_pose(exercise,angle,side)
                        if exercise == 'squat':
                            # Side-on camera: the other leg is behind the visible
                            # one, so auto must choose the side actually exercised.
                            for i in ((12,24,26,28) if side=='left' else (11,23,25,27)):
                                pts[i][3]=.3
                        return SimpleNamespace(pose_landmarks=[[SimpleNamespace(x=x,y=y,z=z,visibility=v) for x,y,z,v in pts]])
                    model=SimpleNamespace(detect_for_video=predict,close=lambda:None)
                    vision=SimpleNamespace(PoseLandmarker=SimpleNamespace(create_from_options=lambda _:model),
                                           PoseLandmarkerOptions=lambda **_:None,RunningMode=SimpleNamespace(VIDEO=1))
                    mp=SimpleNamespace(tasks=SimpleNamespace(BaseOptions=type('BaseOptions',(),{
                        'Delegate':SimpleNamespace(CPU=0),'__init__':lambda self,**_:None})),
                        Image=lambda **_:None,ImageFormat=SimpleNamespace(SRGB=0),
                        solutions=SimpleNamespace(pose=SimpleNamespace(POSE_CONNECTIONS=[])))
                    modules={'mediapipe':mp,'mediapipe.tasks':SimpleNamespace(),
                             'mediapipe.tasks.python':SimpleNamespace(vision=vision)}
                    with patch.dict('sys.modules',modules),patch('product_v1.engine.Camera',Camera),\
                         patch('product_v1.engine.time.monotonic',lambda:clock[0]),\
                         patch.object(device_health,'resources',lambda:dict(temperature_c=40,throttled='throttled=0x0')):
                        reason=run_session(s,{'model_path':'unused'},display,voice,threading.Event(),cloud,lambda *_:None)
                    self.assertEqual(reason,'goal_complete');self.assertEqual(s.progress['reps'],5)
                    begin=next(m for m in messages if m[0]=='set_start')
                    self.assertFalse(any(m[0]=='hold_ready' for m in messages))
                    self.assertEqual(begin[2],'working')
                    self.assertGreaterEqual(begin[1]-messages[-2][1],3)
                    diag=store.get('detection_diagnostics')[-1]
                    self.assertIsNotNone(diag['started_ms']);self.assertGreater(diag['longest_ready_ms'],3000)
                    store.close()

    def test_diagnostics_bound_and_separate_audio_from_missing_pose(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'state.db')
            d=DetectionDiagnostics(dict(exercise='shoulder_flexion',patient_uid='private',session_id='private'))
            for n in range(1100):
                d.sample(dict(sample_timestamp_ms=n*400,phase='WAIT_START',tracking_status='lost',
                              reason='missing_pose',landmarks='private',image='private'),preparing=n<20,countdown=None)
            for _ in range(14):d.save(store)
            reports=store.get('detection_diagnostics')
            self.assertEqual(len(reports),12);self.assertEqual(len(reports[-1]['trace']),1000)
            self.assertNotIn('private',str(reports));self.assertEqual(d.report()['gaps_over_350_ms'],1099)
            self.assertEqual(d.report()['reasons']['preparing_audio'],20)
            self.assertEqual(store.count(),0);store.close()
