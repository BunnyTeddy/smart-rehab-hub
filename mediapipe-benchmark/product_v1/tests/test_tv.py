import tempfile
import unittest
import threading
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from product_v1.display import Display
from product_v1.tv_state import ReadyCountdown, TVPresentation, detection_hint
from product_v1.tv_renderer import TVRenderer
from product_v1.session import Session
from product_v1.state import Store
from product_v1.tests.test_lifecycle import meta


HEALTH = dict(online=True, paired=True, audio_ready=True, storage_fault=False)


class TVTests(unittest.TestCase):
    def test_idle_is_truthful_private_and_dims(self):
        p = TVPresentation(0)
        self.assertEqual(p.view(0, HEALTH, False)['title'], 'Sẵn sàng tập luyện')
        self.assertEqual(p.view(5, {**HEALTH,'online':False}, False)['accent'], 'amber')
        self.assertNotEqual(p.view(5, {**HEALTH,'paired':False}, False)['title'], 'Sẵn sàng tập luyện')
        self.assertTrue(p.view(180, HEALTH, False)['dim'])
        self.assertNotEqual(p.view(180, HEALTH, False)['drift'],p.view(240, HEALTH, False)['drift'])
        p.begin({**meta(), 'patient_name':'SECRET', 'requested_side':'both'})
        self.assertNotIn('SECRET', str(p.__dict__))
        self.assertNotIn('patient_uid',p.meta)

    def test_summary_expires_and_new_session_replaces_it(self):
        p=TVPresentation(0)
        summary=dict(exercise='squat', error='internet_lost', reps=3, active_s=24, patient_uid='PRIVATE')
        p.finish(summary,10)
        self.assertEqual(p.view(24, HEALTH,False)['mode'],'summary')
        self.assertIn('Internet',p.view(24, HEALTH,False)['hint'])
        self.assertNotIn('PRIVATE',str(p.__dict__))
        self.assertEqual(p.view(25, HEALTH,False)['mode'],'idle')
        p.finish(summary,26);p.begin(meta())
        self.assertEqual(p.view(27,HEALTH,False)['mode'],'preparing')

    def test_rest_stopping_and_connection_take_priority(self):
        p=TVPresentation(0);p.begin({**meta(),'goal':dict(mode='sets',sets=3,reps_per_set=5,rest_s=30)})
        p.progress(dict(workload_phase='resting',set_number=1,rest_remaining_s=18,reps=5),'running')
        v=p.view(1,HEALTH,True)
        self.assertEqual(v['number'],'0:18');self.assertIn('2/3',v['hint'])
        self.assertEqual(p.view(1,{**HEALTH,'online':False},True)['title'],'Kết nối đang gián đoạn')
        p.mode='stopping';p.progress(dict(workload_phase='working'),'running')
        self.assertEqual(p.mode,'stopping')

    def test_no_old_frame_or_pose_on_loss_summary_or_new_session(self):
        now=[0.0];d=Display(clock=lambda:now[0]);d.bind_health(lambda:HEALTH)
        d.begin(meta());frame=object();d.offer(frame)
        self.assertIs(d.snapshot()[1],frame)
        now[0]=1.01;self.assertIsNone(d.snapshot()[1])
        d.finish(dict(error='patient_stop'));self.assertIsNone(d.snapshot()[1])
        d.begin(meta());self.assertIsNone(d.snapshot()[1])

    def test_countdown_cancels_on_loss_and_starts_clock_only_after_three_seconds(self):
        with tempfile.TemporaryDirectory() as t:
            now=[0.0];store=Store(Path(t)/'state.db');s=Session(store,meta(),monotonic=lambda:now[0])
            gate=ReadyCountdown()
            for sec,eligible,expected in [(0,False,None),(10,True,3),(11,True,2),(11.5,False,None),
                                           (12,True,3),(14.9,True,1),(15,True,None)]:
                now[0]=sec;count,allow=gate.update(eligible,sec)
                self.assertEqual(count,expected)
                s.sample(dict(sample_timestamp_ms=sec*1000,phase='READY',tracking_status='tracking',angle=160,rep_event=None),allow_start=allow)
                self.assertEqual(s.started is not None,sec==15)
            self.assertEqual(s.progress['elapsed_s'],0)
            gate.update(False,16);self.assertEqual(gate.update(True,50),(3,False))
            store.close()

    def test_joint_diagnostics_and_no_countdown_when_frame_stale(self):
        self.assertIn('cổ tay phải',detection_hint({'reason':'right:landmark_16_out_of_frame'},'shoulder_flexion'))
        p=TVPresentation(0);p.begin(meta())
        p.progress(dict(workload_phase='aligning',tracking_status='tracking',phase='READY'),'aligning',2)
        self.assertEqual(p.view(0,HEALTH,True)['number'],'2')
        self.assertIsNone(p.view(0,HEALTH,False)['countdown'])

    def test_render_preserves_frame_aspect_and_does_not_mutate_camera(self):
        import numpy as np
        renderer=TVRenderer();p=TVPresentation(0);p.begin(meta())
        p.progress(dict(workload_phase='working',tracking_status='tracking',phase='OUTBOUND',remaining_s=120),'running')
        frame=np.full((480,640,3),(20,60,90),dtype=np.uint8);copy=frame.copy()
        for size in [(1280,720),(1920,1080),(1024,768)]:
            view=p.view(0,HEALTH,True);out=renderer.render(size,view,frame)
            x,y,w,h=renderer.fit((640,480),renderer.camera_rect(size))
            self.assertAlmostEqual(w/h,4/3,delta=.003)
            self.assertEqual(out.shape,(size[1],size[0],3))
            self.assertEqual(renderer.camera_rect(size),(0,0,*size))
            # The central body column remains visible from head to foot. Corner
            # HUD pixels are intentionally composited over the source image.
            self.assertTrue(np.all(out[y:y+h,x+w//2]==frame[0,0]))
        self.assertTrue(np.array_equal(frame,copy))
        p.finish(dict(error='goal_complete',reps=5),1)
        a=renderer.render((1280,720),p.view(2,HEALTH,False),frame)
        b=renderer.render((1280,720),p.view(2,HEALTH,False))
        self.assertTrue(np.array_equal(a,b))

    def test_normal_workout_hides_instruction_panels_until_feedback_is_needed(self):
        r=TVRenderer();p=TVPresentation(0);p.begin(meta())
        p.progress(dict(workload_phase='working',tracking_status='tracking',phase='OUTBOUND'), 'running')
        self.assertEqual(r._short_hint(p.view(0,HEALTH,True)), '')
        p.progress(dict(workload_phase='working',tracking_status='tracking',phase='AT_TARGET'), 'running')
        self.assertIn('Về tư thế đầu',r._short_hint(p.view(0,HEALTH,True)))
        p.progress(dict(workload_phase='working',tracking_status='lost',reason='landmark_16_out_of_frame'), 'running')
        self.assertIn('cổ tay phải',r._short_hint(p.view(0,HEALTH,True)))

    def test_engine_drives_countdown_rest_and_three_sets_without_counting_early(self):
        """Run the actual engine/session orchestration with deterministic sensor inputs."""
        # Load the native extension before patch.dict restores sys.modules;
        # OpenCV 4.x cannot safely re-bootstrap half-loaded native submodules.
        import cv2
        import numpy as np
        from product_v1.engine import run_session
        from product_v1 import device_health
        with tempfile.TemporaryDirectory() as directory:
            clock=[0.0];store=Store(Path(directory)/'hub.db')
            s=Session(store,{**meta(),'goal':dict(mode='sets',sets=3,reps_per_set=5,rest_s=15)},monotonic=lambda:clock[0])
            display=Display(clock=lambda:clock[0]);display.ready=True;display.bind_health(lambda:HEALTH);display.begin(s.meta)
            voice=SimpleNamespace(ready=True,until=0.0)
            voice.say=lambda _:setattr(voice,'until',clock[0]+.4)
            voice.idle=lambda:clock[0]>=voice.until
            voice.count=lambda _:None
            cloud=SimpleNamespace(last_success=0.0)
            views=[];starts=[];last_phase=['aligning'];rep_calls=[0];closed=[]
            class FakeCamera:
                def __init__(self,*_):self.n=0
                def next(self,after):
                    clock[0]+=.1;cloud.last_success=clock[0];self.n+=1
                    assert self.n<2000,'Engine did not complete'
                    return self.n,clock[0],int(clock[0]*1000),np.zeros((48,64,3),np.uint8)
                def close(self):closed.append('camera')
            class FakeAlgorithm:
                def __init__(self):self.n=0
                def _discard_cycle(self):self.n=0
                def update(self,landmarks,w,h,ts):
                    self.n+=1
                    # Events emitted before start must still be filtered by Session.
                    event=None
                    if s.workload_phase=='working' and self.n%4==0:
                        rep_calls[0]+=1;event=dict(start_ms=ts-300,target_ms=ts-100,end_ms=ts,duration_ms=300,rom_deg=50)
                    return dict(phase='READY',tracking_status='tracking',reason='ok',reps=0,angle=160,
                                sample_timestamp_ms=ts,rep_event=event)
            prediction=SimpleNamespace(pose_landmarks=[])
            model=SimpleNamespace(detect_for_video=lambda *_:prediction,close=lambda:closed.append('model'))
            vision=SimpleNamespace(PoseLandmarker=SimpleNamespace(create_from_options=lambda _:model),
                                   PoseLandmarkerOptions=lambda **_:None,RunningMode=SimpleNamespace(VIDEO=1))
            mp=SimpleNamespace(tasks=SimpleNamespace(BaseOptions=type('BaseOptions',(),{
                'Delegate':SimpleNamespace(CPU=0),'__init__':lambda self,**kw:None})),
                Image=lambda **_:None,ImageFormat=SimpleNamespace(SRGB=0))
            def sample(result,phase):
                views.append((s.workload_phase,s.progress['reps'],clock[0]))
                if s.workload_phase=='working' and last_phase[0]!='working':starts.append(clock[0])
                last_phase[0]=s.workload_phase
            modules={'mediapipe':mp,'mediapipe.tasks':SimpleNamespace(),
                     'mediapipe.tasks.python':SimpleNamespace(vision=vision)}
            with patch.dict('sys.modules',modules),patch('product_v1.engine.Camera',FakeCamera),\
                 patch('product_v1.engine.create_algorithm',lambda *a,**kw:FakeAlgorithm()),\
                 patch('product_v1.engine.time.monotonic',lambda:clock[0]),\
                 patch.object(device_health,'resources',lambda:dict(temperature_c=40,throttled='throttled=0x0')):
                reason=run_session(s,{'model_path':'unused'},display,voice,threading.Event(),cloud,sample)
            self.assertEqual(reason,'goal_complete');self.assertEqual(s.progress['reps'],15)
            self.assertEqual(len(starts),3);self.assertGreaterEqual(starts[0],3.4)
            for i in range(1,len(views)):
                if views[i][0]=='aligning' or (views[i][0]=='resting' and views[i-1][0]=='resting'):
                    self.assertEqual(views[i][1],views[i-1][1])
            self.assertGreaterEqual(starts[1]-starts[0],18)
            self.assertEqual(set(closed),{'camera','model'});self.assertIsNone(display.frame)
            store.close()
