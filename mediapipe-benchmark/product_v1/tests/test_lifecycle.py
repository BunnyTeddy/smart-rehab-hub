from product_v1.display import Display
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from product_v1.state import Store
from product_v1.session import Session, recover_interrupted
from product_v1.hub import Hub


def meta():
    return dict(session_id='s1', hub_id='h1', patient_uid='p1', exercise='squat', duration_s=180,
                schema_version=2, algorithm_version='2.0.0', created_at=1000, source='camera', form_status='not_evaluated')


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'hub.db')
        self.now = [0.0]

    def tearDown(self):
        self.store.close(); self.tmp.cleanup()

    def sample(self, time_ms, phase='WAIT_START', status='tracking', reps=0, event=None):
        return dict(phase=phase, tracking_status=status, reps=reps, sample_timestamp_ms=time_ms,
                    angle=160 if status == 'tracking' else None, rep_event=event)

    def test_timer_starts_only_on_ready_and_tracking_excludes_gaps(self):
        s = Session(self.store, meta(), monotonic=lambda: self.now[0], wall=lambda: 1000 + int(self.now[0]*1000))
        for sec in [0, 10, 30]:
            self.now[0] = sec
            self.assertFalse(s.sample(self.sample(sec*1000, status='lost')))
            self.assertIsNone(s.started)
        self.now[0] = 40
        s.sample(self.sample(40000, 'READY'))
        self.assertEqual(s.progress['started_at'], 41000)
        self.now[0] = 40.1; s.sample(self.sample(40100, 'OUTBOUND'))
        self.now[0] = 41; s.sample(self.sample(41000, 'WAIT_START', 'lost'))
        self.now[0] = 42; s.sample(self.sample(42000, 'READY'))
        self.assertAlmostEqual(s.progress['tracking_s'], .1)
        self.now[0] = 220
        self.assertTrue(s.sample(self.sample(220000, 'READY')))
        self.assertEqual(s.finish('duration_complete')['elapsed_s'], 180)

    def test_restart_commits_one_result_and_never_resumes(self):
        self.store.accept('cmd', {'status':'accepted'}, meta())
        s = Session(self.store, meta(), monotonic=lambda: self.now[0])
        s.sample(self.sample(0, 'READY'))
        event = dict(id='s1:rep:1', rep=1)
        self.now[0] = 2
        s.sample(self.sample(2000, 'READY', reps=1, event=event))
        result = recover_interrupted(self.store)
        self.assertEqual(result['reps'], 1)
        self.assertEqual(result['error'], 'hub_restarted')
        self.assertIsNone(self.store.get('active'))
        self.assertIsNone(recover_interrupted(self.store))
        summary_count = self.store.db.execute("SELECT COUNT(*) FROM outbox WHERE path LIKE '%/summary'").fetchone()[0]
        self.assertEqual(summary_count, 1)

    def test_duplicate_start_stop_and_owner_validation(self):
        self.store.set('owner_uid','p1')
        started = threading.Event()
        def runner(session, config, display, voice, stop, cloud, on_sample):
            started.set(); stop.wait(5); return 'patient_stop'
        voice = SimpleNamespace(ready=True,say=lambda _:None,close=lambda:None)
        display = Display(); display.ready = True
        cloud = SimpleNamespace(last_success=time.monotonic())
        hub = Hub({'hub_id':'h1'},self.store,cloud,display,voice,runner)
        now = int(time.time()*1000)
        c = dict(action='start',patient_uid='p1',exercise='squat',duration_s=180,created_at=now,expires_at=now+30000)
        hub.command('c1',c); self.assertTrue(started.wait(1)); sid = hub.session.sid
        hub.command('c1',c); self.assertEqual(hub.session.sid,sid)
        hub.command('c2',c); self.assertEqual(self.store.acknowledgement('c2')['reason'],'session_already_active')
        hub.command('c3',{**c,'patient_uid':'p2'}); self.assertEqual(self.store.acknowledgement('c3')['status'],'rejected')
        hub.command('c4',{**c,'created_at':1,'expires_at':2}); self.assertEqual(self.store.acknowledgement('c4')['reason'],'command_expired')
        hub.command('c5',dict(action='stop',patient_uid='p1',session_id=sid,created_at=now,expires_at=now+30000))
        hub.thread.join(2)
        self.assertIsNone(hub.session)
        self.assertEqual(self.store.get('last_summary')['error'],'patient_stop')
        hub.close()
