export const exercises = {squat:'Squat', biceps_curl:'Biceps curl', shoulder_press:'Shoulder press', bent_over_row:'Bent-over row', hanging_leg_raise:'Hanging leg raise'};
export const validId = id => typeof id === 'string' && /^[A-Za-z0-9_-]{1,100}$/.test(id);
export function parseSample(x,id) {
  if (!x || x.schema_version!==2 || x.session_id!==id || !exercises[x.exercise] || x.form_status!=='not_evaluated') return null;
  for(const key of ['sequence','reps','timestamp']) if(!Number.isSafeInteger(x[key]) || x[key]<0) return null;
  if(x.sequence<1 || !Number.isFinite(x.sample_timestamp_ms) || x.sample_timestamp_ms<0) return null;
  if(!['WAIT_START','READY','OUTBOUND','AT_TARGET','RETURNING'].includes(x.phase) || !['tracking','lost','selecting_side'].includes(x.tracking_status)) return null;
  if(![null,undefined,'left','right'].includes(x.side)) return null;
  if(x.angle!=null && (!Number.isFinite(x.angle) || x.angle<0 || x.angle>180)) return null;
  if(x.tracking_status==='tracking' && (x.angle==null || x.side==null)) return null;
  if(x.tracking_status!=='tracking' && x.angle!=null) return null;
  if(x.frame_received_epoch_ms!=null && (!Number.isSafeInteger(x.frame_received_epoch_ms) || x.frame_received_epoch_ms<0)) return null;
  if(x.source!=null && !['camera','replay'].includes(x.source)) return null;
  return {...x, angle:x.angle??null, side:x.side??null};
}
export function acceptSample(previous,value,id,now=Date.now()) {
  const next=parseSample(value,id);
  if(!next) return {sample:previous,error:'Dữ liệu sai phiên hoặc sai schema'};
  if(previous && (next.sequence<=previous.sequence || next.sample_timestamp_ms<=previous.sample_timestamp_ms)) return {sample:previous,error:null,duplicate:true};
  if(previous && (next.exercise!==previous.exercise || next.reps<previous.reps || (previous.side && next.side!==previous.side))) return {sample:previous,error:'Phiên thay đổi không hợp lệ'};
  if(next.timestamp>now+5000 || (next.frame_received_epoch_ms??0)>now+5000) return {sample:previous,error:'Đồng hồ thiết bị không khớp'};
  return {sample:next,error:null};
}
export function stateOf(sample,receivedAt,now,error,summary) {
  if(error) return 'error';
  if(summary) return 'ended';
  if(!sample) return 'waiting';
  if(now-receivedAt>=2000 || now-(sample.frame_received_epoch_ms??sample.timestamp)>=2000) return 'stale';
  return sample.tracking_status;
}
export function validSummary(x,id,sample) {
  return !!x && x.session_id===id && !!exercises[x.exercise] && Number.isSafeInteger(x.reps) && x.reps>=0 &&
    Number.isSafeInteger(x.ended_at) && typeof x.status==='string' && (!sample || (x.exercise===sample.exercise && x.reps>=sample.reps));
}
export function chartPoint(previous,next) {
  const points=[];
  if(previous && (next.sample_timestamp_ms-previous.sample_timestamp_ms>350 || previous.side!==next.side)) points.push({x:next.sample_timestamp_ms/1000-.001,y:null});
  points.push({x:next.sample_timestamp_ms/1000,y:next.angle??null});
  return points;
}
