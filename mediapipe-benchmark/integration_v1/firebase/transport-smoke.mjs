// Loopback emulator only. Never creates accounts or writes to a cloud project.
import {initializeTestEnvironment} from '@firebase/rules-unit-testing';
import {ref,set,get} from 'firebase/database';
import {spawn} from 'node:child_process';
import {readFileSync} from 'node:fs';
if(process.env.FIREBASE_DATABASE_EMULATOR_HOST!=='127.0.0.1:9000')throw new Error('Emulator required');
const email=`pi-${Date.now()}@integration.invalid`,password='emulator-only-test-password';
const response=await fetch('http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1/accounts:signUp?key=demo-key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password,returnSecureToken:true})});
const account=await response.json();if(!account.localId)throw new Error('Emulator signup failed');
const env=await initializeTestEnvironment({projectId:'demo-smart-rehab',database:{host:'127.0.0.1',port:9000,rules:readFileSync(new URL('database.rules.json',import.meta.url),'utf8')}});
try{
 await env.withSecurityRulesDisabled(c=>set(ref(c.database(),'demo_e2e_v1/grants/transport_smoke'),{device_uid:account.localId,owner_uid:'patient',viewers:{doctor:true}}));
 await env.withSecurityRulesDisabled(c=>set(ref(c.database(),'demo_e2e_v1/grants/transport_outage'),{device_uid:account.localId,owner_uid:'patient',viewers:{doctor:true}}));
 const child=spawn('python3',['-m','integration_v1.transport_smoke'],{cwd:new URL('../..',import.meta.url),stdio:['pipe','inherit','inherit']});
 child.stdin.end(JSON.stringify({email,password,api_key:'demo-key',emulator:true,database_url:'http://127.0.0.1:9000'}));
 const code=await new Promise(resolve=>child.on('exit',resolve));if(code!==0)throw new Error('Python publisher failed');
 const snapshot=await get(ref(env.authenticatedContext('doctor').database(),'demo_e2e_v1/sessions/transport_smoke'));
 if(snapshot.child('latest/reps').val()!==1||snapshot.child('summary/reps').val()!==1||snapshot.child('events').size!==1)throw new Error('End-to-end mismatch');
 console.log('PYTHON_TO_FIREBASE_EMULATOR_TO_VIEWER_READ_OK (synthetic; not Pi/cloud measurement)');
 const outage=await get(ref(env.authenticatedContext('doctor').database(),'demo_e2e_v1/sessions/transport_outage'));
 if(outage.child('summary/reps').val()!==3 || outage.child('events').size!==3)throw new Error('Outage recovery duplicated or lost events');
 console.log('REAL_30_SECOND_PUBLISHER_PAUSE_RECOVERY_OK (synthetic emulator transport test; not real Internet outage)');
}finally{await env.cleanup()}
