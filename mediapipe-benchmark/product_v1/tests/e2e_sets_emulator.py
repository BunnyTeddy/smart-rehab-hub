from product_v1.display import Display
"""Real Auth + RTDB stream + outbox, injected synthetic engine and accelerated set clock."""
import json
import tempfile
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from product_v1.tests.e2e_emulator import account, admin, until, BASE, PROJECT
from product_v1.hub import Hub
from product_v1.session import Session, epoch_ms
from product_v1.state import Store
from product_v1.protocol import ROOT


def main():
    from product_v1.tests.e2e_emulator import main as legacy
    legacy()
    hid='sets_'+uuid.uuid4().hex[:8]
    p1,patient=account('sets-patient',{});p2,stranger=account('sets-stranger',{})
    uid,device=account('sets-hub',{'role':'hub','hub_id':hid})
    did,doctor=account('sets-doctor',{'role':'doctor'})
    patient.put(f'{ROOT}/patients/{p1}/profile',{'name':'Synthetic set test','updated_at':epoch_ms()})
    admin('hubs/'+hid,{'device_uid':uid,'owner_uid':p1})
    admin('doctorDirectory/'+did,{'name':'Synthetic doctor'})
    patient.put(f'{ROOT}/careLinks/{did}/{p1}',True)
    clock=[0.0]
    def engine(session,config,display,voice,stop,cloud,on_sample):
        sequence=0
        def sample(event=False,allow=True):
            nonlocal sequence
            sequence+=1;clock[0]+=.2
            value=dict(schema_version=2,algorithm_version=session.meta['algorithm_version'],session_id=session.sid,
                       exercise=session.meta['exercise'],sequence=sequence,sample_timestamp_ms=int(clock[0]*1000),
                       frame_received_epoch_ms=epoch_ms(),side='left',phase='READY',tracking_status='tracking',
                       angle=10,raw_angle=10,visibility=1,reps=0,form_status='not_evaluated',source='camera',reason='ok',joint='shoulder')
            if event:value['rep_event']=dict(id='synthetic',rep=1,start_ms=int(clock[0]*1000)-150,target_ms=int(clock[0]*1000)-80,end_ms=int(clock[0]*1000),duration_ms=150,min_angle_deg=10,max_angle_deg=90,rom_deg=80)
            session.sample(value,allow_start=allow);on_sample(value,session.phase);stop.wait(.15)
        sample()
        for number in range(3):
            for _ in range(5):sample(event=True)
            if number<2:
                sample(event=True) # rest must ignore an accidental/synthetic event
                clock[0]+=15;session.tick();sample(event=True,allow=False);sample()
        return session.completion_reason
    voice=SimpleNamespace(ready=True,say=lambda _:None,close=lambda:None)
    display=Display(); display.ready=True
    goal=dict(mode='sets',reps_per_set=5,sets=3,rest_s=15)
    with tempfile.TemporaryDirectory() as tmp:
        store=Store(Path(tmp)/'db');store.set('owner_uid',p1)
        with patch('product_v1.hub.Session',lambda store,meta:Session(store,meta,monotonic=lambda:clock[0])):
            hub=Hub({'hub_id':hid},store,device,display,voice,engine);hub.start()
            try:
                until(lambda:device.last_success>0)
                now=epoch_ms();c=dict(action='start',patient_uid=p1,protocol_version=2,exercise='shoulder_abduction',requested_side='left',goal=goal,created_at=now,expires_at=now+29000)
                patient.put(f'{ROOT}/commands/{hid}/sets1',c)
                ack=until(lambda:patient.get(f'{ROOT}/acks/{hid}/sets1'));assert ack['status']=='accepted',ack
                sid=ack['session_id'];hub.command('sets1',c);assert hub.session.sid==sid
                summary=until(lambda:patient.get(f'{ROOT}/sessions/{sid}/summary'),30)
                until(lambda:store.count()==0)
                events=patient.get(f'{ROOT}/sessions/{sid}/events')
                history=patient.get(f'{ROOT}/patientSessions/{p1}/{sid}')
                assert summary['reps']==15 and summary['completed_sets']==3 and summary['error']=='goal_complete',summary
                assert len(events)==15 and [e['rep'] for e in events.values()]==list(range(1,16))
                assert [e['rep_in_set'] for e in events.values()]==list(range(1,6))*3
                assert history['reps']==summary['reps'] and history['goal']==summary['goal']==goal
                assert doctor.get(f'{ROOT}/sessions/{sid}/summary')==summary
                # Fixed paths are safe to resend after an ambiguous HTTP response.
                for k,e in events.items():device.put(f'{ROOT}/sessions/{sid}/events/{k}',e)
                assert len(patient.get(f'{ROOT}/sessions/{sid}/events'))==15
                for account_ in (stranger,):
                    try:account_.get(f'{ROOT}/sessions/{sid}');raise AssertionError('Cross-patient access')
                    except RuntimeError:pass
                note=dict(text='Set test comment',doctor_name='Synthetic doctor',updated_at=epoch_ms())
                doctor.put(f'{ROOT}/comments/{sid}/{did}',note);assert patient.get(f'{ROOT}/comments/{sid}/{did}')==note
                patient.request('DELETE',f'{ROOT}/careLinks/{did}/{p1}')
                try:doctor.get(f'{ROOT}/sessions/{sid}');raise AssertionError('Revoked doctor access')
                except RuntimeError:pass
                print(json.dumps(dict(test='synthetic_sets_cloud_e2e',passed=True,reps=summary['reps'],sets=summary['completed_sets'],event_count=len(events),history_matches=True,doctor_matches=True,physical_motion_acceptance=False)))
            finally:
                hub.close();store.close()

if __name__=='__main__':main()
