"""Generate product-only rules; deployment merges these with the live rules."""
import json
from pathlib import Path
from product_v1.catalog import EXERCISE_CATALOG, LEGACY_EXERCISES


def immutable(fields):
    return '(!data.exists() || (' + ' && '.join(
        f"newData.child('{k}').val() === data.child('{k}').val()" for k in fields) + '))'


def fields(spec):
    return {**{k: {'.validate': v} for k, v in spec.items()}, '$other': {'.validate': False}}


def product_rules():
    signed = 'auth != null'
    patient = "auth != null && (auth.token.role == null || auth.token.role === 'patient')"
    hub = "auth != null && auth.token.role === 'hub' && auth.token.hub_id === $hub && root.child('rehab_v1/hubs').child($hub).child('device_uid').val() === auth.uid"
    owner = "auth != null && root.child('rehab_v1/hubs').child($hub).child('owner_uid').val() === auth.uid"
    access = "auth != null && (auth.uid === $patient || (auth.token.role === 'doctor' && root.child('rehab_v1/careLinks').child(auth.uid).child($patient).val() === true))"
    session_patient = "root.child('rehab_v1/sessions').child($sid).child('meta/patient_uid').val()"
    session_hub = "root.child('rehab_v1/sessions').child($sid).child('meta/hub_id').val()"
    writer = f"auth != null && auth.token.role === 'hub' && auth.token.hub_id === {session_hub} && root.child('rehab_v1/hubs').child(auth.token.hub_id).child('device_uid').val() === auth.uid"
    reader = f"auth != null && (auth.uid === {session_patient} || (auth.token.role === 'doctor' && root.child('rehab_v1/careLinks').child(auth.uid).child({session_patient}).val() === true) || ({writer}))"
    text = 'newData.isString() && newData.val().length <= 200'
    number = 'newData.isNumber() && newData.val() >= 0'
    integer = number + ' && newData.val() % 1 === 0'
    exercise = " || ".join(f"newData.val() === '{k}'" for k in EXERCISE_CATALOG)
    meta_fields = ['session_id', 'hub_id', 'patient_uid', 'exercise', 'duration_s', 'schema_version', 'algorithm_version', 'created_at', 'source', 'form_status']
    summary_fields = ['session_id', 'hub_id', 'patient_uid', 'exercise', 'status', 'error', 'reps', 'started_at', 'ended_at', 'elapsed_s', 'tracking_s', 'measured_samples', 'inference_fps', 'algorithm_p95_ms', 'max_temperature_c', 'throttled', 'form_status']
    event_fields = ['id', 'rep', 'start_ms', 'target_ms', 'end_ms', 'duration_ms', 'min_angle_deg', 'max_angle_deg', 'rom_deg']
    latest_specs = {
        'schema_version': 'newData.val() === 2', 'algorithm_version': text,
        'session_id': 'newData.val() === $sid', 'exercise': exercise,
        'sequence': integer + ' && newData.val() >= 1', 'sample_timestamp_ms': number,
        'timestamp': 'newData.isNumber() && newData.val() <= now + 5000 && newData.val() >= now - 5000',
        'frame_received_epoch_ms': 'newData.isNumber() && newData.val() <= now + 5000 && newData.val() >= now - 5000',
        'angle': 'newData.isNumber() && newData.val() >= 0 && newData.val() <= 180',
        'raw_angle': 'newData.isNumber() && newData.val() >= 0 && newData.val() <= 180',
        'visibility': 'newData.isNumber() && newData.val() >= 0 && newData.val() <= 1',
        'side': "newData.val() === 'left' || newData.val() === 'right' || newData.val() === 'both'",
        'phase': "newData.val() === 'WAIT_START' || newData.val() === 'READY' || newData.val() === 'OUTBOUND' || newData.val() === 'AT_TARGET' || newData.val() === 'RETURNING'",
        'tracking_status': "newData.val() === 'tracking' || newData.val() === 'lost' || newData.val() === 'selecting_side'",
        'reps': integer, 'form_status': "newData.val() === 'not_evaluated'",
        'reason': text, 'joint': text, 'source': "newData.val() === 'camera'",
        'inference_complete_epoch_ms': number, 'algorithm_complete_epoch_ms': number,
    }
    rules = {
        'doctorDirectory': {'$doctor': {'.read': signed, '.write': False}},
        'patients': {'$patient': {
            'profile': {'.read': access, '.write': patient + ' && auth.uid === $patient && newData.exists()',
                '.validate': "newData.hasChildren(['name','updated_at'])",
                **fields({'name': 'newData.isString() && newData.val().length > 0 && newData.val().length <= 100', 'updated_at': number})},
        }},
        'careLinks': {'$doctor': {
            '.read': "auth != null && auth.uid === $doctor && auth.token.role === 'doctor'",
            '$patient': {'.read': 'auth != null && auth.uid === $patient',
                '.write': patient + " && auth.uid === $patient && (!newData.exists() || root.child('rehab_v1/doctorDirectory').child($doctor).exists())",
                '.validate': 'newData.val() === true'},
        }},
        'patientDoctors': {'$patient': {'.read': 'auth != null && auth.uid === $patient',
            '$doctor': {'.write': patient + ' && auth.uid === $patient', '.validate': "newData.val() === true && root.child('rehab_v1/doctorDirectory').child($doctor).exists()"}}},
        'hubs': {'$hub': {
            '.read': '(' + hub + ') || (' + owner + ')',
            'owner_uid': {'.write': hub + " && newData.isString() && (!data.exists() || newData.val() === data.val())",
                '.validate': "root.child('rehab_v1/patients').child(newData.val()).child('profile').exists() && (!newData.parent().parent().parent().child('patientHub').child(newData.val()).exists() || newData.parent().parent().parent().child('patientHub').child(newData.val()).val() === $hub)"},
        }},
        'patientHub': {'$patient': {'.read': 'auth != null && auth.uid === $patient',
            '.write': "auth != null && auth.token.role === 'hub' && newData.val() === auth.token.hub_id && root.child('rehab_v1/hubs').child(auth.token.hub_id).child('device_uid').val() === auth.uid && newData.parent().parent().child('hubs').child(auth.token.hub_id).child('owner_uid').val() === $patient && (!data.exists() || newData.val() === data.val())"}},
        'hubState': {'$hub': {'.read': '(' + hub + ') || (' + owner + ')', '.write': hub,
            '.validate': "newData.hasChildren(['state','updated_at','version'])",
            **fields({'state': "newData.val() === 'idle' || newData.val() === 'preparing' || newData.val() === 'aligning' || newData.val() === 'running' || newData.val() === 'stopping' || newData.val() === 'error'",
                'updated_at': number, 'version': text, 'session_id': text, 'exercise': exercise,
                'reason': text, 'audio_ready': 'newData.isBoolean()', 'display_ready': 'newData.isBoolean()', 'ready': 'newData.isBoolean()'})}},
        'commands': {'$hub': {'.read': '(' + hub + ') || (' + owner + ')', '.indexOn': ['created_at'], '$command': {
            '.write': '(' + patient + ') && (' + owner + ') && !data.exists() && newData.exists()',
            '.validate': "newData.hasChildren(['action','patient_uid','created_at','expires_at']) && newData.child('patient_uid').val() === auth.uid && newData.child('created_at').val() >= now - 5000 && newData.child('created_at').val() <= now + 5000 && newData.child('expires_at').val() > now && newData.child('expires_at').val() <= newData.child('created_at').val() + 30000 && ((newData.child('action').val() === 'start' && newData.hasChildren(['exercise','duration_s'])) || (newData.child('action').val() === 'stop' && newData.child('session_id').val() === root.child('rehab_v1/hubState').child($hub).child('session_id').val()))",
            **fields({'action': "newData.val() === 'start' || newData.val() === 'stop'", 'patient_uid': text,
                'created_at': number, 'expires_at': number, 'exercise': exercise,
                'duration_s': 'newData.val() === 180 || newData.val() === 300 || newData.val() === 600', 'session_id': text})}}},
        'acks': {'$hub': {'.read': '(' + hub + ') || (' + owner + ')', '$command': {
            '.write': hub + ' && newData.exists() && ' + immutable(['status', 'session_id', 'reason', 'at']),
            '.validate': "newData.hasChildren(['status','at'])",
            **fields({'status': "newData.val() === 'accepted' || newData.val() === 'rejected'", 'session_id': text, 'reason': text, 'at': number})}}},
        'sessions': {'$sid': {
            '.read': reader,
            'meta': {'.write': "auth != null && auth.token.role === 'hub' && auth.token.hub_id === newData.child('hub_id').val() && root.child('rehab_v1/hubs').child(auth.token.hub_id).child('device_uid').val() === auth.uid && root.child('rehab_v1/hubs').child(auth.token.hub_id).child('owner_uid').val() === newData.child('patient_uid').val() && newData.exists() && " + immutable(meta_fields),
                '.validate': "newData.hasChildren(['session_id','hub_id','patient_uid','exercise','duration_s','created_at','schema_version','source','form_status']) && newData.child('session_id').val() === $sid && newData.child('schema_version').val() === 2 && newData.child('source').val() === 'camera' && newData.child('form_status').val() === 'not_evaluated'",
                **fields({k: exercise if k == 'exercise' else integer if k in ('duration_s','created_at','schema_version') else text for k in meta_fields})},
            'latest': {'.write': writer + " && newData.exists() && !root.child('rehab_v1/sessions').child($sid).child('summary').exists()",
                '.validate': "newData.hasChildren(['schema_version','session_id','exercise','sequence','sample_timestamp_ms','timestamp','frame_received_epoch_ms','reps','phase','tracking_status','form_status','source']) && newData.child('exercise').val() === root.child('rehab_v1/sessions').child($sid).child('meta/exercise').val() && (!data.exists() || (newData.child('sequence').val() > data.child('sequence').val() && newData.child('sample_timestamp_ms').val() > data.child('sample_timestamp_ms').val() && newData.child('reps').val() >= data.child('reps').val() && (!data.child('side').exists() || newData.child('side').val() === data.child('side').val()))) && (newData.child('tracking_status').val() !== 'tracking' || (newData.child('angle').isNumber() && newData.child('side').isString())) && (newData.child('tracking_status').val() === 'tracking' || !newData.child('angle').exists())",
                **fields(latest_specs)},
            'points': {'$point': {'.write': writer + ' && newData.exists() && ' + immutable(['t_ms','angle','tracking_status']),
                '.validate': "newData.hasChildren(['t_ms','tracking_status'])",
                **fields({'t_ms': number, 'angle': latest_specs['angle'], 'tracking_status': latest_specs['tracking_status']})}},
            'events': {'$event': {'.write': writer + ' && newData.exists() && ' + immutable(event_fields),
                '.validate': "newData.hasChildren(['id','rep','start_ms','target_ms','end_ms','duration_ms','rom_deg']) && newData.child('rep').val() >= 1 && newData.child('start_ms').val() <= newData.child('target_ms').val() && newData.child('target_ms').val() <= newData.child('end_ms').val()",
                **fields({k: text if k == 'id' else number for k in event_fields})}},
            'summary': {'.write': writer + ' && newData.exists() && ' + immutable(summary_fields),
                '.validate': "newData.hasChildren(['session_id','patient_uid','hub_id','exercise','status','reps','ended_at','elapsed_s','tracking_s']) && newData.child('session_id').val() === $sid && newData.child('patient_uid').val() === " + session_patient + " && newData.child('hub_id').val() === " + session_hub + " && newData.child('exercise').val() === root.child('rehab_v1/sessions').child($sid).child('meta/exercise').val() && (!root.child('rehab_v1/sessions').child($sid).child('latest').exists() || newData.child('reps').val() >= root.child('rehab_v1/sessions').child($sid).child('latest/reps').val())",
                **fields({k: exercise if k == 'exercise' else number if k in ('reps','started_at','ended_at','elapsed_s','tracking_s','measured_samples','inference_fps','algorithm_p95_ms','max_temperature_c') else text for k in summary_fields})},
        }},
        'patientSessions': {'$patient': {'.read': access, '.indexOn': ['created_at'], '$sid': {
            '.write': writer + " && newData.exists() && " + session_patient + ' === $patient',
            '.validate': "newData.hasChildren(['session_id','exercise','created_at','status','reps']) && newData.child('session_id').val() === $sid && newData.child('exercise').val() === root.child('rehab_v1/sessions').child($sid).child('meta/exercise').val() && (!data.exists() || newData.child('created_at').val() === data.child('created_at').val())",
            **fields({'session_id': text, 'exercise': exercise, 'created_at': number, 'status': text, 'reps': integer,
                'elapsed_s': number, 'tracking_s': number, 'ended_at': number})}}},
        'comments': {'$sid': {'.read': reader, '$doctor': {
            '.write': "auth != null && auth.uid === $doctor && auth.token.role === 'doctor' && root.child('rehab_v1/careLinks').child($doctor).child(" + session_patient + ").val() === true && newData.exists()",
            '.validate': "newData.hasChildren(['text','updated_at','doctor_name'])",
            **fields({'text': 'newData.isString() && newData.val().length > 0 && newData.val().length <= 4000', 'updated_at': number, 'doctor_name': text})}}},
    }

    # Version 2 fields are additive. Read/write principals above stay unchanged.
    goal_spec = fields({
        'mode': "newData.val() === 'time' || newData.val() === 'sets'",
        'duration_s': integer + ' && newData.val() >= 60 && newData.val() <= 600 && newData.val() % 60 === 0',
        'reps_per_set': "newData.val() === 5 || newData.val() === 10 || newData.val() === 15",
        'sets': "newData.val() === 1 || newData.val() === 2 || newData.val() === 3",
        'rest_s': integer + ' && newData.val() >= 15 && newData.val() <= 120 && newData.val() % 15 === 0',
    })
    goal_valid = "((newData.child('mode').val() === 'time' && newData.hasChildren(['mode','duration_s']) && !newData.child('reps_per_set').exists() && !newData.child('sets').exists() && !newData.child('rest_s').exists()) || (newData.child('mode').val() === 'sets' && newData.hasChildren(['mode','reps_per_set','sets','rest_s']) && !newData.child('duration_s').exists()))"
    goal_node = {'.validate': goal_valid, **goal_spec}
    side = "newData.val() === 'auto' || newData.val() === 'left' || newData.val() === 'right' || newData.val() === 'both'"
    workload = "newData.val() === 'aligning' || newData.val() === 'working' || newData.val() === 'resting' || newData.val() === 'complete'"
    progress_spec = {
        'goal': goal_node, 'requested_side': {'.validate': side},
        'workload_phase': {'.validate': workload}, 'set_number': {'.validate': integer + ' && newData.val() >= 1 && newData.val() <= 3'},
        'rep_in_set': {'.validate': integer}, 'completed_sets': {'.validate': integer + ' && newData.val() <= 3'},
        'remaining_s': {'.validate': number}, 'rest_remaining_s': {'.validate': number + ' && newData.val() <= 120'},
        'elapsed_s': {'.validate': number}, 'active_s': {'.validate': number},
    }
    hs=rules['hubState']['$hub']
    hs.update(progress_spec)
    hs['capabilities']={'.validate': "newData.hasChildren(['protocol_version','catalog_version','exercises','modes'])",
        **fields({'protocol_version': 'newData.val() === 2', 'catalog_version': text})}
    hs['capabilities']['exercises']=fields({k:'newData.isBoolean()' for k in EXERCISE_CATALOG})
    hs['capabilities']['modes']=fields({'time':'newData.isBoolean()', 'sets':'newData.isBoolean()'})
    hs['capabilities']['bilateral']=fields({k:'newData.isBoolean()' for k in EXERCISE_CATALOG})
    command=rules['commands']['$hub']['$command']
    legacy_ex = "(" + " || ".join(f"newData.child('exercise').val() === '{k}'" for k in LEGACY_EXERCISES) + ")"
    auto_ex = "(" + " || ".join(f"newData.child('exercise').val() === '{k}'" for k,v in EXERCISE_CATALOG.items() if v['side_mode']=='auto') + ")"
    required_ex = "(" + " || ".join(f"newData.child('exercise').val() === '{k}'" for k,v in EXERCISE_CATALOG.items() if v['side_mode']=='required') + ")"
    both_ex = "(" + " || ".join(f"newData.child('exercise').val() === '{k}'" for k,v in EXERCISE_CATALOG.items() if v.get('bilateral')) + ")"
    legacy = f"(!newData.child('protocol_version').exists() && {legacy_ex} && (newData.child('duration_s').val() === 180 || newData.child('duration_s').val() === 300 || newData.child('duration_s').val() === 600) && !newData.child('goal').exists() && !newData.child('requested_side').exists())"
    modern = f"(newData.child('protocol_version').val() === 2 && newData.hasChildren(['goal','requested_side']) && !newData.child('duration_s').exists() && (({auto_ex} && newData.child('requested_side').val() === 'auto') || ({required_ex} && (newData.child('requested_side').val() === 'left' || newData.child('requested_side').val() === 'right')) || ({both_ex} && newData.child('requested_side').val() === 'both' && root.child('rehab_v1/hubState').child($hub).child('capabilities/bilateral').child(newData.child('exercise').val()).val() === true)))"
    base_command = "newData.hasChildren(['action','patient_uid','created_at','expires_at']) && newData.child('patient_uid').val() === auth.uid && newData.child('created_at').val() >= now - 5000 && newData.child('created_at').val() <= now + 5000 && newData.child('expires_at').val() > now && newData.child('expires_at').val() <= newData.child('created_at').val() + 30000"
    command['.validate']=base_command + f" && ((newData.child('action').val() === 'start' && newData.child('exercise').exists() && !newData.child('session_id').exists() && ({legacy} || {modern})) || (newData.child('action').val() === 'stop' && newData.child('session_id').isString() && newData.child('session_id').val() === root.child('rehab_v1/hubState').child($hub).child('session_id').val() && !newData.child('exercise').exists() && !newData.child('goal').exists() && !newData.child('duration_s').exists() && !newData.child('requested_side').exists() && !newData.child('protocol_version').exists()))"
    command.update({'goal': goal_node, 'requested_side': {'.validate': side}, 'protocol_version': {'.validate': 'newData.val() === 2'}})
    session=rules['sessions']['$sid']
    new_meta_fields=['protocol_version','requested_side','preset_version','catalog_version']
    session['meta'].update(fields({k: 'newData.val() === 1 || newData.val() === 2' if k=='protocol_version' else side if k=='requested_side' else text for k in new_meta_fields}))
    session['meta']['goal']=goal_node
    goal_paths=['goal/'+k for k in ('mode','duration_s','reps_per_set','sets','rest_s')]
    session['meta']['.write'] += ' && ' + immutable(new_meta_fields+goal_paths)
    session['latest'].update(progress_spec)
    for key in ('angle_left', 'angle_right'):
        session['latest'][key] = {'.validate': latest_specs['angle']}
    session['latest']['.validate'] += " && (newData.child('side').val() !== 'both' || (root.child('rehab_v1/sessions').child($sid).child('meta/requested_side').val() === 'both' && (newData.child('tracking_status').val() !== 'tracking' || newData.hasChildren(['angle_left','angle_right']))))"
    # Measurements can never change the goal or requested body side of their session.
    session['latest']['.validate'] += " && (!newData.child('goal').exists() || (" + ' && '.join(f"newData.child('{k}').val() === root.child('rehab_v1/sessions').child($sid).child('meta/{k}').val()" for k in goal_paths) + ")) && (!newData.child('requested_side').exists() || newData.child('requested_side').val() === root.child('rehab_v1/sessions').child($sid).child('meta/requested_side').val())"
    point= session['points']['$point']
    point.update({'workload_phase': {'.validate': workload}, 'set_number': progress_spec['set_number']})
    point.update(fields({'reason': text, 'phase': latest_specs['phase'], 'angle_left': latest_specs['angle'], 'angle_right': latest_specs['angle']}))
    point['.write']+=' && '+immutable(['workload_phase','set_number','reason','phase','angle_left','angle_right'])
    event=session['events']['$event']
    event.update({'set_number':progress_spec['set_number'],'rep_in_set':{'.validate':integer+' && newData.val() >= 1'}})
    event['.write']+=' && '+immutable(['set_number','rep_in_set'])
    bilateral_event_fields = [s+'_'+bound+'_angle_deg' for s in ('left','right') for bound in ('min','max')] + ['rom_left_deg','rom_right_deg']
    event.update(fields({k: latest_specs['angle'] for k in bilateral_event_fields}))
    event['.write']+=' && '+immutable(bilateral_event_fields)
    summary=session['summary']
    summary.update({'goal':goal_node,'requested_side':{'.validate':side},'algorithm_version':{'.validate':text},
                    'completed_sets':progress_spec['completed_sets'], 'active_s':{'.validate':number},
                    'rest_s':{'.validate':number}, 'aligning_s':{'.validate':number}})
    set_fields={'set_number':integer+' && newData.val() >= 1 && newData.val() <= 3','reps':integer+' && newData.val() <= 15',
                'completed':'newData.isBoolean()','active_s':number,'started_at':number,'ended_at':number}
    summary['set_results']={'$set':{'.validate':"($set === 'set001' || $set === 'set002' || $set === 'set003') && newData.hasChildren(['set_number','reps','completed','active_s','started_at'])",**fields(set_fields)}}
    summary['.write']+=' && '+immutable(goal_paths+['requested_side','algorithm_version','completed_sets','active_s','rest_s','aligning_s']+[f'set_results/set{i:03d}/{k}' for i in range(1,4) for k in set_fields])
    index=rules['patientSessions']['$patient']['$sid']
    index.update({'goal':goal_node,'requested_side':{'.validate':side},'algorithm_version':{'.validate':text},
                  'completed_sets':progress_spec['completed_sets'],'active_s':{'.validate':number}})
    return rules



def generate():
    base = Path(__file__).resolve().parents[2]
    original = json.loads((base / 'integration_v1/firebase/database.rules.json').read_text())
    original['rules']['rehab_v1'] = product_rules()
    target = Path(__file__).with_name('database.rules.json')
    target.write_text(json.dumps(original, ensure_ascii=False, indent=2) + '\n')
    return target


if __name__ == '__main__':
    print(generate())
