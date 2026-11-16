import {exercises, exerciseDetails} from './catalog.g.js';
export {exercises, exerciseDetails};
export const exerciseName = id => exerciseDetails(id).name || 'Bài tập';
export const numeric = value => typeof value === 'number' && Number.isFinite(value) ? value : 0;
export const dateText = timestamp => numeric(timestamp) > 0 ? new Intl.DateTimeFormat('vi-VN', {dateStyle: 'medium', timeStyle: 'short'}).format(timestamp) : 'Chưa có thời gian';
export const durationText = seconds => {
  const total = Math.max(0, Math.round(numeric(seconds)));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
};
export const rows = data => Object.values(data || {}).filter(v => v && typeof v === 'object').sort((a, b) => numeric(b.created_at) - numeric(a.created_at));
export const reasons = {
  goal_complete: 'Hoàn thành mục tiêu các hiệp', session_limit: 'Hết giới hạn 30 phút, chưa hoàn thành mục tiêu',
  duration_complete: 'Hoàn thành thời lượng', patient_stop: 'Bệnh nhân chủ động dừng', internet_lost: 'Hub mất Internet',
  hub_restarted: 'Hub khởi động lại', hub_shutdown: 'Hub đã tắt', camera_disconnected: 'Webcam ngắt kết nối',
  camera_unavailable: 'Không mở được webcam', camera_shutdown_timeout: 'Webcam không đóng được',
  preparation_timeout: 'Chưa đạt tư thế sẵn sàng', temperature_limit: 'Hub cần giảm nhiệt',
  display_disconnected: 'Màn hình ngắt kết nối', audio_unavailable: 'Âm thanh chưa sẵn sàng',
  storage_unavailable: 'Lỗi lưu trữ', engine_error: 'Phiên bị gián đoạn',
};
export const statusText = row => row.status === 'completed' ? 'Hoàn thành' : row.status === 'stopped' ? 'Đã dừng' : row.status === 'interrupted' ? 'Gián đoạn' : 'Chưa có tổng kết';
export function statistics(sessions, exercise = 'all') {
  const completed = sessions.filter(s => numeric(s.ended_at) > 0 && (exercise === 'all' || s.exercise === exercise));
  return {sessions: completed.length, seconds: completed.reduce((a, s) => a + numeric(s.active_s ?? s.elapsed_s), 0), reps: completed.reduce((a, s) => a + numeric(s.reps), 0)};
}
export function dailyTrend(sessions, exercise = 'all') {
  const dates = new Map();
  for (const s of sessions) {
    if (!s.ended_at || (exercise !== 'all' && s.exercise !== exercise)) continue;
    const key = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Ho_Chi_Minh', year:'numeric', month:'2-digit', day:'2-digit'}).format(s.created_at);
    const day = dates.get(key) || {day: key, reps: 0, minutes: 0, sessions: 0};
    day.reps += numeric(s.reps); day.minutes += numeric(s.active_s ?? s.elapsed_s) / 60; day.sessions += 1; dates.set(key, day);
  }
  return [...dates.values()].sort((a, b) => a.day.localeCompare(b.day));
}
export function anglePoints(data, field = 'angle') {
  const points = Object.values(data || {}).sort((a, b) => numeric(a.t_ms) - numeric(b.t_ms));
  const out = []; let previous = null;
  for (const point of points) {
    if (previous !== null && point.t_ms - previous > 1500) out.push({x: (previous + point.t_ms) / 2000, y: null});
    out.push({x: numeric(point.t_ms) / 1000, y: point.workload_phase !== 'resting' && point.tracking_status === 'tracking' && typeof point[field] === 'number' ? point[field] : null});
    previous = point.t_ms;
  }
  return out;
}

export const sideText = side => ({left:'Bên trái',right:'Bên phải',auto:'Tự chọn bên nhìn rõ',both:'Cả hai cùng lúc'}[side] || 'Chưa ghi bên tập');
export const goalText = goal => goal?.mode === 'sets' ? `${numeric(goal.reps_per_set)} lần × ${numeric(goal.sets)} hiệp` : goal?.mode === 'time' ? `${numeric(goal.duration_s)/60} phút` : 'Theo thời gian';
export const phaseText = phase => ({aligning:'Căn người để sẵn sàng',working:'Đang tập',resting:'Nghỉ giữa hiệp',complete:'Đang lưu kết quả'}[phase] || 'Chuẩn bị');
export function filterSessions(sessions, {exercise='all', side='all', mode='all'} = {}) {
  return sessions.filter(s => (exercise==='all' || s.exercise===exercise) && (side==='all' || s.requested_side===side) && (mode==='all' || (s.goal?.mode || 'time')===mode));
}
export function workloadSegments(data, phase) {
  const points=Object.values(data || {}).sort((a,b)=>numeric(a.t_ms)-numeric(b.t_ms));
  const out=[];let start=null, previous=null;
  for(const p of points) {
    if(p.workload_phase===phase && start===null) start=p.t_ms;
    if(p.workload_phase!==phase && start!==null) {out.push({from:start,to:p.t_ms});start=null;}
    previous=p.t_ms;
  }
  if(start!==null) out.push({from:start,to:previous});
  return out;
}
export function missingSegments(data) {
  const points=Object.values(data || {}).sort((a,b)=>numeric(a.t_ms)-numeric(b.t_ms));
  const gaps=[];let start=null,previous=null;
  for(const p of points) {
    const planned=['resting','aligning'].includes(p.workload_phase);
    if(previous && p.t_ms-previous.t_ms>1500 && !['resting','aligning'].includes(previous.workload_phase)) {
      if(start===null) start=previous.t_ms;
    }
    if(planned) {
      if(start!==null) {gaps.push({from:start,to:p.t_ms});start=null;}
    } else if(p.tracking_status!=='tracking' || typeof p.angle!=='number') {
      if(start===null) start=p.t_ms;
    } else if(start!==null) {gaps.push({from:start,to:p.t_ms});start=null;}
    previous=p;
  }
  if(start!==null) gaps.push({from:start,to:previous.t_ms});
  return gaps;
}
export function restAnglePoints(data) {
  return Object.values(data || {}).sort((a,b)=>numeric(a.t_ms)-numeric(b.t_ms)).map(p=>({x:numeric(p.t_ms)/1000,y:p.workload_phase==='resting' && p.tracking_status==='tracking' && typeof p.angle==='number' ? p.angle : null}));
}
