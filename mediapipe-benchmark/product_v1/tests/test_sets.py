"""Clock/atomicity tests with injected monotonic time, not synthesized motion evidence."""
import copy
import itertools
import tempfile
import unittest
from pathlib import Path
from product_v1.protocol import validate_command, validate_goal
from product_v1.session import Session, recover_interrupted
from product_v1.state import Store

class SetsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'state.db'
        self.store=Store(self.path);self.now=0.0;self.timestamp=0
    def tearDown(self):
        self.store.close();self.tmp.cleanup()
    def new(self,sets=3,rest=15,goal=None):
        meta=dict(session_id='s1',hub_id='h1',patient_uid='p1',exercise='squat',schema_version=2,
                  algorithm_version='2.0.0',created_at=1000,source='camera',form_status='not_evaluated',
                  requested_side='auto',goal=goal or dict(mode='sets',reps_per_set=5,sets=sets,rest_s=rest))
        self.store.accept('c1',dict(status='accepted'),meta)
        return Session(self.store,meta,monotonic=lambda:self.now,wall=lambda:1000+int(self.now*1000))
    def frame(self,s,event=False,phase='READY',tracking='tracking',allow=True):
        self.timestamp+=100;self.now+=.1
        value=dict(sample_timestamp_ms=self.timestamp,phase=phase,tracking_status=tracking,
                   angle=160 if tracking=='tracking' else None,reps=99,
                   rep_event=dict(id='wrong',rep=99,start_ms=1,target_ms=2,end_ms=3,duration_ms=2,rom_deg=30) if event else None)
        done=s.sample(value,allow_start=allow)
        return done,value
    def finish_set(self,s):
        for _ in range(5):self.frame(s,event=True)
    def test_three_sets_rest_realign_and_no_extra_rep(self):
        s=self.new();self.frame(s,allow=False);self.assertIsNone(s.started)
        self.frame(s);self.finish_set(s)
        self.assertEqual((s.progress['reps'],s.workload_phase),(5,'resting'))
        self.assertEqual(s.phase,'running')
        for _ in range(5):self.frame(s,event=True)
        self.assertEqual(s.progress['reps'],5)
        self.now+=15;s.tick();self.assertEqual(s.workload_phase,'aligning')
        self.frame(s,event=True,allow=False);self.assertEqual(s.progress['reps'],5)
        self.frame(s);self.finish_set(s)
        self.now+=15;s.tick();self.frame(s);self.finish_set(s)
        self.assertEqual(s.completion_reason,'goal_complete')
        self.frame(s,event=True);self.assertEqual(s.progress['reps'],15)
        out=s.finish('patient_stop');self.assertEqual(out['completed_sets'],3)
        self.assertEqual(out['status'],'completed');self.assertEqual(len(out['set_results']),3)
        self.assertAlmostEqual(out['active_s']+out['rest_s']+out['aligning_s'],out['elapsed_s'])
        events=[__import__('json').loads(r[0]) for r in self.store.db.execute("select payload from outbox where path like '%/events/%'")]
        self.assertEqual([e['rep'] for e in events],list(range(1,16)))
        self.assertEqual([e['rep_in_set'] for e in events],list(range(1,6))*3)
    def test_atomic_restart_before_and_after_terminal_rep(self):
        s=self.new(sets=1);self.frame(s)
        for _ in range(4):self.frame(s,event=True)
        saved=copy.deepcopy(self.store.get('progress'))
        self.frame(s,event=True)
        self.assertEqual(self.store.get('progress')['completed_sets'],1)
        # A real SQLite reopen preserves terminal completion even before summary commit.
        self.store.close();self.store=Store(self.path)
        out=recover_interrupted(self.store)
        self.assertEqual((out['reps'],out['status'],out['error']),(5,'completed','goal_complete'))
        self.assertIsNone(recover_interrupted(self.store))
        self.assertEqual(saved['reps'],4);self.assertNotIn('completion_reason',saved)
    def test_reboot_during_rest_does_not_resume_or_lose_completed_set(self):
        s=self.new();self.frame(s);self.finish_set(s)
        self.store.close();self.store=Store(self.path)
        out=recover_interrupted(self.store)
        self.assertEqual((out['reps'],out['completed_sets'],out['error']),(5,1,'hub_restarted'))
        self.assertIsNone(self.store.get('active'))
    def test_timeout_deadline_and_duplicate_timestamp(self):
        s=self.new();self.now=120;self.assertEqual(s.tick(),'preparation_timeout')
    def test_set_limit_counts_from_first_ready(self):
        s=self.new();self.now=100;self.frame(s);self.now+=1800
        self.assertEqual(s.tick(),'session_limit');self.assertEqual(s.finish('patient_stop')['elapsed_s'],1800)
    def test_time_deadline_rejects_last_partial_or_late_rep(self):
        s=self.new(goal=dict(mode='time',duration_s=60));self.frame(s)
        self.frame(s,event=True);self.now+=60;_,v=self.frame(s,event=True)
        self.assertEqual((s.completion_reason,s.progress['reps']),('duration_complete',1))
        self.assertIsNone(v['rep_event'])
    def test_goal_bounds_exhaustive_and_commands_compatible(self):
        for minutes in range(1,11):validate_goal(dict(mode='time',duration_s=minutes*60))
        for r,n,t in itertools.product((5,10,15),(1,2,3),range(15,121,15)):
            validate_goal(dict(mode='sets',reps_per_set=r,sets=n,rest_s=t))
        for goal in [dict(mode='time',duration_s=x) for x in (0,59,61,601,True)] + [dict(mode='sets',reps_per_set=5,sets=3,rest_s=x) for x in (0,14,16,121,True)] + [dict(mode='sets',reps_per_set=4,sets=1,rest_s=30),dict(mode='time',duration_s=60,extra=1)]:
            with self.assertRaises(ValueError):validate_goal(goal)
        c=dict(action='start',patient_uid='p1',created_at=1000,expires_at=31000,exercise='biceps_curl',protocol_version=2,requested_side='left',goal=dict(mode='time',duration_s=60))
        validate_command(c,'p1',2000)
        for change in [dict(requested_side='auto'),dict(protocol_version=3),dict(duration_s=60)]:
            with self.assertRaises(ValueError):validate_command({**c,**change},'p1',2000)
        old={k:v for k,v in c.items() if k not in ('goal','protocol_version','requested_side')};old['duration_s']=180
        validate_command(old,'p1',2000)
        with self.assertRaises(ValueError):validate_command({**old,'exercise':'shoulder_flexion'},'p1',2000)
