from product_v1.display import Display
"""Actual bilateral detector + SQLite + Firebase emulator; synthetic landmarks only."""
import json
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from product_v1.tests.e2e_emulator import account, admin, until
from product_v1.tests.test_bilateral_review import pose
from product_v1.movement import create_algorithm
from product_v1.hub import Hub
from product_v1.session import Session, epoch_ms
from product_v1.state import Store
from product_v1.protocol import ROOT


def main():
    hid='both_'+uuid.uuid4().hex[:8]
    p1,patient=account('both-patient',{})
    uid,device=account('both-device',{'role':'hub','hub_id':hid})
    did,doctor=account('both-doctor',{'role':'doctor'})
    patient.put(f'{ROOT}/patients/{p1}/profile',{'name':'Synthetic bilateral fixture','updated_at':epoch_ms()})
    admin('hubs/'+hid,{'device_uid':uid,'owner_uid':p1})
    admin('doctorDirectory/'+did,{'name':'Fixture doctor'})
    patient.put(f'{ROOT}/careLinks/{did}/{p1}',True)
    clock=[0.0]
    def engine(session,config,display,voice,stop,cloud,on_sample):
        algorithm=create_algorithm('shoulder_abduction',side='both',session_id=session.sid)
        def feed(left,right,n=4):
            for _ in range(n):
                clock[0]+=.1
                value=algorithm.update(pose('shoulder_abduction',left,right),100,100,round(clock[0]*1000))
                value.update(source='camera',frame_received_epoch_ms=epoch_ms())
                session.sample(value);on_sample(value,session.phase);stop.wait(.015)
        for set_no in range(3):
            algorithm._discard_cycle();feed(5,5)
            # Alternating arms are not a shared repetition.
            feed(85,5);feed(5,5);feed(5,85);feed(5,5)
            assert session.progress['rep_in_set']==0
            for _ in range(5):
                for x in (5,40,85,40,5):feed(x,x)
            assert session.progress['reps']==5*(set_no+1)
            if set_no<2:
                assert session.workload_phase=='resting'
                clock[0]+=15;session.tick()
        return session.completion_reason
    goal=dict(mode='sets',reps_per_set=5,sets=3,rest_s=15)
    with tempfile.TemporaryDirectory() as tmp:
        store=Store(Path(tmp)/'db');store.set('owner_uid',p1)
        voice=SimpleNamespace(ready=True,say=lambda _:None,close=lambda:None)
        display=Display(); display.ready=True
        with patch('product_v1.hub.Session',lambda store,meta:Session(store,meta,monotonic=lambda:clock[0])):
            hub=Hub({'hub_id':hid},store,device,display,voice,engine);hub.start()
            try:
                until(lambda:(patient.get(f'{ROOT}/hubState/{hid}') or {}).get('capabilities',{}).get('bilateral',{}).get('shoulder_abduction'))
                now=epoch_ms()
                c=dict(action='start',patient_uid=p1,protocol_version=2,exercise='shoulder_abduction',requested_side='both',goal=goal,created_at=now,expires_at=now+29000)
                patient.put(f'{ROOT}/commands/{hid}/both1',c)
                ack=until(lambda:patient.get(f'{ROOT}/acks/{hid}/both1'));assert ack['status']=='accepted',ack
                sid=ack['session_id']
                summary=until(lambda:patient.get(f'{ROOT}/sessions/{sid}/summary'),30)
                until(lambda:store.count()==0)
                events=patient.get(f'{ROOT}/sessions/{sid}/events')
                points=patient.get(f'{ROOT}/sessions/{sid}/points')
                assert summary['reps']==15 and summary['completed_sets']==3 and summary['error']=='goal_complete',summary
                assert summary['requested_side']=='both' and summary['algorithm_version'].endswith('+bilateral1')
                assert len(events)==15 and all('rom_left_deg' in e and 'rom_right_deg' in e for e in events.values())
                assert any('angle_left' in p and 'angle_right' in p for p in points.values())
                assert patient.get(f'{ROOT}/patientSessions/{p1}/{sid}')['reps']==15
                assert doctor.get(f'{ROOT}/sessions/{sid}/summary')==summary
                for k,e in events.items():device.put(f'{ROOT}/sessions/{sid}/events/{k}',e)
                assert len(patient.get(f'{ROOT}/sessions/{sid}/events'))==15
                print(json.dumps(dict(test='bilateral_detector_cloud_e2e',passed=True,reps=15,sets=3,per_side_angles=True,physical_motion_acceptance=False)))
            finally:hub.close();store.close()

if __name__=='__main__':main()
