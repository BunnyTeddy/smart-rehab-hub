import copy
import json
import math
import unittest

from pose_algorithm import PoseAlgorithm, PRESETS, angle_2d
from pose_algorithm.core import TRIPLES


def pose(value, joint="elbow", left=.95, right=.9, width=640, height=480):
    points = [[.5, .5, 0., .95] for _ in range(33)]
    for side, visibility in (("left", left), ("right", right)):
        a, b, c = TRIPLES[joint][side]
        center = .35 if side == "left" else .65
        points[a] = [center+.12, .5, 0., visibility]
        points[b] = [center, .5, 0., visibility]
        radians = math.radians(value)
        points[c] = [center+.12*math.cos(radians), .5+.12*width/height*math.sin(radians), 0., visibility]
    return points


def run_angles(engine, values, step=100, start=0):
    results = []
    for i, value in enumerate(values):
        points = [] if value is None else pose(value, engine.preset["joint"])
        results.append(engine.update(points, 640, 480, start+i*step))
    return results


class GeometryTests(unittest.TestCase):
    def test_angles_and_aspect_ratio(self):
        for value in (0, 30, 90, 120, 180):
            self.assertAlmostEqual(angle_2d(pose(value), (11,13,15), 640,480)[0], value)
        self.assertNotAlmostEqual(angle_2d(pose(60), (11,13,15), 480,640)[0], 60)

    def test_invalid_geometry(self):
        for bad in (float("nan"), float("inf"), -1, 2):
            points = pose(90); points[11][0] = bad
            self.assertIsNone(angle_2d(points, (11,13,15), 640,480)[0])
        points = pose(90); points[11] = points[13][:]
        self.assertIsNone(angle_2d(points, (11,13,15), 640,480)[0])
        self.assertIsNone(angle_2d(pose(90,left=.49), (11,13,15),640,480)[0])
        self.assertIsNone(angle_2d([], (11,13,15),640,480)[0])
        self.assertIsNone(angle_2d(pose(90), (11,13,15),0,480)[0])


class AlgorithmTests(unittest.TestCase):
    def engine(self, exercise="biceps_curl", **kw):
        return PoseAlgorithm(exercise, side=kw.pop("side", "left"), **kw)

    def test_all_five_full_cycles(self):
        for exercise in PRESETS["exercises"]:
            with self.subTest(exercise=exercise):
                engine = self.engine(exercise)
                start, target = (90,175) if exercise == "shoulder_press" else (175,65)
                values = [start]*5 + [130,120] + [target]*5 + [130,140] + [start]*5
                results = run_angles(engine, values)
                self.assertEqual(engine.reps, 1)
                events = [r["rep_event"] for r in results if r["rep_event"]]
                self.assertEqual(len(events), 1)
                event = events[0]
                self.assertLess(event["start_ms"], event["target_ms"])
                self.assertLess(event["target_ms"], event["end_ms"])
                self.assertGreater(event["rom_deg"], 40)

    def test_partial_initial_and_final(self):
        engine = self.engine()
        run_angles(engine, [70]*5 + [130,170,170,170] + [120,70,70,70])
        self.assertEqual(engine.reps,0)

    def test_returns_without_target(self):
        engine = self.engine()
        run_angles(engine, [175]*5 + [130]*5 + [175]*5)
        self.assertEqual(engine.reps,0)

    def test_hold_and_jitter_and_single_sample_spike(self):
        engine = self.engine()
        run_angles(engine, [175]*5+[70]+[175]*5+[144,146]*8+[175]*5)
        self.assertEqual(engine.reps,0)
        engine = self.engine()
        run_angles(engine,[175]*5+[70]*20+[175]*20)
        self.assertEqual(engine.reps,1)

    def test_missing_pose_discards_partial_but_retains_reps(self):
        engine = self.engine()
        values=[175]*5+[70]*5+[175]*5+[70]*5+[None]+[175]*5
        results=run_angles(engine,values)
        self.assertEqual(engine.reps,1)
        lost=results[20]
        self.assertEqual(lost["tracking_status"],"lost")
        self.assertIsNone(lost["angle"])
        self.assertIsNone(lost["raw_angle"])

    def test_gap_discards_partial(self):
        engine = self.engine()
        run_angles(engine,[175]*5+[70]*5)
        r=engine.update(pose(175),640,480,1400)
        self.assertEqual(r["reason"],"gap_reset")
        run_angles(engine,[175]*5,start=1500)
        self.assertEqual(engine.reps,0)

    def test_invalid_timestamp_changes_no_state(self):
        engine = self.engine()
        engine.update(pose(175),640,480,100)
        before=copy.deepcopy(engine.__dict__)
        for timestamp in (100,99,float("nan"),float("inf"),-1,True):
            self.assertIsNone(engine.update(pose(70),640,480,timestamp))
            self.assertEqual(engine.__dict__,before)

    def test_auto_side_locked_through_occlusion(self):
        engine = self.engine(side="auto")
        run_angles(engine,[175]*5)
        self.assertEqual(engine.side,"left")
        result=engine.update(pose(70,left=.1,right=1),640,480,500)
        self.assertEqual(result["side"],"left")
        self.assertEqual(result["tracking_status"],"lost")
        self.assertIsNone(result["angle"])

    def test_wait_for_quality_and_reset(self):
        engine=self.engine(side="auto")
        for i in range(10):
            r=engine.update(pose(175,left=.6,right=.6),640,480,i*100)
        self.assertIsNone(r["side"])
        self.assertEqual(r["tracking_status"],"selecting_side")
        engine.reset()
        self.assertEqual(engine.sequence,0)
        self.assertIsNone(engine.last_timestamp)

    def test_same_motion_at_9_15_30_fps(self):
        for fps in (9,15,30):
            engine=self.engine()
            for i in range(fps*7):
                t=i/fps; phase=t%3
                value=(175 if phase<.6 else 175-(phase-.6)/.6*105 if phase<1.2
                       else 70 if phase<1.8 else 70+(phase-1.8)/.6*105 if phase<2.4 else 175)
                engine.update(pose(value),640,480,t*1000)
            self.assertEqual(engine.reps,2, fps)

    def test_deterministic_and_json_finite(self):
        a=self.engine(); b=self.engine()
        sequence=[175]*5+[70]*5+[None]*2+[175]*4
        aa=run_angles(a,sequence); bb=run_angles(b,sequence)
        self.assertEqual(aa,bb)
        json.dumps(aa,allow_nan=False)

    def test_min_duration_rejects_fast_cycle(self):
        config=copy.deepcopy(PRESETS); config["ema_tau_ms"]=1
        engine=self.engine(config=config)
        run_angles(engine,[175]*3+[70]*3+[175]*3,step=40)
        self.assertEqual(engine.reps,0)


if __name__ == "__main__":
    unittest.main()
