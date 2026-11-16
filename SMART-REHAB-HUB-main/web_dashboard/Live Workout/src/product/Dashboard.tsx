import {useEffect, useMemo, useRef, useState} from 'react';
import {onAuthStateChanged, signInWithEmailAndPassword, signOut, sendPasswordResetEmail, User} from 'firebase/auth';
import {ref, onValue, query, orderByChild, limitToLast, set, serverTimestamp} from 'firebase/database';
import Chart from 'chart.js/auto';
import QRCode from 'qrcode';
import {Activity, ArrowLeft, ArrowUpRight, Check, Clock, Dumbbell, HeartPulse, LogOut, MessageSquare, QrCode, Search, Users, Wifi, WifiOff} from 'lucide-react';
import {auth, db, root} from './firebase';
import {observeDoctorAccess} from './access.js';
import {anglePoints, dailyTrend, dateText, durationText, exerciseName, missingSegments, numeric, reasons, rows, statistics, statusText, exercises, exerciseDetails, filterSessions, goalText, sideText, phaseText, workloadSegments, restAnglePoints} from './data.js';
import './product.css';

type RecordData = Record<string, any>;
function useData(path: string | null, history = false) {
  const [state, update] = useState<{data: RecordData | null; loading: boolean; error: string | null}>({data: null, loading: true, error: null});
  useEffect(() => {
    update({data: null, loading: !!path, error: null});
    if (!path) return;
    const target = ref(db, path.startsWith('.info/') ? path : `${root}/${path}`);
    const source = history ? query(target, orderByChild('created_at'), limitToLast(100)) : target;
    return onValue(source, snapshot => update({data: snapshot.val() ?? {}, loading: false, error: null}), () => update({data: null, loading: false, error: 'Không thể đọc dữ liệu. Quyền truy cập có thể đã thay đổi.'}));
  }, [path, history]);
  return state;
}
function useNow() { const [now, setNow] = useState(Date.now()); useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []); return now; }
function Empty({title, children}: {title: string; children?: React.ReactNode}) { return <div className="sr-empty"><HeartPulse size={30}/><h3>{title}</h3><p>{children}</p></div>; }
function Loading() { return <div className="sr-loading" role="status"><span/>Đang tải dữ liệu…</div>; }
function ErrorBox({text}: {text: string}) { return <div className="sr-error" role="alert">{text}</div>; }

export default function Dashboard() {
  const [{user, loading, error: accessError, retryable}, setAccess] = useState<{user: User | null; loading: boolean; error: string; retryable: boolean}>({user: null, loading: true, error: '', retryable: false});
  const [attempt, retry] = useState(0);
  useEffect(() => observeDoctorAccess(callback => onAuthStateChanged(auth, callback), setAccess), [attempt]);
  if (loading) return <main className="smart-rehab"><Loading/></main>;
  if (!user) return <Login accessError={accessError} retry={retryable ? () => retry(value => value + 1) : undefined}/>;
  return <DoctorWorkspace key={user.uid} user={user}/>;
}
function Login({accessError, retry}: {accessError: string; retry?: () => void}) {
  const [email, setEmail] = useState(''), [password, setPassword] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function login(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { await signInWithEmailAndPassword(auth, email.trim(), password); }
    catch { setError('Chưa đăng nhập được. Kiểm tra email, mật khẩu và kết nối Internet.'); }
    finally { setBusy(false); }
  }
  return <main className="smart-rehab sr-login"><section className="sr-login-story"><Brand/><div><p className="sr-eyebrow">ĐỒNG HÀNH CÙNG NGƯỜI BỆNH</p><h1>Theo dõi từng buổi tập.<br/>Thấu hiểu từng bước tiến.</h1><p>Dữ liệu tập luyện tại nhà, được kết nối với sự chăm sóc của bác sĩ.</p></div><div className="sr-story-note"><Activity/> Một nơi để xem tiến độ và trao đổi sau mỗi buổi tập.</div></section><section className="sr-login-form"><div><span className="sr-chip"><HeartPulse size={15}/> Dành cho bác sĩ</span><h2>Chào mừng trở lại</h2><p>Đăng nhập bằng tài khoản đã được quản trị viên cấp.</p><form onSubmit={login}><label>Email<input required type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} placeholder="bacsi@example.com"/></label><label>Mật khẩu<input required type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>{(error || accessError) && <ErrorBox text={error || accessError}/>}{retry && <button className="sr-text" type="button" onClick={retry}>Thử xác minh lại</button>}<button className="sr-primary" disabled={busy}>{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}<ArrowUpRight size={18}/></button><button className="sr-text" type="button" disabled={busy} onClick={async()=>{if(!email.includes('@')){setError('Nhập email để nhận hướng dẫn đặt lại mật khẩu.');return;}try{await sendPasswordResetEmail(auth,email.trim());setError('Nếu email đã đăng ký, hướng dẫn đặt lại mật khẩu sẽ được gửi tới hộp thư.');}catch{setError('Chưa gửi được hướng dẫn. Kiểm tra kết nối và thử lại.');}}}>Quên mật khẩu?</button></form><small>Bệnh nhân dùng ứng dụng SMART REHAB trên Android để tập luyện và cấp quyền xem dữ liệu.</small></div></section></main>;
}
function Brand() { return <div className="sr-brand"><span><Activity size={23}/></span><div>SMART REHAB<small>CHĂM SÓC TIẾP NỐI</small></div></div>; }
function DoctorWorkspace({user}: {user: User}) {
  const links = useData(`careLinks/${user.uid}`), doctor = useData(`doctorDirectory/${user.uid}`), connection = useData('.info/connected');
  const [patient, selectPatient] = useState<string | null>(null), [search, setSearch] = useState(''), [showQr, setShowQr] = useState(false);
  const ids = Object.keys(links.data || {}).filter(id => links.data![id] === true);
  useEffect(() => { if (!links.loading && patient && !ids.includes(patient)) selectPatient(null); }, [links.data, links.loading, patient]);
  const name = doctor.data?.name || user.displayName || 'Bác sĩ';
  return <main className="smart-rehab sr-workspace"><aside className="sr-sidebar"><Brand/><nav><button className="selected" onClick={()=>selectPatient(null)}><Users size={20}/>Bệnh nhân</button><button onClick={()=>setShowQr(true)}><QrCode size={20}/>Mã liên kết của tôi</button></nav><div className="sr-sidebar-foot"><div className="sr-avatar">{name.slice(0,1)}</div><div><b>{name}</b><small>Tài khoản bác sĩ</small></div><button aria-label="Đăng xuất" title="Đăng xuất" onClick={()=>signOut(auth)}><LogOut size={18}/></button></div></aside><section className="sr-main"><header className="sr-topbar"><span>Không gian bác sĩ <span>/</span> {patient ? 'Chi tiết bệnh nhân' : 'Bệnh nhân'}</span><span className={`sr-connection ${connection.data === true ? '' : 'offline'}`}>{connection.data === true ? <Wifi size={15}/> : <WifiOff size={15}/>} {connection.data === true ? 'Đã kết nối' : 'Mất kết nối · dữ liệu có thể cũ'}</span></header><div className="sr-content">{patient && ids.includes(patient) ? <PatientDetail key={patient} id={patient} doctorId={user.uid} doctorName={name} connected={connection.data === true} back={()=>selectPatient(null)}/> : <><div className="sr-page-heading"><div><p className="sr-eyebrow">THEO DÕI TẬP LUYỆN TẠI NHÀ</p><h1>Bệnh nhân của bạn</h1><p>Xem buổi tập, theo dõi tiến độ và để lại nhận xét.</p></div><button className="sr-primary" onClick={()=>setShowQr(true)}><QrCode size={18}/>Mã liên kết</button></div><div className="sr-list-toolbar"><h2>{ids.length} bệnh nhân đã liên kết</h2><label className="sr-search"><Search size={18}/><input aria-label="Tìm bệnh nhân" placeholder="Tìm theo tên bệnh nhân…" value={search} onChange={e=>setSearch(e.target.value)}/></label></div>{links.loading ? <Loading/> : links.error ? <ErrorBox text={links.error}/> : !ids.length ? <Empty title="Chưa có bệnh nhân được liên kết">Chia sẻ mã liên kết để bệnh nhân quét trong ứng dụng. Dữ liệu chỉ xuất hiện khi bệnh nhân cho phép.</Empty> : <div className="sr-patients">{ids.map(id=><PatientCard key={id} id={id} search={search} open={()=>selectPatient(id)}/>)}</div>}</>}<footer>SMART REHAB · Dữ liệu góc 2D và số lần tập hỗ trợ theo dõi buổi tập.</footer></div></section>{showQr && <DoctorQr id={user.uid} name={name} close={()=>setShowQr(false)}/>}</main>;
}
function DoctorQr({id, name, close}: {id:string; name:string; close:()=>void}) {
  const [url, setUrl] = useState('');
  useEffect(()=>{QRCode.toDataURL(JSON.stringify({v:1,type:'doctor',doctor_uid:id}),{width:320,margin:2,color:{dark:'#153e36',light:'#ffffff'}}).then(setUrl);},[id]);
  return <div className="sr-modal-backdrop" onClick={close}><section className="sr-modal" role="dialog" aria-modal="true" aria-labelledby="qr-title" onClick={e=>e.stopPropagation()}><h2 id="qr-title">Liên kết với {name}</h2><p>Bệnh nhân mở Cá nhân → Liên kết bác sĩ, rồi quét mã này.</p>{url ? <img src={url} width="280" height="280" alt="Mã QR liên kết bác sĩ"/> : <Loading/>}<p className="sr-muted">Bệnh nhân có thể thu hồi quyền xem bất cứ lúc nào.</p><button className="sr-primary" autoFocus onClick={close}>Đóng</button></section></div>;
}
function PatientCard({id, search, open}: {id:string;search:string;open:()=>void}) {
  const profile = useData(`patients/${id}/profile`), history = useData(`patientSessions/${id}`, true);
  const sessions = rows(history.data), summary = statistics(sessions), latest = sessions[0];
  const name = profile.data?.name || 'Bệnh nhân';
  if (profile.loading) return <div className="sr-patient-card"><Loading/></div>;
  if (!name.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi'))) return null;
  return <button className="sr-patient-card" onClick={open}><div className="sr-card-title"><span className="sr-avatar">{name.slice(0,1)}</span><div><h3>{name}</h3><span className={`sr-pill ${latest && !latest.ended_at ? 'active' : ''}`}>{latest && !latest.ended_at ? 'Phiên chưa có tổng kết' : 'Đã liên kết'}</span></div><ArrowUpRight size={20}/></div>{profile.error || history.error ? <ErrorBox text="Quyền truy cập đã thay đổi."/> : <><div className="sr-card-metrics"><span><b>{summary.sessions}</b>buổi đã lưu</span><span><b>{Math.round(summary.seconds/60)}</b>phút tập</span><span><b>{summary.reps}</b>lần tập</span></div><div className="sr-card-last"><Clock size={14}/>{latest ? `Gần nhất: ${dateText(latest.created_at)}` : 'Chưa có buổi tập'}</div></>}</button>;
}
function Metric({icon: Icon, value, label, detail}: any) { return <div className="sr-metric"><span><Icon size={20}/></span><small>{label}</small><strong>{value}</strong><p>{detail}</p></div>; }
function PatientDetail({id, doctorId, doctorName, connected, back}: {id:string;doctorId:string;doctorName:string;connected:boolean;back:()=>void}) {
  const profile = useData(`patients/${id}/profile`), history = useData(`patientSessions/${id}`, true);
  const [exercise,setExercise]=useState('all'),[side,setSide]=useState('all'),[mode,setMode]=useState('all'),[session,selectSession]=useState<string|null>(null);
  const sessions=rows(history.data), filtered=filterSessions(sessions,{exercise,side,mode}),stats=statistics(filtered);
  if (profile.error || history.error) return <><button className="sr-text" onClick={back}><ArrowLeft size={16}/>Danh sách bệnh nhân</button><ErrorBox text="Không còn quyền xem dữ liệu bệnh nhân này."/></>;
  if (session) return <SessionDetail key={session} id={session} patientId={id} patientName={profile.data?.name || 'Bệnh nhân'} doctorId={doctorId} doctorName={doctorName} connected={connected} back={()=>selectSession(null)}/>;
  return <>
    <button className="sr-text sr-back" onClick={back}><ArrowLeft size={16}/>Danh sách bệnh nhân</button>
    <div className="sr-page-heading"><div><p className="sr-eyebrow">HỒ SƠ TẬP LUYỆN</p><h1>{profile.data?.name || 'Đang tải…'}</h1><p>Thống kê từ tối đa 100 buổi gần nhất, gồm các buổi đã dừng và gián đoạn.</p></div></div>
    <div className="sr-workout-filters">
      <label className="sr-filter">Bài tập<select value={exercise} onChange={e=>setExercise(e.target.value)}><option value="all">Tất cả bài tập</option>{Object.entries(exercises).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
      <label className="sr-filter">Bên tập<select value={side} onChange={e=>setSide(e.target.value)}><option value="all">Tất cả / phiên cũ</option><option value="left">Bên trái</option><option value="right">Bên phải</option><option value="both">Cả hai cùng lúc</option><option value="auto">Tự chọn bên nhìn rõ</option></select></label>
      <label className="sr-filter">Chế độ<select value={mode} onChange={e=>setMode(e.target.value)}><option value="all">Tất cả chế độ</option><option value="time">Theo thời gian</option><option value="sets">Theo lần và hiệp</option></select></label>
    </div>
    <div className="sr-metrics"><Metric icon={Activity} value={stats.sessions} label="Buổi đã lưu" detail="Có tổng kết từ hub"/><Metric icon={Clock} value={Math.round(stats.seconds/60)} label="Phút tập" detail="Bỏ thời gian nghỉ khi có dữ liệu"/><Metric icon={Dumbbell} value={stats.reps} label="Lần hoàn thành" detail="Theo chu kỳ đã ghi nhận"/></div>
    <section className="sr-panel"><div className="sr-panel-heading"><div><h2>Nhịp tập theo ngày</h2><p>Số lần hoàn thành · múi giờ Việt Nam</p></div><span className="sr-legend"><i/>Số lần tập</span></div><Trend sessions={filtered} exercise="all"/></section>
    <section className="sr-panel"><div className="sr-panel-heading"><h2>Lịch sử buổi tập</h2><span>{filtered.length} buổi</span></div>{history.loading ? <Loading/> : !filtered.length ? <Empty title="Chưa có buổi tập phù hợp">Thử chọn bộ lọc khác hoặc chờ phiên mới được đồng bộ.</Empty> : <div className="sr-table-scroll"><table><thead><tr><th>Buổi tập</th><th>Bài tập / bên</th><th>Mục tiêu</th><th>Thời gian tập</th><th>Số lần</th><th>Trạng thái</th><th/></tr></thead><tbody>{filtered.map(s=><tr key={s.session_id}><td>{dateText(s.created_at)}</td><td>{exerciseName(s.exercise)}<small className="sr-table-note">{sideText(s.requested_side)}</small></td><td>{goalText(s.goal)}</td><td>{s.ended_at ? durationText(s.active_s ?? s.elapsed_s) : '—'}</td><td>{numeric(s.reps)}</td><td><span className={`sr-pill ${s.status==='completed' ? 'success' : ''}`}>{statusText(s)}</span></td><td><button className="sr-text" onClick={()=>selectSession(s.session_id)}>Xem<ArrowUpRight size={15}/></button></td></tr>)}</tbody></table></div>}</section>
  </>;
}
function Trend({sessions, exercise}: any) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const points = useMemo(()=>dailyTrend(sessions,exercise),[sessions,exercise]);
  useEffect(()=>{
    if (!canvas.current || !points.length) return;
    const chart = new Chart(canvas.current,{type:'bar',data:{labels:points.map(p=>p.day.split('-').reverse().slice(0,2).join('/')),datasets:[{label:'Số lần tập',data:points.map(p=>p.reps),backgroundColor:'#16836d',borderRadius:5,maxBarThickness:36}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0},grid:{color:'#edf2ef'}},x:{grid:{display:false}}}}});
    return ()=>chart.destroy();
  },[points]);
  return points.length ? <div className="sr-chart"><canvas ref={canvas} aria-label="Biểu đồ số lần tập theo ngày" role="img"/></div> : <Empty title="Chưa có buổi tập đã lưu">Biểu đồ sẽ hiển thị khi có tổng kết.</Empty>;
}
function SessionDetail({id, patientId, patientName, doctorId, doctorName, connected, back}: any) {
  const meta=useData(`sessions/${id}/meta`),summary=useData(`sessions/${id}/summary`),latest=useData(`sessions/${id}/latest`),points=useData(`sessions/${id}/points`),events=useData(`sessions/${id}/events`);
  const now=useNow(),ended=!!summary.data?.ended_at,live=connected && !ended && now-numeric(latest.data?.timestamp)<2500;
  const values=ended ? summary.data! : latest.data || {}, goal=meta.data?.goal || values.goal;
  const gaps=missingSegments(points.data),restSegments=workloadSegments(points.data,'resting'),alignSegments=workloadSegments(points.data,'aligning');
  const label=exerciseDetails(meta.data?.exercise).angle_label || 'Góc khớp', both=meta.data?.requested_side==='both';
  if ([meta,summary,latest,points,events].some(s=>s.error)) return <><button className="sr-text" onClick={back}><ArrowLeft size={16}/>Hồ sơ bệnh nhân</button><ErrorBox text="Không còn đọc được phiên này. Kiểm tra kết nối và quyền liên kết."/></>;
  return <>
    <button className="sr-text sr-back" onClick={back}><ArrowLeft size={16}/>{patientName}</button>
    <div className="sr-page-heading"><div><p className="sr-eyebrow">CHI TIẾT BUỔI TẬP</p><h1>{exerciseName(meta.data?.exercise)}</h1><p>{patientName} · {dateText(meta.data?.created_at)}</p><p>{sideText(meta.data?.requested_side)} · Mục tiêu: {goalText(goal)}</p></div><span className={`sr-pill ${live ? 'active' : ended ? 'success' : ''}`}>{live ? phaseText(values.workload_phase) : ended ? statusText(summary.data) : 'Chờ dữ liệu từ hub'}</span></div>
    {!ended && <div className={`sr-live-banner ${live ? '' : 'stale'}`}><Activity size={20}/><div><b>{live ? values.workload_phase==='resting' ? `Nghỉ còn ${durationText(values.rest_remaining_s)}` : values.workload_phase==='aligning' ? 'Căn người cho hiệp tiếp theo' : values.tracking_status==='tracking' ? 'Hub đang nhận rõ khớp' : 'Hub chưa thấy đủ khớp' : 'Dữ liệu trực tiếp đã cũ; chờ cập nhật từ hub'}</b><p>{live && goal?.mode==='sets' ? `Hiệp ${numeric(values.set_number)}/${numeric(goal.sets)} · ${numeric(values.rep_in_set)}/${numeric(goal.reps_per_set)} lần` : live && goal?.mode==='time' ? `Còn ${durationText(values.remaining_s)}` : 'Tiến độ sẽ cập nhật khi nhận dữ liệu mới.'}</p></div></div>}
    <div className="sr-metrics"><Metric icon={Dumbbell} value={numeric(values.reps)} label="Lần hoàn thành" detail={live || ended ? 'Đếm chu kỳ đầy đủ' : 'Giá trị nhận gần nhất'}/><Metric icon={Clock} value={ended ? durationText(values.active_s ?? values.elapsed_s) : live ? durationText(values.active_s) : '—'} label="Thời gian tập" detail={ended ? `Nhận rõ khớp ${durationText(values.tracking_s)}` : 'Đồng hồ do hub quản lý'}/><Metric icon={Activity} value={!ended && live && typeof values.angle==='number' ? `${Math.round(values.angle)}°` : '—'} label={label} detail={both ? 'Trung bình hai bên · xem từng bên ở đồ thị' : 'Phép đo 2D'}/></div>
    <div className="sr-detail-grid"><div>
      {goal?.mode==='sets' && <section className="sr-panel"><div className="sr-panel-heading"><h2>Mục tiêu và từng hiệp</h2><span>{numeric(values.completed_sets)}/{numeric(goal.sets)} hiệp đã đủ</span></div><p>{goalText(goal)} · Nghỉ giữa hiệp {numeric(goal.rest_s)} giây</p>{ended ? <><div className="sr-table-scroll"><table><thead><tr><th>Hiệp</th><th>Thực hiện</th><th>Thời gian tập</th><th>Kết quả</th></tr></thead><tbody>{Array.from({length:numeric(goal.sets)},(_,i)=>{const s=values.set_results?.[`set${String(i+1).padStart(3,'0')}`];return <tr key={i}><td>{i+1}</td><td>{numeric(s?.reps)}/{numeric(goal.reps_per_set)} lần</td><td>{s ? durationText(s.active_s) : '—'}</td><td>{s?.completed ? 'Đủ mục tiêu' : s ? 'Chưa đủ' : 'Chưa bắt đầu'}</td></tr>})}</tbody></table></div><p>Tổng nghỉ: {durationText(values.rest_s)} · Căn lại: {durationText(values.aligning_s)} · Thời gian toàn phiên: {durationText(values.elapsed_s)}</p></> : <p>{live ? phaseText(values.workload_phase) : 'Chờ trạng thái mới từ hub.'}</p>}</section>}
      <section className="sr-panel"><div className="sr-panel-heading"><div><h2>Diễn biến {label.toLocaleLowerCase('vi')}</h2><p>Mỗi giây một mẫu · nét xám là nghỉ giữa hiệp</p></div></div><AngleChart points={points.data} label={label} both={both}/><div className="sr-session-facts"><span>Kết thúc: <b>{ended ? reasons[values.error] || 'Phiên bị gián đoạn' : 'Chưa kết thúc'}</b></span><span>Thiếu dữ liệu: <b>{gaps.length} đoạn</b></span><span>Nghỉ: <b>{restSegments.length} đoạn</b></span><span>Căn người: <b>{alignSegments.length} đoạn</b></span><span>Preset: <b>{meta.data?.preset_version || meta.data?.algorithm_version || 'Phiên cũ'}</b></span></div>{[['Thiếu dữ liệu',gaps],['Nghỉ giữa hiệp',restSegments],['Căn người',alignSegments]].map(([name,segments]:any)=>segments.length ? <details key={name}><summary>{name}</summary><ul>{segments.map((g:any,i:number)=><li key={i}>{durationText(g.from/1000)} – {durationText(g.to/1000)}</li>)}</ul></details> : null)}</section>
      <section className="sr-panel"><div className="sr-panel-heading"><h2>Các lần tập đã ghi nhận</h2><span>{Object.keys(events.data || {}).length} lần</span></div>{Object.keys(events.data || {}).length ? <div className="sr-table-scroll"><table><thead><tr><th>Lần toàn phiên</th><th>Hiệp / lần</th><th>Bắt đầu</th><th>Chu kỳ</th><th>{both ? "Góc trái (min–max)" : "Góc thấp nhất"}</th><th>{both ? "Góc phải (min–max)" : "Góc cao nhất"}</th><th>{both ? "Biên độ trái / phải" : "Biên độ 2D"}</th></tr></thead><tbody>{Object.values(events.data || {}).sort((a:any,b:any)=>a.rep-b.rep).map((e:any)=><tr key={e.id}><td>{e.rep}</td><td>{e.set_number ? `${e.set_number} / ${e.rep_in_set}` : '—'}</td><td>{durationText(e.start_ms/1000)}</td><td>{(numeric(e.duration_ms)/1000).toFixed(1)} giây</td><td>{both ? `${numeric(e.left_min_angle_deg).toFixed(1)}–${numeric(e.left_max_angle_deg).toFixed(1)}°` : `${numeric(e.min_angle_deg).toFixed(1)}°`}</td><td>{both ? `${numeric(e.right_min_angle_deg).toFixed(1)}–${numeric(e.right_max_angle_deg).toFixed(1)}°` : `${numeric(e.max_angle_deg).toFixed(1)}°`}</td><td>{both ? `${numeric(e.rom_left_deg).toFixed(1)}° / ${numeric(e.rom_right_deg).toFixed(1)}°` : `${numeric(e.rom_deg).toFixed(1)}°`}</td></tr>)}</tbody></table></div> : <Empty title="Chưa có lần tập hoàn chỉnh">Chuyển động dở hoặc mất khớp sẽ không được tính thêm.</Empty>}</section>
    </div><Comments id={id} patientId={patientId} doctorId={doctorId} doctorName={doctorName} connected={connected}/></div>
  </>;
}
function AngleChart({points,label,both=false}: {points:RecordData|null;label:string;both?:boolean}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const data=useMemo(()=>anglePoints(points),[points]);
  const left=useMemo(()=>anglePoints(points,'angle_left'),[points]), right=useMemo(()=>anglePoints(points,'angle_right'),[points]);
  const restData=useMemo(()=>restAnglePoints(points),[points]);
  useEffect(()=>{
    if(!canvas.current || !data.length) return;
    const line = (name:string, values:any[], color:string) => ({label:name,data:values,borderColor:color,backgroundColor:color,borderWidth:2,pointRadius:0,spanGaps:false,tension:0});
    const datasets = both ? [line(label+' trái (°)',left,'#16836d'),line(label+' phải (°)',right,'#8c55a8')] : [line(label+' khi tập (°)',data,'#16836d')];
    datasets.push({...line(both ? 'Nghỉ · trung bình hai bên (°)' : 'Trong lúc nghỉ (°)',restData,'#879790'),borderDash:[4,4]} as any);
    const chart = new Chart(canvas.current,{type:'line',data:{datasets},options:{animation:false,responsive:true,maintainAspectRatio:false,plugins:{legend:{display:true}},scales:{x:{type:'linear',title:{display:true,text:'Giây từ khi mở phiên'},grid:{display:false}},y:{min:0,max:180,title:{display:true,text:'Độ (°)'},grid:{color:'#edf2ef'}}}}});
    return ()=>chart.destroy();
  },[data,left,right,restData,label,both]);
  return data.length ? <div className="sr-chart"><canvas ref={canvas} role="img" aria-label={both ? 'Diễn biến góc bên trái và bên phải' : 'Diễn biến góc khớp 2D theo thời gian'}/></div> : <Empty title="Đang chờ dữ liệu góc">Dữ liệu được gửi từ hub trong buổi tập.</Empty>;
}

function Comments({id, doctorId, doctorName, connected}: any) {
  const comments = useData(`comments/${id}`); const [draft, setDraft] = useState(''), [saved, setSaved] = useState(false), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const loaded = useRef(false);
  useEffect(()=>{if(!comments.loading && !loaded.current){setDraft(comments.data?.[doctorId]?.text || '');loaded.current=true;}},[comments.data,comments.loading,doctorId]);
  async function save(e: React.FormEvent){e.preventDefault(); if(!connected || !draft.trim())return;setBusy(true);setError('');setSaved(false);try{await set(ref(db,`${root}/comments/${id}/${doctorId}`),{text:draft.trim(),doctor_name:doctorName,updated_at:serverTimestamp()});setSaved(true);}catch{setError('Chưa lưu được. Kiểm tra kết nối và quyền xem bệnh nhân.');}finally{setBusy(false);}}
  return <aside className="sr-panel sr-comments"><div className="sr-panel-heading"><h2><MessageSquare size={19}/>Nhận xét</h2></div><p>Bệnh nhân sẽ thấy nhận xét này trong ứng dụng.</p>{comments.error ? <ErrorBox text={comments.error}/> : <><form onSubmit={save}><label htmlFor="comment">Nhận xét của bạn</label><textarea id="comment" rows={8} maxLength={4000} value={draft} onChange={e=>{setDraft(e.target.value);setSaved(false);}} placeholder="Ghi nhận buổi tập và hướng dẫn cho lần tới…"/><div className="sr-comment-meta"><span>{draft.length}/4000</span>{saved && <span className="sr-saved"><Check size={14}/>Đã lưu</span>}</div>{error && <ErrorBox text={error}/>}<button className="sr-primary" disabled={!connected || !draft.trim() || busy}>{busy ? 'Đang lưu…' : 'Lưu nhận xét'}</button></form>{Object.entries(comments.data || {}).filter(([uid])=>uid!==doctorId).map(([uid,c]:any)=><article className="sr-other-comment" key={uid}><b>{c.doctor_name}</b><small>{dateText(c.updated_at)}</small><p>{c.text}</p></article>)}</>}</aside>;
}
