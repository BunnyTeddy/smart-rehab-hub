"""Executed by emulator harness; synthetic transport check, never a Pi benchmark."""
import json
import sys
import tempfile
import time
from pathlib import Path
from .storage import Journal
from .transport import FirebaseClient,Publisher

def main():
    config=json.load(sys.stdin)
    if not config.get('emulator'):raise ValueError('Only emulator credentials accepted')
    client=FirebaseClient(config)
    with tempfile.TemporaryDirectory(prefix='rehab-publisher-test-') as directory:
        journal=Journal(Path(directory)/'outbox.sqlite3');pub=Publisher(client,journal,'transport_smoke')
        now=time.time_ns()//1000000
        packet={'schema_version':2,'session_id':'transport_smoke','exercise':'squat','sequence':1,'sample_timestamp_ms':1000,
                'frame_received_epoch_ms':now,'angle':160.,'reps':1,'phase':'READY','side':'left',
                'tracking_status':'tracking','form_status':'not_evaluated','source':'replay'}
        journal.enqueue('meta',{'session_id':'transport_smoke','exercise':'squat','source':'replay','schema_version':2,'created_at':now,'form_status':'not_evaluated'})
        pub.offer(packet);assert pub.step()
        event={'id':'transport_smoke:rep:1','rep':1,'start_ms':100,'target_ms':500,'end_ms':1000,'duration_ms':900,
               'min_angle_deg':100,'max_angle_deg':160,'rom_deg':60}
        journal.enqueue('events/rep_000001',event);assert pub.step()
        # Force an actual token renewal path (emulator signs in again; production uses refresh_token).
        client.expires=0;client.authenticate()
        # Exercise HTTP retries of the SAME immutable event against real emulator Rules.
        assert pub.send('events/rep_000001',event)
        journal.enqueue('summary',{'session_id':'transport_smoke','exercise':'squat','status':'completed','reps':1,'ended_at':now+1000})
        assert pub.step();assert journal.remaining()==0
        journal.close()
    print('PYTHON_PUBLISHER_REAL_HTTP_OK')
    with tempfile.TemporaryDirectory(prefix='rehab-outage-test-') as directory:
        journal=Journal(Path(directory)/'outbox.sqlite3')
        pub=Publisher(client,journal,'transport_outage')
        pub.schedule_pause(0,30)
        pub.start();started=time.monotonic();sequence=0
        # Continue local acquisition offers and durable events during the pause.
        for rep in range(1,4):
            event={'id':f'transport_outage:rep:{rep}','rep':rep,'start_ms':rep*1000,'target_ms':rep*1000+200,
                   'end_ms':rep*1000+600,'duration_ms':600,'min_angle_deg':100,'max_angle_deg':160,'rom_deg':60}
            journal.enqueue(f'events/rep_{rep:06d}',event)
        while time.monotonic()-started < 31:
            sequence+=1;now=time.time_ns()//1000000
            pub.offer({**packet,'session_id':'transport_outage','sequence':sequence,'sample_timestamp_ms':sequence*100,
                       'frame_received_epoch_ms':now,'reps':3})
            if time.monotonic()-started < 29:
                assert pub.successes==0 and journal.remaining()==3
            time.sleep(.1)
        deadline=time.monotonic()+5
        while journal.remaining() and time.monotonic()<deadline:time.sleep(.1)
        assert journal.remaining()==0
        assert len(pub.fault_history)==2
        measured_pause=pub.fault_history[1]['monotonic_s']-pub.fault_history[0]['monotonic_s']
        assert 29.9 <= measured_pause < 32
        # Stop producer before immutable summary; reconnect must not mint events.
        assert pub.close()
        assert pub.send('events/rep_000003',event)
        journal.enqueue('summary',{'session_id':'transport_outage','exercise':'squat','status':'completed','reps':3,'ended_at':time.time_ns()//1000000})
        assert pub.step();assert journal.remaining()==0
        journal.close()
        print(json.dumps({'synthetic_outage_measured_s':measured_pause,'local_samples_offered':sequence,'event_ids':3}))

if __name__=='__main__':main()
