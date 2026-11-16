from product_v1.display import Display
"""Runs the actual REST stream/outbox/lifecycle against Firebase emulators.

The injected engine is explicitly synthetic; this is not motion acceptance.
"""
import json
import tempfile
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from types import SimpleNamespace
from product_v1.cloud_client import Cloud
from product_v1.hub import Hub
from product_v1.state import Store
from product_v1.protocol import ROOT

PROJECT = 'demo-smart-rehab-product'
BASE = 'http://127.0.0.1:19000'


def admin(path, value):
    req = urllib.request.Request(f'{BASE}/{ROOT}/{path}.json?ns={PROJECT}', data=json.dumps(value).encode(), method='PUT', headers={'Authorization':'Bearer owner','Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r: return json.load(r)


def account(label, claims):
    email = f'{label}-{uuid.uuid4().hex[:8]}@fixture.invalid'
    body = {'email':email,'password':'EmulatorOnly2026!','returnSecureToken':True}
    base = 'http://127.0.0.1:19099/identitytoolkit.googleapis.com/v1/'
    def post(url,data):
        req=urllib.request.Request(url,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer owner'})
        with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
    user=post(base+'accounts:signUp?key=demo-key',body)
    post(base+f'projects/{PROJECT}/accounts:update',{'localId':user['localId'],'customAttributes':json.dumps(claims)})
    cloud=Cloud({'api_key':'demo-key','email':email,'password':body['password'],'emulator':True,'database_url':BASE})
    return user['localId'],cloud


def until(predicate, seconds=15):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=predicate()
        if value:return value
        time.sleep(.1)
    raise AssertionError('Timed out waiting for state')


def main():
    from product_v1.cloud.generate_rules import generate
    rule_request = urllib.request.Request(BASE + '/.settings/rules.json?ns=' + PROJECT,
        data=generate().read_bytes(), method='PUT', headers={'Authorization':'Bearer owner','Content-Type':'application/json'})
    with urllib.request.urlopen(rule_request, timeout=10) as response:
        response.read()
    hid='e2e_'+uuid.uuid4().hex[:10]
    p1,patient=account('patient',{}); p2,stranger=account('stranger',{})
    device_uid,device=account('device',{'role':'hub','hub_id':hid})
    doctor_uid,doctor=account('doctor',{'role':'doctor'})
    patient.put(f'{ROOT}/patients/{p1}/profile',{'name':'Emulator patient','updated_at':int(time.time()*1000)})
    admin('hubs/'+hid,{'device_uid':device_uid,'label':'Emulator hub'})
    assert device.verify_patient(patient.token()) == p1
    device.request('PATCH',ROOT,{f'hubs/{hid}/owner_uid':p1,f'patientHub/{p1}':hid})
    admin('doctorDirectory/'+doctor_uid,{'name':'Emulator doctor'})
    patient.put(f'{ROOT}/careLinks/{doctor_uid}/{p1}',True)
    completed=threading.Event()
    def engine(session,config,display,voice,stop,cloud,on_sample):
        for n in range(1,21):
            if stop.is_set(): break
            now=int(time.time()*1000)
            sample={'schema_version':2,'algorithm_version':'2.0.0','session_id':session.sid,'exercise':'squat','sequence':n,
                'sample_timestamp_ms':n*100,'timestamp':now,'frame_received_epoch_ms':now,'reps':0,'angle':160,'raw_angle':160,
                'side':'left','phase':'READY','tracking_status':'tracking','form_status':'not_evaluated','source':'camera'}
            session.sample(sample);on_sample(sample,session.phase);stop.wait(.1)
        completed.set();return 'duration_complete'
    voice=SimpleNamespace(ready=True,say=lambda _:None,close=lambda:None)
    display=Display(); display.ready=True
    with tempfile.TemporaryDirectory() as tmp:
        store=Store(Path(tmp)/'hub.db');store.set('owner_uid',p1)
        hub=Hub({'hub_id':hid},store,device,display,voice,engine);hub.start()
        until(lambda:device.last_success>0)
        now=int(time.time()*1000)
        command={'action':'start','patient_uid':p1,'exercise':'squat','duration_s':180,'created_at':now,'expires_at':now+29000}
        patient.put(f'{ROOT}/commands/{hid}/command1',command)
        ack=until(lambda:patient.get(f'{ROOT}/acks/{hid}/command1'))
        assert ack['status']=='accepted',ack
        sid=ack['session_id']
        hub.command('command1',command)
        assert store.acknowledgement('command1')['session_id']==sid
        until(lambda:patient.get(f'{ROOT}/sessions/{sid}/latest'))
        try:stranger.get(f'{ROOT}/sessions/{sid}');raise AssertionError('Cross-patient read allowed')
        except RuntimeError:pass
        assert completed.wait(10)
        summary=until(lambda:patient.get(f'{ROOT}/sessions/{sid}/summary'))
        until(lambda:store.count()==0)
        assert summary['reps']==0 and summary['status']=='completed'
        assert doctor.get(f'{ROOT}/sessions/{sid}/summary')==summary
        note={'text':'Emulator transport check','doctor_name':'Emulator doctor','updated_at':int(time.time()*1000)}
        doctor.put(f'{ROOT}/comments/{sid}/{doctor_uid}',note)
        assert patient.get(f'{ROOT}/comments/{sid}/{doctor_uid}')==note
        patient.request('DELETE',f'{ROOT}/careLinks/{doctor_uid}/{p1}')
        try:doctor.get(f'{ROOT}/sessions/{sid}');raise AssertionError('Revoked doctor allowed')
        except RuntimeError:pass
        assert patient.get(f'{ROOT}/patientSessions/{p1}/{sid}')['reps']==summary['reps']
        hub.close()
        print(json.dumps({'passed':True,'transport':'actual Firebase Auth/Rules/REST streaming/outbox',
                          'engine':'synthetic; not a physical acceptance run','session_id':sid,
                          'checks':['atomic pairing','SSE start and ack','duplicate start','latest','summary','history','cross-patient denial','doctor read','comment roundtrip','revoke']},ensure_ascii=False))


if __name__=='__main__':main()
