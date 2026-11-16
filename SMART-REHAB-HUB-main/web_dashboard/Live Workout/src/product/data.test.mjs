import {test} from 'node:test';
import assert from 'node:assert/strict';
import {statistics,dailyTrend,anglePoints,missingSegments,filterSessions,workloadSegments} from './data.js';
test('statistics uses finalized sessions only and filters exercise',()=>{
 const data=[{exercise:'squat',ended_at:1,reps:5,elapsed_s:180},{exercise:'biceps_curl',ended_at:2,reps:8,elapsed_s:120},{exercise:'squat',reps:3,elapsed_s:100}];
 assert.deepEqual(statistics(data),{sessions:2,seconds:300,reps:13});
 assert.deepEqual(statistics(data,'squat'),{sessions:1,seconds:180,reps:5});
});
test('daily trend uses Vietnam day and never invents a recovery score',()=>{
 const data=[{created_at:Date.parse('2026-10-04T18:00:00Z'),ended_at:1,reps:5,elapsed_s:180,exercise:'squat'}];
 assert.deepEqual(dailyTrend(data),[{day:'2026-10-05',reps:5,minutes:3,sessions:1}]);
});
test('missing pose and missing timestamps break lines',()=>{
 const data={a:{t_ms:0,angle:150,tracking_status:'tracking'},b:{t_ms:1000,tracking_status:'lost'},c:{t_ms:2000,angle:90,tracking_status:'tracking'},d:{t_ms:6000,angle:150,tracking_status:'tracking'}};
 assert.equal(anglePoints(data).filter(p=>p.y===null).length,2);
 assert.deepEqual(missingSegments(data),[{from:1000,to:2000},{from:2000,to:6000}]);
});

test('set and time filters use real side, and active time excludes rest',()=>{
 const data=[{exercise:'squat',elapsed_s:90,reps:4,ended_at:1,created_at:1},{exercise:'shoulder_flexion',requested_side:'left',goal:{mode:'sets'},elapsed_s:90,active_s:30,reps:5,ended_at:1,created_at:1}];
 assert.equal(filterSessions(data,{mode:'time'}).length,1);
 assert.equal(filterSessions(data,{side:'left',mode:'sets'})[0].exercise,'shoulder_flexion');
 assert.equal(statistics(data).seconds,120);
});
test('rest with missing joints is distinct from tracking loss and remains a chart gap',()=>{
 const points={a:{t_ms:0,angle:160,tracking_status:'tracking',workload_phase:'working'},b:{t_ms:1000,tracking_status:'lost',workload_phase:'resting'},c:{t_ms:2000,tracking_status:'lost',workload_phase:'resting'},d:{t_ms:3000,tracking_status:'lost',workload_phase:'aligning'},e:{t_ms:4000,angle:160,tracking_status:'tracking',workload_phase:'working'},f:{t_ms:5000,tracking_status:'lost',workload_phase:'working'},g:{t_ms:6000,angle:160,tracking_status:'tracking',workload_phase:'working'}};
 assert.deepEqual(missingSegments(points),[{from:5000,to:6000}]);
 assert.deepEqual(workloadSegments(points,'resting'),[{from:1000,to:3000}]);
 assert.equal(anglePoints(points)[1].y,null);
});

test('both mode has two independent angle series and a distinct history filter',()=>{
 const points={a:{t_ms:0,angle:45,angle_left:30,angle_right:60,tracking_status:'tracking'},b:{t_ms:1000,angle_left:60,tracking_status:'lost'}};
 assert.deepEqual(anglePoints(points,'angle_left').map(p=>p.y),[30,null]);
 assert.deepEqual(anglePoints(points,'angle_right').map(p=>p.y),[60,null]);
 assert.equal(filterSessions([{requested_side:'both'},{requested_side:'left'}],{side:'both'}).length,1);
});
