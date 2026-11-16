import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import {test, before, after, beforeEach} from 'node:test';
const require=createRequire(new URL('../../integration_v1/firebase/package.json',import.meta.url));
const {initializeTestEnvironment,assertFails,assertSucceeds}=require('@firebase/rules-unit-testing');
const {ref,set,get,remove,update}=require('firebase/database');
let env;
const claims={hub:{role:'hub',hub_id:'h1'},hub2:{role:'hub',hub_id:'h2'},doctor:{role:'doctor'},doctor2:{role:'doctor'}};
const db=uid=>uid?env.authenticatedContext(uid,claims[uid]||{}).database():env.unauthenticatedContext().database();
const root='rehab_v1';
const meta={session_id:'s1',hub_id:'h1',patient_uid:'p1',exercise:'squat',duration_s:180,schema_version:2,algorithm_version:'2.0.0',created_at:1000,source:'camera',form_status:'not_evaluated'};
const sample=extra=>({schema_version:2,session_id:'s1',exercise:'squat',sequence:1,sample_timestamp_ms:100,timestamp:Date.now(),frame_received_epoch_ms:Date.now(),reps:0,angle:160,side:'left',phase:'READY',tracking_status:'tracking',form_status:'not_evaluated',source:'camera',...extra});
const summary=extra=>({session_id:'s1',hub_id:'h1',patient_uid:'p1',exercise:'squat',status:'completed',reps:3,started_at:1000,ended_at:Date.now(),elapsed_s:180,tracking_s:150,form_status:'not_evaluated',...extra});
const put=(uid,path,value)=>set(ref(db(uid),root+'/'+path),value);
const read=(uid,path)=>get(ref(db(uid),root+'/'+path));
before(async()=>{env=await initializeTestEnvironment({projectId:'demo-smart-rehab-product',database:{host:'127.0.0.1',port:19000,rules:readFileSync(new URL('database.rules.json',import.meta.url),'utf8')}})});
beforeEach(async()=>{await env.clearDatabase();await env.withSecurityRulesDisabled(async c=>set(ref(c.database(),root),{
 hubs:{h1:{device_uid:'hub',owner_uid:'p1'},h2:{device_uid:'hub2',owner_uid:'p2'},unclaimed:{device_uid:'newhub'}},
 doctorDirectory:{doctor:{name:'Bác sĩ thử'},doctor2:{name:'Bác sĩ khác'}},careLinks:{doctor:{p1:true}},
 patients:{p1:{profile:{name:'Người thử A',updated_at:1000}},p2:{profile:{name:'Người thử B',updated_at:1000}}},
 sessions:{s1:{meta}},hubState:{h1:{state:'running',session_id:'s1',updated_at:Date.now(),version:'test'}}
}))});
after(async()=>env?.cleanup());
test('bilateral commands require supported exercise, updated hub and bound owner',async()=>{
 const c={action:'start',patient_uid:'p1',protocol_version:2,exercise:'shoulder_abduction',requested_side:'both',goal:{mode:'time',duration_s:180},created_at:Date.now(),expires_at:Date.now()+29000};
 await assertFails(put('p1','commands/h1/both-old',c));
 const capabilities={protocol_version:2,catalog_version:'1.1.1',exercises:{shoulder_abduction:true},modes:{time:true,sets:true},bilateral:{shoulder_abduction:true}};
 await assertSucceeds(put('hub','hubState/h1',{state:'idle',updated_at:Date.now(),version:'new',capabilities}));
 await assertSucceeds(put('p1','commands/h1/both-ok',c));
 await assertFails(put('p2','commands/h1/both-other',{...c,patient_uid:'p2'}));
 await assertFails(put('p1','commands/h1/both-leg',{...c,exercise:'standing_hip_abduction'}));
 await assertFails(put('p1','commands/h1/both-squat',{...c,exercise:'squat'}));
});
test('bilateral angles persist and remain immutable, authorization unchanged',async()=>{
 const m={...meta,session_id:'both',exercise:'shoulder_abduction',requested_side:'both',protocol_version:2,goal:{mode:'time',duration_s:180}};
 await assertSucceeds(put('hub','sessions/both/meta',m));
 const v=sample({session_id:'both',exercise:'shoulder_abduction',side:'both',requested_side:'both',angle:60,angle_left:55,angle_right:65});
 await assertSucceeds(put('hub','sessions/both/latest',v));
 await assertFails(put('hub','sessions/both/latest',{...v,sequence:2,sample_timestamp_ms:200,angle_right:null}));
 const point={t_ms:1000,tracking_status:'tracking',angle:60,angle_left:55,angle_right:65,reason:'ok',phase:'OUTBOUND'};
 await assertSucceeds(put('hub','sessions/both/points/p1',point));
 await assertSucceeds(put('hub','sessions/both/points/p1',point));
 await assertFails(put('hub','sessions/both/points/p1',{...point,angle_left:40}));
 for(const u of ['p1','doctor','hub'])await assertSucceeds(read(u,'sessions/both'));
 for(const u of ['p2','doctor2','hub2'])await assertFails(read(u,'sessions/both'));
});
test('patient, assigned doctor and own hub can read; everyone else denied',async()=>{
 for(const u of ['p1','doctor','hub'])await assertSucceeds(read(u,'sessions/s1'));
 for(const u of [null,'p2','doctor2','hub2'])await assertFails(read(u,'sessions/s1'));
 await assertFails(read('doctor','sessions'));await assertFails(read('p1','patients'));
});
test('role cannot be escalated from a profile or doctor directory',async()=>{
 await assertFails(put('p1','doctorDirectory/p1',{name:'Fake'}));
 await assertFails(put('p1','patients/p1/profile',{name:'A',updated_at:1,role:'doctor'}));
 await assertFails(put('doctor','patients/p1/profile',{name:'Edited',updated_at:1}));
 await assertSucceeds(put('p1','patients/p1/profile',{name:'Tên mới',updated_at:Date.now()}));
});
test('patient controls doctor grant and revocation immediately applies',async()=>{
 await assertSucceeds(put('p1','careLinks/doctor2/p1',true));await assertSucceeds(read('doctor2','sessions/s1'));
 await assertFails(put('doctor2','careLinks/doctor2/p2',true));await assertFails(put('p2','careLinks/doctor2/p1',true));
 await assertSucceeds(remove(ref(db('p1'),root+'/careLinks/doctor2/p1')));await assertFails(read('doctor2','sessions/s1'));
});
test('patient can revoke a doctor even after the directory entry is removed',async()=>{
 await env.withSecurityRulesDisabled(async c=>{
   await set(ref(c.database(),root+'/patientDoctors/p1/doctor'),true);
   await remove(ref(c.database(),root+'/doctorDirectory/doctor'));
 });
 await assertSucceeds(update(ref(db('p1'),root),{'careLinks/doctor/p1':null,'patientDoctors/p1/doctor':null}));
 await assertFails(read('doctor','sessions/s1'));
});
test('only bound owner can enqueue fresh bounded commands',async()=>{
 const c={action:'start',patient_uid:'p1',exercise:'squat',duration_s:180,created_at:Date.now(),expires_at:Date.now()+29000};
 await assertSucceeds(put('p1','commands/h1/c1',c));await assertFails(put('p1','commands/h1/c1',c));
 for(const u of ['p2','doctor','hub',null])await assertFails(put(u,'commands/h1/c2',{...c,patient_uid:u}));
 for(const change of [{expires_at:1},{duration_s:999},{exercise:'hanging_leg_raise'},{created_at:1},{shell:'bad'}])await assertFails(put('p1','commands/h1/c2',{...c,...change}));
});
test('stop targets the exact current session',async()=>{
 const c={action:'stop',patient_uid:'p1',session_id:'s1',created_at:Date.now(),expires_at:Date.now()+29000};
 await assertSucceeds(put('p1','commands/h1/stop1',c));await assertFails(put('p1','commands/h1/stop2',{...c,session_id:'s2'}));
});
test('a bound hub cannot be stolen or re-pointed',async()=>{
 await assertSucceeds(put('hub','hubs/h1/owner_uid','p1'));
 for(const u of ['hub','p1','p2','hub2'])await assertFails(put(u,'hubs/h1/owner_uid','p2'));
 await assertFails(put('hub','hubs/h1/device_uid','hub2'));
 await assertSucceeds(put('hub','patientHub/p1','h1'));await assertFails(put('hub','patientHub/p2','h1'));
});
test('atomic pairing binds the registry and patient index and cannot steal another patient hub',async()=>{
 await env.withSecurityRulesDisabled(async c=>{
   await remove(ref(c.database(),root+'/hubs/h2/owner_uid'));
   await set(ref(c.database(),root+'/patientHub/p1'),'h1');
 });
 await assertSucceeds(update(ref(db('hub2'),root),{'hubs/h2/owner_uid':'p2','patientHub/p2':'h2'}));
 await assertFails(update(ref(db('hub2'),root),{'hubs/h2/owner_uid':'p1','patientHub/p1':'h2'}));
});
test('hub can create only its owner sessions and cannot rewrite meta',async()=>{
 await assertSucceeds(put('hub','sessions/s2/meta',{...meta,session_id:'s2'}));
 await assertFails(put('hub','sessions/s3/meta',{...meta,session_id:'s3',patient_uid:'p2'}));
 await assertFails(put('hub','sessions/s1/meta',{...meta,exercise:'biceps_curl'}));
 await assertFails(put('p1','sessions/s3/meta',{...meta,session_id:'s3'}));
});
test('measurement contract rejects bad values, backwards sequence, changed side and images',async()=>{
 await assertSucceeds(put('hub','sessions/s1/latest',sample()));
 for(const change of [{sequence:1},{reps:-1},{side:'right'},{exercise:'biceps_curl'},{angle:181},{angle:null},{image:'bad'},{timestamp:1}])await assertFails(put('hub','sessions/s1/latest',sample({sequence:2,sample_timestamp_ms:200,...change})));
 await assertSucceeds(put('hub','sessions/s1/latest',sample({sequence:2,sample_timestamp_ms:200,angle:null,tracking_status:'lost'})));
 await assertFails(put('p1','sessions/s1/latest',sample()));
});
test('durable events and summaries are idempotent and immutable',async()=>{
 const e={id:'s1:rep:1',rep:1,start_ms:100,target_ms:600,end_ms:1200,duration_ms:1100,min_angle_deg:90,max_angle_deg:160,rom_deg:70};
 await assertSucceeds(put('hub','sessions/s1/events/rep_000001',e));await assertSucceeds(put('hub','sessions/s1/events/rep_000001',e));
 await assertFails(put('hub','sessions/s1/events/rep_000001',{...e,rep:2}));
 const s=summary();await assertSucceeds(put('hub','sessions/s1/summary',s));await assertSucceeds(put('hub','sessions/s1/summary',s));
 await assertFails(put('hub','sessions/s1/summary',{...s,reps:4}));await assertFails(put('hub','sessions/s1/latest',sample()));
 await assertFails(remove(ref(db('hub'),root+'/sessions/s1/summary')));
});
test('doctor comments require a current grant; patient reads but cannot edit',async()=>{
 const c={text:'Nhận xét thử',doctor_name:'Bác sĩ thử',updated_at:Date.now()};
 await assertSucceeds(put('doctor','comments/s1/doctor',c));await assertSucceeds(read('p1','comments/s1'));
 for(const u of ['p1','p2','hub','doctor2'])await assertFails(put(u,'comments/s1/'+u,c));
 await remove(ref(db('p1'),root+'/careLinks/doctor/p1'));await assertFails(put('doctor','comments/s1/doctor',c));
});
test('history indexes cannot publish someone else session',async()=>{
 const i={session_id:'s1',exercise:'squat',created_at:1000,status:'running',reps:0};
 await assertSucceeds(put('hub','patientSessions/p1/s1',i));await assertSucceeds(read('doctor','patientSessions/p1'));
 await assertFails(put('hub','patientSessions/p2/s1',i));await assertFails(put('p1','patientSessions/p1/s1',i));
});
test('root and legacy access remain denied',async()=>{
 for(const u of ['p1','doctor','hub',null])await assertFails(get(ref(db(u),'/')));
 await assertFails(set(ref(db('hub'),'sessions/legacy/latest'),sample()));
});
test('protocol 2 validates all exercises, sides and goals without changing ownership',async()=>{
 const now=Date.now(), c={action:'start',patient_uid:'p1',protocol_version:2,exercise:'shoulder_abduction',requested_side:'left',goal:{mode:'sets',reps_per_set:5,sets:3,rest_s:30},created_at:now,expires_at:now+29000};
 await assertSucceeds(put('p1','commands/h1/v2',c));
 for(const [i,change] of [{requested_side:'auto'},{protocol_version:3},{goal:{mode:'time',duration_s:61}},{goal:{mode:'sets',reps_per_set:4,sets:3,rest_s:30}},{goal:{mode:'sets',reps_per_set:5,sets:4,rest_s:30}},{goal:{mode:'sets',reps_per_set:5,sets:3,rest_s:31}},{goal:{mode:'time',duration_s:60,sets:1}},{goal:{mode:'time',duration_s:60,shell:'bad'}},{duration_s:180}].entries())await assertFails(put('p1',`commands/h1/bad${i}`,{...c,...change}));
 for(const u of ['p2','hub','doctor',null])await assertFails(put(u,`commands/h1/from${u}`,{...c,patient_uid:u}));
 for(const id of ['squat','sit_to_stand'])await assertSucceeds(put('p1',`commands/h1/${id}`,{...c,exercise:id,requested_side:'auto',goal:{mode:'time',duration_s:60}}));
 await assertFails(put('p1','commands/h1/wrongside',{...c,exercise:'squat',requested_side:'left'}));
});
test('capabilities, set progress and enriched summaries survive immutable retries',async()=>{
 const goal={mode:'sets',reps_per_set:5,sets:3,rest_s:30};
 const m={...meta,goal,protocol_version:2,requested_side:'auto',preset_version:'2.0.0',catalog_version:'1.1.0',duration_s:1800};
 await put('hub','sessions/s2/meta',{...m,session_id:'s2'});
 const v=sample({session_id:'s2',goal,requested_side:'auto',workload_phase:'resting',set_number:1,rep_in_set:5,completed_sets:1,remaining_s:1700,rest_remaining_s:30,elapsed_s:100,active_s:100,reps:5});
 await assertSucceeds(put('hub','sessions/s2/latest',v));
 await assertFails(put('hub','sessions/s2/latest',{...v,sequence:2,sample_timestamp_ms:200,goal:{...goal,sets:2}}));
 const e={id:'s2:rep:5',rep:5,set_number:1,rep_in_set:5,start_ms:100,target_ms:600,end_ms:1200,duration_ms:1100,rom_deg:70};
 await assertSucceeds(put('hub','sessions/s2/events/rep000005',e));await assertSucceeds(put('hub','sessions/s2/events/rep000005',e));
 await assertFails(put('hub','sessions/s2/events/rep000005',{...e,set_number:2}));
 const s=summary({session_id:'s2',goal,requested_side:'auto',algorithm_version:'2.0.0',completed_sets:1,active_s:100,rest_s:30,aligning_s:50,reps:5,status:'stopped',set_results:{set001:{set_number:1,reps:5,completed:true,active_s:100,started_at:1000,ended_at:2000}}});
 await assertSucceeds(put('hub','sessions/s2/summary',s));await assertSucceeds(put('hub','sessions/s2/summary',s));
 await assertFails(put('hub','sessions/s2/summary',{...s,set_results:{set001:{...s.set_results.set001,reps:4}}}));
 await assertSucceeds(read('doctor','sessions/s2'));await assertFails(read('p2','sessions/s2'));
 await assertSucceeds(put('hub','hubState/h1',{state:'running',session_id:'s2',version:'1.1.0-rc1',updated_at:Date.now(),workload_phase:'resting',goal,requested_side:'auto',set_number:1,rep_in_set:5,completed_sets:1,remaining_s:1700,rest_remaining_s:30,elapsed_s:100,active_s:100,capabilities:{protocol_version:2,catalog_version:'1.1.0',exercises:{squat:true,shoulder_abduction:true},modes:{time:true,sets:true}}}));
});
