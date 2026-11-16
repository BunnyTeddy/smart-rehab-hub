import {useEffect,useRef,useState} from 'react';
import {initializeApp,getApps} from 'firebase/app';
import {getAuth,signInWithEmailAndPassword,signOut,connectAuthEmulator} from 'firebase/auth';
import {getDatabase,ref,onValue,get,connectDatabaseEmulator} from 'firebase/database';
import Chart from 'chart.js/auto';
import {acceptSample,chartPoint,exercises,stateOf,validId,validSummary} from './session.js';

const config={apiKey:import.meta.env.VITE_FIREBASE_API_KEY,appId:import.meta.env.VITE_FIREBASE_APP_ID,projectId:'smart-rehab-hub',authDomain:'smart-rehab-hub.firebaseapp.com',databaseURL:'https://smart-rehab-hub-default-rtdb.asia-southeast1.firebasedatabase.app'};
const root=import.meta.env.VITE_SESSION_ROOT||'demo_e2e_v1/sessions';
const emulator=import.meta.env.VITE_EMULATOR==='true';
let services:any;
function cloud() {
  if(services)return services;
  if(!['sessions','demo_e2e_v1/sessions'].includes(root))throw new Error('Session root không hợp lệ');
  if(!emulator && (!config.apiKey || !config.appId))throw new Error('Chưa cấu hình Firebase Web. Không dùng dữ liệu giả thay cloud.');
  const app=getApps()[0]||initializeApp(emulator?{...config,apiKey:'demo-key',appId:'demo-app',projectId:'demo-smart-rehab',databaseURL:'https://demo-smart-rehab.firebaseio.com'}:config);
  const auth=getAuth(app),database=getDatabase(app);
  if(emulator){connectAuthEmulator(auth,'http://127.0.0.1:9099',{disableWarnings:true});connectDatabaseEmulator(database,'127.0.0.1',9000);}
  services={auth,database};return services;
}
const card:React.CSSProperties={background:'white',border:'1px solid #dce5e3',borderRadius:16,padding:20};
const input:React.CSSProperties={padding:'10px 12px',border:'1px solid #cbd5e1',borderRadius:8,color:'#12302d',background:'white',minWidth:180};
const button:React.CSSProperties={...input,background:'#047857',color:'white',cursor:'pointer',minWidth:100};

export function IntegrationDashboard(){
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[sessionId,setSessionId]=useState('');
  const [user,setUser]=useState<string|null>(null),[active,setActive]=useState(''),[fixture,setFixture]=useState(false);
  const [sample,setSample]=useState<any>(null),[summary,setSummary]=useState<any>(null),[error,setError]=useState<string|null>(null);
  const [connected,setConnected]=useState(false),[now,setNow]=useState(Date.now()),[received,setReceived]=useState(0);
  const [bindingGeneration,setBindingGeneration]=useState(0);
  const launcherBound=useRef(''),launcherAuthenticated=useRef(false),autoTimingSaved=useRef('');
  const latest=useRef<any>(null),ended=useRef<any>(null),metrics=useRef<any[]>([]),canvas=useRef<HTMLCanvasElement>(null),chart=useRef<Chart|null>(null);
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),250);return()=>clearInterval(timer)},[]);
  useEffect(()=>{
    if(import.meta.env.VITE_LAUNCHER!=='true'||location.hostname!=='127.0.0.1')return;
    let disposed=false,busy=false;
    async function poll(){
      if(busy)return;busy=true;
      try{
        const s=await (await fetch('/__launcher')).json();
        if(!s.enabled||!validId(s.session_id))return;
        if(s.session_id===launcherBound.current){
          if(cloud().auth.currentUser)await fetch('/__launcher_ready',{method:'POST',headers:{'X-Rehab-Demo':'local-only'},body:JSON.stringify({session_id:s.session_id})});
          return;
        }
        if(!launcherAuthenticated.current){
          const r=await fetch('/__demo_login',{method:'POST',headers:{'X-Rehab-Demo':'local-only'}});
          if(!r.ok)throw new Error();const c=await r.json();
          const auth=await signInWithEmailAndPassword(cloud().auth,c.email,c.password);c.password='';
          if(disposed)return;setUser(auth.user.uid);launcherAuthenticated.current=true;
        }
        await get(ref(cloud().database,`${root}/${s.session_id}/meta`));
        if(disposed)return;launcherBound.current=s.session_id;
        setSessionId(s.session_id);setFixture(false);setActive(s.session_id);setBindingGeneration(n=>n+1);
      }catch{if(!disposed)setError('Chưa kết nối được — xem trang điều khiển SMART REHAB.');}
      finally{busy=false;}
    }
    void poll();const timer=setInterval(poll,1000);
    return()=>{disposed=true;clearInterval(timer)};
  },[]);
  useEffect(()=>{if(!canvas.current)return;chart.current=new Chart(canvas.current,{type:'line',data:{datasets:[{label:'Góc trong 2D (°)',data:[],borderColor:'#059669',pointRadius:0,tension:0,spanGaps:false}]},options:{animation:false,responsive:true,maintainAspectRatio:false,scales:{x:{type:'linear',title:{display:true,text:'Thời gian mẫu (giây)'}},y:{min:0,max:180}}}});return()=>{chart.current?.destroy();chart.current=null}},[]);
  useEffect(()=>{
    latest.current=null;ended.current=null;metrics.current=[];setSample(null);setSummary(null);setReceived(0);setError(null);setConnected(false);
    if(chart.current){chart.current.data.datasets[0].data=[];chart.current.update()}
    if(!active)return;
    let live=true;
    function receive(value:any){
      if(!live||ended.current||value==null)return;
      const at=Date.now(),foregroundAtReceive=document.visibilityState==='visible'&&document.hasFocus(),result=acceptSample(latest.current,value,active,at);
      if(result.error){setError(result.error);return}
      if(result.duplicate)return;
      if(chart.current){chart.current.data.datasets[0].data.push(...chartPoint(latest.current,result.sample));chart.current.data.datasets[0].data=chart.current.data.datasets[0].data.slice(-600);chart.current.update()}
      latest.current=result.sample;setSample(result.sample);setReceived(at);setError(null);
      requestAnimationFrame(()=>{if(live)metrics.current.push({session_id:active,sequence:result.sample.sequence,frame_received_epoch_ms:result.sample.frame_received_epoch_ms,published_at_epoch_ms:result.sample.timestamp,browser_received_epoch_ms:at,browser_render_callback_epoch_ms:Date.now(),browser_foreground_at_receive:foregroundAtReceive,browser_foreground_at_render:document.visibilityState==='visible'&&document.hasFocus(),clock_verified:false,source:result.sample.source,synthetic:fixture})});
    }
    if(fixture){
      let seq=0;const timer=setInterval(()=>{seq++;const t=seq*200,missing=seq%30>=24;receive({schema_version:2,session_id:active,exercise:'squat',sequence:seq,reps:Math.floor(seq/25),sample_timestamp_ms:t,timestamp:Date.now(),frame_received_epoch_ms:Date.now(),angle:missing?null:130+35*Math.cos(t/1000),side:'left',phase:'READY',tracking_status:missing?'lost':'tracking',form_status:'not_evaluated',source:'replay'});},200);
      return()=>{live=false;clearInterval(timer)};
    }
    let unsub:Array<()=>void>=[];
    try{const {database}=cloud();unsub=[
      onValue(ref(database,'.info/connected'),s=>setConnected(s.val()===true)),
      onValue(ref(database,`${root}/${active}/latest`),s=>receive(s.val()),()=>setError('Không đọc được phiên / không có quyền')),
      onValue(ref(database,`${root}/${active}/summary`),s=>{if(!s.exists())return;if(!validSummary(s.val(),active,latest.current)){setError('Tổng kết không hợp lệ');return}ended.current=s.val();setSummary(s.val())},()=>setError('Không đọc được tổng kết'))
    ];if(import.meta.env.VITE_LAUNCHER==='true'){
      void get(ref(database,`${root}/${active}/meta`)).then(()=>{
        if(live)return fetch('/__launcher_ready',{method:'POST',headers:{'X-Rehab-Demo':'local-only'},body:JSON.stringify({session_id:active})});
      }).catch(()=>{if(live)setError('Chưa được cấp quyền phiên.');});
    }}catch(e:any){setError(e.message)}
    return()=>{live=false;unsub.forEach(f=>f())};
  },[active,fixture,bindingGeneration]);
  useEffect(()=>{
    if(import.meta.env.VITE_LAUNCHER!=='true'||!summary||!metrics.current.length||autoTimingSaved.current===active)return;
    autoTimingSaved.current=active;
    void fetch('/__timing',{method:'POST',headers:{'X-Rehab-Demo':'local-only'},body:JSON.stringify({rows:metrics.current})})
      .then(r=>{if(!r.ok)throw new Error()}).catch(()=>{autoTimingSaved.current='';setError('Timing chưa lưu tự động.');});
  },[summary,active]);
  const state=stateOf(sample,received,now,error,summary),angle=state==='tracking'?sample?.angle:null;
  const exercise=summary?.exercise||sample?.exercise;
  async function login(e:React.FormEvent){e.preventDefault();try{const credential=await signInWithEmailAndPassword(cloud().auth,email,password);setUser(credential.user.uid);setPassword('');setError(null)}catch{setError('Đăng nhập thất bại hoặc thiếu cấu hình Firebase Web.')}}
  async function localDemoLogin(){try{if(location.hostname!=='127.0.0.1')throw new Error('loopback');const r=await fetch('/__demo_login',{method:'POST',headers:{'X-Rehab-Demo':'local-only'}});if(!r.ok)throw new Error('expired');const c=await r.json();const credential=await signInWithEmailAndPassword(cloud().auth,c.email,c.password);c.password='';setUser(credential.user.uid);setPassword('');setError(null)}catch{setError('Local demo credential unavailable')}}
  async function logout(){setActive('');setSample(null);setSummary(null);setUser(null);setFixture(false);setPassword('');if(services)await signOut(services.auth)}
  function bind(){if(!validId(sessionId)){setError('Session ID chỉ gồm chữ, số, _ và -');return}setFixture(false);setActive(sessionId);setBindingGeneration(n=>n+1)}
  async function download(){const text=JSON.stringify({clock_verified:false,rows:metrics.current},null,2);if(import.meta.env.VITE_LOCAL_AUTH==='true'){try{const r=await fetch('/__timing',{method:'POST',headers:{'X-Rehab-Demo':'local-only'},body:text});if(!r.ok)throw new Error();setError(null)}catch{setError('Timing chưa lưu; giữ trang này mở')}return}const blob=new Blob([text],{type:'application/json'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`browser_timing_${active}.json`;a.click();URL.revokeObjectURL(url)}
  return <main style={{minHeight:'100vh',background:'#f3f7f6',color:'#173934',fontFamily:'system-ui',padding:'32px max(20px,5vw)'}}>
    <header style={{display:'flex',justifyContent:'space-between',gap:16,flexWrap:'wrap'}}><div><p style={{letterSpacing:2,fontSize:12}}>SMART REHAB · INTEGRATION V1</p><h1 style={{fontSize:32,margin:'8px 0'}}>Theo dõi phiên tập</h1><p>Quan sát dữ liệu Pi · góc 2D · chu kỳ hoàn chỉnh</p></div><div><b>{fixture?'FIXTURE TỔNG HỢP':emulator?'FIREBASE EMULATOR':'FIREBASE CLOUD'}</b><p>{connected?'Kết nối database':'Chưa kết nối database'} ≠ đang nhận mẫu mới</p></div></header>
    <section style={{...card,margin:'20px 0'}}>
      {!user?<form onSubmit={login} style={{display:'flex',gap:10,flexWrap:'wrap'}}><input aria-label="Email" style={input} type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="Email tài khoản thử"/><input aria-label="Mật khẩu" style={input} type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Mật khẩu"/><button style={button}>Đăng nhập</button></form>:<div style={{display:'flex',gap:10,flexWrap:'wrap'}}><input aria-label="Session ID" style={input} value={sessionId} onChange={e=>setSessionId(e.target.value)} placeholder="Session ID in trên Pi"/><button style={button} onClick={bind}>Theo dõi phiên</button><button style={input} onClick={logout}>Đăng xuất</button></div>}
      <button style={{...input,marginTop:12}} onClick={()=>{setFixture(true);setActive('demo_fixture')}}>Thử fixture offline</button>
      {!user&&import.meta.env.VITE_LOCAL_AUTH==='true'&&<button style={{...input,margin:12}} onClick={localDemoLogin}>Đăng nhập tài khoản demo cục bộ</button>}
      <p style={{fontSize:13}}>Pi chọn bài và điều khiển phiên. Không quét QR, không điều khiển từ xa. {active&&`Phiên: ${active}`}</p>
    </section>
    {fixture&&<p role="status" style={{padding:14,background:'#fef3c7'}}>DỮ LIỆU TỔNG HỢP — không phải phép đo Pi, camera hoặc kiểm chứng thuật toán.</p>}
    {error&&<p role="alert" style={{color:'#991b1b'}}>{error}</p>}
    <section style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(175px,1fr))',gap:14}}>
      {[['Bài tập',exercises[exercise]||'Chờ dữ liệu'],['Chu kỳ hoàn chỉnh',summary?.reps??sample?.reps??'—'],['Góc trong 2D',angle==null?'—':`${angle.toFixed(1)}°`],['Trạng thái',state],['Pha / bên',`${sample?.phase||'—'} / ${sample?.side||'—'}`],['Nguồn',sample?.source||'—']].map(([label,value])=><article key={label} style={card}><p style={{fontSize:12,color:'#526a65'}}>{label}</p><strong style={{fontSize:22}}>{value}</strong></article>)}
    </section>
    <section style={{...card,marginTop:18}}><h2 style={{fontSize:18}}>Góc theo thời gian mẫu</h2><div style={{height:260}}><canvas ref={canvas} aria-label="Biểu đồ góc"/></div><p style={{fontSize:12}}>Không nội suy qua mẫu mất khớp hoặc gap &gt;350 ms. Góc không đo được không phải 0°.</p></section>
    {summary&&<section style={{...card,marginTop:18}}><h2>Phiên đã kết thúc</h2><p>{summary.status} · {summary.reps} chu kỳ · {summary.error||'Không có lỗi runtime được báo'}</p></section>}
    <footer style={{marginTop:20,fontSize:13}}><p>Form: chưa đánh giá. Squat và curl đang nghiệm thu; ba bài còn lại chưa nghiệm thu. TTS chỉ phát tại Pi.</p><p>Không có live video từ xa. Dữ liệu thử, không dùng để quyết định điều trị.</p><button style={input} disabled={!active} onClick={download}>Xuất timing trình duyệt</button><p>Timing render là callback trình duyệt, chưa phải đo màn hình vật lý; đồng hồ chưa được kiểm chứng.</p></footer>
  </main>;
}
