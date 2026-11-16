"""Render local TV fixtures; no webcam, network or patient data. Also microbench."""
import argparse
import json
import time
from pathlib import Path
import cv2
import numpy as np
from product_v1.tv_state import TVPresentation
from product_v1.tv_renderer import TVRenderer


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    health=dict(online=True,paired=True,audio_ready=True,storage_fault=False)
    renderer=TVRenderer();p=TVPresentation(0)
    # Original vector avatar to judge framing; this is not a webcam capture.
    frame=np.full((480,640,3),(173,184,184),dtype=np.uint8)
    cv2.rectangle(frame,(0,365),(640,480),(125,140,145),-1)
    cv2.line(frame,(0,365),(640,365),(157,170,172),3)
    cv2.ellipse(frame,(320,444),(100,14),0,0,360,(106,119,124),-1)
    cv2.line(frame,(290,285),(280,425),(47,64,73),32,cv2.LINE_AA)
    cv2.line(frame,(349,285),(360,425),(47,64,73),32,cv2.LINE_AA)
    cv2.line(frame,(270,432),(285,432),(27,38,45),16,cv2.LINE_AA)
    cv2.line(frame,(356,432),(376,432),(27,38,45),16,cv2.LINE_AA)
    cv2.ellipse(frame,(320,214),(62,91),0,0,360,(66,112,102),-1)
    cv2.line(frame,(276,159),(205,186),(66,112,102),27,cv2.LINE_AA)
    cv2.line(frame,(205,186),(150,228),(151,183,210),22,cv2.LINE_AA)
    cv2.line(frame,(364,159),(435,186),(66,112,102),27,cv2.LINE_AA)
    cv2.line(frame,(435,186),(490,228),(151,183,210),22,cv2.LINE_AA)
    cv2.rectangle(frame,(308,112),(332,146),(151,183,210),-1)
    cv2.ellipse(frame,(320,89),(30,39),0,0,360,(151,183,210),-1)
    cv2.ellipse(frame,(320,72),(31,25),0,180,360,(37,49,56),-1)
    joints=[(276,159),(364,159),(205,186),(435,186),(150,228),(490,228),(290,285),(349,285),(285,355),(355,355),(280,425),(360,425)]
    for a,b in [(0,1),(0,2),(2,4),(1,3),(3,5),(0,6),(1,7),(6,7),(6,8),(8,10),(7,9),(9,11)]:
        cv2.line(frame,joints[a],joints[b],(154,234,185),2,cv2.LINE_AA)
    for point in joints:cv2.circle(frame,point,3,(235,250,240),-1)
    views={}
    views['idle']=p.view(0,health,False)
    views['offline']=p.view(1,{**health,'online':False},False)
    views['dimmed']=p.view(190,health,False)
    p.begin(dict(exercise='shoulder_abduction',requested_side='both',goal=dict(mode='sets',sets=3,reps_per_set=5,rest_s=30)))
    views['preparing']=p.view(1,health,False)
    p.progress(dict(workload_phase='aligning',tracking_status='tracking',phase='READY',set_number=1),'aligning',3)
    views['countdown']=p.view(2,health,True)
    p.progress(dict(workload_phase='working',tracking_status='tracking',phase='AT_TARGET',set_number=2,rep_in_set=4,reps=9),'running')
    views['working']=p.view(3,health,True)
    p.progress(dict(workload_phase='resting',set_number=2,rep_in_set=5,reps=10,rest_remaining_s=18),'running')
    views['resting']=p.view(4,health,True)
    p.progress(dict(workload_phase='working',tracking_status='lost',reason='landmark_16_out_of_frame',set_number=2,rep_in_set=4),'running')
    views['tracking_lost']=p.view(5,health,True)
    p.finish(dict(exercise='shoulder_abduction',error='goal_complete',reps=15,completed_sets=3,active_s=132,goal=dict(mode='sets',sets=3)),10)
    views['summary']=p.view(11,health,False)
    times=[]
    for name,view in views.items():
        cv2.imwrite(str(args.output/(name+'.png')),renderer.render((1280,720),view,frame if view.get('camera_fresh') else None))
    # Alternating frames, unchanged text measures the hot camera render path.
    view=views['working'];renderer.render((1920,1080),view,frame)
    for _ in range(80):
        before=time.perf_counter();renderer.render((1920,1080),view,frame);times.append((time.perf_counter()-before)*1000)
    cold=[]
    for n in range(12):
        before=time.perf_counter();renderer.render((1920,1080),{**view,'number':str(n)},frame);cold.append((time.perf_counter()-before)*1000)
    report=dict(camera_composite_ms_median=float(np.median(times)),camera_composite_ms_p95=float(np.percentile(times,95)),
                text_change_ms_median=float(np.median(cold)),physical_acceptance=False)
    (args.output/'render-benchmark.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
