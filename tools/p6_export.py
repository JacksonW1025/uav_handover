#!/usr/bin/env python3
"""Export P6 runs for model fitting and kernel checks without the raw ULog (config p6.export).

Per run export/<run directory name>/:
  trace.csv.gz  one row per active RAPTOR inference (research_memory KIND_STEP, RAPTOR owns the motors), from the setup
                entry to the N->C (takeoff and landing are classic and omitted). Columns:
    t_s, px4_us          gyro-sample time of the RAPTOR cycle; t_s relative to the run's time origin (summary 'time_origin')
    ep_u, ep_w, ev_u, ev_w           UNCLIPPED position / velocity error (vehicle - RAPTOR target), horizontal, in the
                                     motion-axis frame: u along the planned motion axis, w = u rotated +90 deg (to the
                                     right, NED) -- a fixed horizontal rotation of the target-yaw frame
    ep_u_clip, ep_w_clip, ev_u_clip, ev_w_clip   the clipped error the network saw (research_memory.policy_input [0:2],
                                     [12:14], target-yaw FLU frame) rotated into the same u/w frame
    ep_f_clip, ep_l_clip, ev_f_clip, ev_l_clip   the same clipped inputs as seen (target-yaw frame: forward, left);
                                     clipping acts per axis in THIS frame (+-0.5 m, +-1.0 m/s)
    ep_f, ep_l, ev_f, ev_l           unclipped errors in the target-yaw frame (forward, left)
    ep_z, ev_z                       unclipped vertical errors (NED, down positive)
    a_u, a_w, a_z                    vehicle acceleration (vehicle_local_position ax, ay, az of the sample RAPTOR used,
                                     i.e. the EKF2 output acceleration, NED), horizontal projected on u/w
    v_u, v_w                         vehicle velocity on u/w (same sample)
    tilt_deg                         vehicle_attitude (latest at or before the cycle)
    alt_loss_m                       altitude below the altitude at the time origin (positive = lower)
    target_yaw_rad, target_mode      RAPTOR's target: external (latest external setpoint read), t0_capture (zero-velocity
                                     capture hold, RTGT=0), t1_profile (speed-matched capture / T1 profile row)
    gap_active                       1 between the last setpoint reception before a planned interruption and the first after
    recon_ok                         1 when the reconstruction matched the vehicle-state sample and a target
  summary.json  run identity, outcome, maxima, events with the unclipped state just before and at/after each event,
                resume jumps with the P5 predictions, reconstruction residual.
export/manifest.json lists every exported run (updated in place: one entry per run name).

Reconstruction (validated per run on the unclipped components of policy_input, residual reported): vehicle state =
vehicle_local_position sample named by research_timing.local_position_sample; target = the external setpoint RAPTOR read
(raptor_status reception cycles; for a cycle without a raptor_status row the latest logged setpoint counts as read unless
the next status row reads it) or RAPTOR's research_target capture / T1 profile row of a later cycle.
"""
import argparse,datetime,gzip,hashlib,io,json,math,os,subprocess
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_metrics import tilt_deg
ROOT=Path(__file__).resolve().parents[1]
TOPICS=['research_memory','research_timing','research_target','trajectory_setpoint','vehicle_local_position','raptor_status','vehicle_attitude']
COLS=['t_s','px4_us','ep_u','ep_w','ev_u','ev_w','ep_u_clip','ep_w_clip','ev_u_clip','ev_w_clip','ep_f_clip','ep_l_clip','ev_f_clip','ev_l_clip',
      'ep_f','ep_l','ev_f','ev_l','ep_z','ev_z','a_u','a_w','a_z','v_u','v_w','tilt_deg','alt_loss_m','target_yaw_rad','target_mode','gap_active','recon_ok']
MAX_BYTES=1_000_000;THIN_HZ=50;EVENT_KEEP_S=3.0

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def reconstruct(T):
    """Per active RAPTOR inference: vehicle state used, RAPTOR target used, clipped inputs, unclipped errors (target frame)."""
    m=T['research_memory'];tm=T['research_timing'];tg=T['research_target'];sp=T['trajectory_setpoint'];lp=T['vehicle_local_position'];st=T['raptor_status']
    ms=np.asarray(m['timestamp_sample'],np.int64);w=np.flatnonzero((np.asarray(m['kind'])==1)&(np.asarray(m['active'])==1));s=ms[w]
    tts=np.asarray(tm['timestamp_sample'],np.int64);called=np.asarray(tm['executor_called']).astype(bool);key=tts[called];ls=np.asarray(tm['local_position_sample'],np.int64)[called]
    it=np.minimum(np.searchsorted(key,s),len(key)-1);ok=key[it]==s
    lts=np.asarray(lp['timestamp_sample'],np.int64);il=np.minimum(np.searchsorted(lts,ls[it]),len(lts)-1);ok&=lts[il]==ls[it]
    X=lambda d,keys,idx:np.stack([np.asarray(d[k],float)[idx] for k in keys],1)
    pos=X(lp,['x','y','z'],il);vel=X(lp,['vx','vy','vz'],il);acc=X(lp,['ax','ay','az'],il)
    spt=np.asarray(sp['timestamp'],np.int64)
    sts=np.asarray(st['timestamp_sample'],np.int64);flag=np.asarray(st['subscription_update_trajectory_setpoint'])==1
    order=np.argsort(sts,kind='stable');sts,flag=sts[order],flag[order];stat=dict(zip(sts.tolist(),flag.tolist()))
    tgs=np.asarray(tg['timestamp_sample'],np.int64);tk=np.asarray(tg['kind'])
    trow={int(tgs[i]):int(i) for i in np.flatnonzero((tk==1)|(tk==2))}
    cycles=sorted(set(s.tolist())|set(stat)|set(trow));cur=-1;src=None;assign={}
    for c in cycles:
        latest=int(np.searchsorted(spt,c,side='right'))-1
        if c in stat:
            if stat[c] and latest>cur:cur=latest;src=('sp',cur)
        elif latest>cur:
            # No raptor_status row for this cycle: the setpoint counts as read here unless the next status row reads it.
            # A status row >= 10 ms after the arrival (setpoints are stamped up to a few ms before they can be read) that
            # did not read it means it is an old setpoint that RAPTOR never took (e.g. the pre-arming DDS check).
            k=int(np.searchsorted(sts,c,side='right'));kp=k-1
            read_later=k<len(sts) and flag[k] and int(np.searchsorted(spt,sts[k],side='right'))-1==latest
            missed=kp>=0 and sts[kp]>=spt[latest]+10000
            if not read_later and not missed:cur=latest;src=('sp',cur)
        if c in trow:src=('tg',trow[c])
        assign[c]=src
    n=len(s);P=np.full((n,3),np.nan);V=np.full((n,3),np.nan);Y=np.full(n,np.nan);mode=np.array(['none']*n,dtype=object)
    for q,c in enumerate(s.tolist()):
        a=assign.get(c)
        if a is None:continue
        d,i=(sp,a[1]) if a[0]=='sp' else (tg,a[1])
        P[q]=[d[f'position[{k}]'][i] for k in range(3)];V[q]=[d[f'velocity[{k}]'][i] for k in range(3)];Y[q]=float(d['yaw'][i])
        mode[q]='external' if a[0]=='sp' else ('t0_capture' if int(tg['mode'][i])==0 else 't1_profile')
    ok&=np.isfinite(Y)
    pin=np.stack([np.asarray(m[f'policy_input[{k}]'],float)[w] for k in range(22)],1)
    e=pos-P;ev=vel-V;c_,s_=np.cos(Y),np.sin(Y)
    to_t=lambda x:np.stack([c_*x[:,0]+s_*x[:,1],s_*x[:,0]-c_*x[:,1],-x[:,2]],1)  # NED -> target-yaw FLU (mc_raptor observe())
    pf,vf=to_t(e),to_t(ev)
    up=ok[:,None]&(np.abs(pin[:,0:3])<0.5*(1-1e-6));uv=ok[:,None]&(np.abs(pin[:,12:15])<1.0*(1-1e-6))
    rp=np.abs(pf-pin[:,0:3])[up];rv=np.abs(vf-pin[:,12:15])[uv]
    resid={'position_max_abs':float(rp.max()) if rp.size else None,'velocity_max_abs':float(rv.max()) if rv.size else None,
           'components_over_1e-4':int((rp>1e-4).sum()+(rv>1e-4).sum()),'components_checked':int(rp.size+rv.size),'rows':int(n),'rows_unmatched':int((~ok).sum()),
           'rows_with_clipping':int((~(up.all(1)&uv.all(1))&ok).sum())}
    return {'s':s,'ok':ok,'pos':pos,'vel':vel,'acc':acc,'e':e,'ev':ev,'pf':pf,'vf':vf,'pin':pin,'yaw':Y,'mode':mode,'resid':resid}

def uw(x,axis):
    perp=np.array([-axis[1],axis[0]]);return x[:,:2]@axis[:2],x[:,:2]@perp

def from_target_frame(f,l,yaw):
    c,s=np.cos(yaw),np.sin(yaw);return np.stack([c*f+s*l,s*f-c*l],1)  # inverse of the horizontal part of to_t

def time_origin(m6):
    if m6.get('kind')=='p6_ident':
        t=(m6.get('times_px4_us') or {}).get('family_start');return t,'family start: first logged setpoint leaving the reference hold (step / target appears / acceleration start)'
    g=m6.get('gaps') or []
    if g:return g[0]['last_reception_px4_us'],'last setpoint reception before the first interruption'
    og=(m6.get('p6') or {}).get('open_gap') or {}
    if og.get('open_gap'):return og['last_arrival_px4_us'],'last setpoint reception before the interruption (run aborted inside it)'
    t=(m6.get('times_px4_us') or {}).get('profile_start');return t,'profile start (no interruption measured)'

def gap_windows(m6):
    if m6.get('kind')=='p6_ident':
        g=m6.get('gap');return [(g['last_reception_px4_us'],g['first_reception_px4_us'])] if g else []
    w=[(g['last_reception_px4_us'],g['first_reception_px4_us']) for g in m6.get('gaps') or []]
    og=(m6.get('p6') or {}).get('open_gap') or {}
    if og.get('open_gap'):w.append((og['last_arrival_px4_us'],og['raptor_last_active_px4_us']+1))
    return w

def export_run(run,out,batch,row,stage):
    run=ROOT/run;cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text())
    m6=json.loads((run/'p6-metrics.json').read_text());events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
    u=ULog(str(run/'flight.ulg'),TOPICS);T={d.name:d.data for d in u.data_list if d.multi_id==0}
    R=reconstruct(T);s=R['s'];axis=np.asarray(cfg['p2_profile']['motion_axis_ned'],float)
    t0,t0_def=time_origin(m6);t0=int(t0) if t0 is not None else int(s[0])
    att=T['vehicle_attitude'];at=np.asarray(att['timestamp'],np.int64);ia=np.maximum(np.searchsorted(at,s,side='right')-1,0)
    tilt=tilt_deg(np.stack([np.asarray(att[f'q[{i}]'],float) for i in range(4)],1)[ia])
    lp=T['vehicle_local_position'];lts=np.asarray(lp['timestamp_sample'],np.int64);z0=float(np.asarray(lp['z'],float)[max(int(np.searchsorted(lts,t0,side='right'))-1,0)])
    ep_u,ep_w=uw(R['e'],axis);ev_u,ev_w=uw(R['ev'],axis);a_u,a_w=uw(R['acc'],axis);v_u,v_w=uw(R['vel'],axis)
    cp=from_target_frame(R['pin'][:,0],R['pin'][:,1],R['yaw']);cv=from_target_frame(R['pin'][:,12],R['pin'][:,13],R['yaw'])
    cpu,cpw=uw(cp,axis);cvu,cvw=uw(cv,axis)
    gaps=gap_windows(m6);ga=np.zeros(len(s),int)
    for a,b in gaps:ga[(s>=a)&(s<b)]=1
    data={'t_s':(s-t0)/1e6,'px4_us':s,'ep_u':ep_u,'ep_w':ep_w,'ev_u':ev_u,'ev_w':ev_w,'ep_u_clip':cpu,'ep_w_clip':cpw,'ev_u_clip':cvu,'ev_w_clip':cvw,
          'ep_f_clip':R['pin'][:,0],'ep_l_clip':R['pin'][:,1],'ev_f_clip':R['pin'][:,12],'ev_l_clip':R['pin'][:,13],'ep_f':R['pf'][:,0],'ep_l':R['pf'][:,1],'ev_f':R['vf'][:,0],'ev_l':R['vf'][:,1],
          'ep_z':R['e'][:,2],'ev_z':R['ev'][:,2],'a_u':a_u,'a_w':a_w,'a_z':R['acc'][:,2],'v_u':v_u,'v_w':v_w,'tilt_deg':tilt,'alt_loss_m':R['pos'][:,2]-z0,
          'target_yaw_rad':R['yaw'],'target_mode':R['mode'],'gap_active':ga,'recon_ok':R['ok'].astype(int)}
    # Events (PX4 times): interruptions (capture, resume), identification family events, end of the stream.
    ev=[]
    if m6.get('kind')=='p6_ident':
        ev.append(('family_start',t0,{}))
        sw=next((e for e in events if e['event']=='p6_chase_switch'),None)
        if sw:ev.append(('chase_deceleration_start',t0+int(round(float(sw['family_time_s'])*1e6)),{'reason':sw['reason'],'runner_lag_m':sw['along_axis_lag_m']}))
        g=m6.get('gap')
        if g:
            if g.get('capture'):ev.append(('capture',g['capture']['px4_us'],{'mode':g['capture']['mode']}))
            ev.append(('resume',g['first_reception_px4_us'],{'silence_s':g['silence_s']}))
    for k,g in enumerate(m6.get('gaps') or []):
        if g.get('capture'):ev.append(('capture',g['capture']['px4_us'],{'gap':k,'mode':g['capture']['mode'],'decel_m_s2':g['capture']['decel_m_s2'],'captured_speed_m_s':float(np.hypot(*g['capture']['vehicle_velocity_ned_m_s'][:2]))}))
        r=g.get('resume') or {};info={'gap':k,'silence_s':g.get('silence_s'),'planned_D_s':g.get('planned_D_s')}
        if r:
            v=float(cfg['p1_speed_m_s']);a=float(cfg['p2_treatment_parameters']['rtdec']);mode=(g.get('capture') or {}).get('mode');lag=-float(r['offset_at_capture_along_axis_m']);Dc=float(g['planned_D_s'])-0.2
            if mode==0:formula=lag+v*Dc
            elif Dc<v/a:formula=lag+.5*a*Dc*Dc
            else:formula=lag+v*Dc-v*v/(2*a)
            info.update({'jump_along_axis_m':r['jump_along_axis_m'],'velocity_jump_along_axis_m_s':r['velocity_jump_along_axis_m_s'],'prediction_exact_m':r['prediction_m'],
                'prediction_formula_m':formula,'formula':'P5 report: lag at the capture + 0.5*a*(D-0.2)^2 while T1 decelerates, lag + v*(D-0.2) - v^2/(2a) after it stopped, lag + v*(D-0.2) for T0 (planned D and v)',
                'lag_at_capture_m':lag,'capture_to_resume_s':r['capture_to_resume_s'],'estimate_half_a_D2_m':r.get('estimate_half_a_D2_m')})
        ev.append(('resume',g['first_reception_px4_us'],info))
    og=(m6.get('p6') or {}).get('open_gap') or {}
    if og.get('open_gap') and og.get('capture'):
        ev.append(('capture',og['capture']['px4_us'],{'gap':og.get('gap_index'),'mode':og['capture']['mode'],'captured_speed_m_s':og['capture']['captured_speed_m_s'],'open_gap':True}))
    if og.get('failure_reason') or m6.get('aborted'):
        fa=next((e for e in events if e['event']=='failure'),None);ev.append(('runner_abort',int(og.get('raptor_last_active_px4_us') or s[-1]),{'reason':fa['reason'] if fa else None,'time':'last RAPTOR-active status row' if og.get('raptor_last_active_px4_us') else 'last RAPTOR inference'}))
    se=next((e for e in events if e['event'] in ['p5_stream_ended','p6_stream_ended']),None)
    if se:ev.append(('stream_end',int(se['end_bound_px4_us']),{}))
    keys=['ep_u','ev_u','ep_w','ev_w','a_u','a_w','ep_u_clip','ev_u_clip','ep_w_clip','ev_w_clip','tilt_deg','alt_loss_m','v_u']
    def state(i):return None if i<0 or i>=len(s) else {'t_s':float(data['t_s'][i]),'target_mode':str(R['mode'][i]),**{k:float(data[k][i]) for k in keys}}
    evs=[]
    for name,t,info in sorted(ev,key=lambda x:x[1]):
        i=int(np.searchsorted(s,t,side='left'))
        if name=='resume':
            # The resumed setpoint is logged on arrival and read by RAPTOR in its next cycle: first cycle on it.
            j=np.flatnonzero((s>=t)&(R['mode']=='external'));i=int(j[0]) if len(j) else i
        evs.append({'event':name,'px4_us':int(t),'t_s':(t-t0)/1e6,**info,'state_before':state(i-1),'state_at_or_after':state(i)})
    # CSV (downsampled outside +-3 s of events only if the compressed trace exceeds 1 MB).
    def csv(idx):
        b=io.StringIO();b.write(','.join(COLS)+'\n')
        for i in idx:
            b.write(','.join(f'{data[c][i]:.7g}' if isinstance(data[c][i],(float,np.floating)) else str(data[c][i]) for c in COLS)+'\n')
        return gzip.compress(b.getvalue().encode(),compresslevel=9,mtime=0)
    idx=np.arange(len(s));blob=csv(idx);thinned=False
    if len(blob)>MAX_BYTES:
        near=np.zeros(len(s),bool)
        for e in evs:near|=np.abs(s-e['px4_us'])<=EVENT_KEEP_S*1e6
        bucket=(s//int(1e6/THIN_HZ));first=np.r_[True,bucket[1:]!=bucket[:-1]]
        idx=np.flatnonzero(near|first);blob=csv(idx);thinned=True
    d=out/run.name;d.mkdir(parents=True,exist_ok=True);(d/'trace.csv.gz').write_bytes(blob)
    m=m6.get('whole') or {};tt=m6.get('tilt') or (m6.get('p6') or {}).get('tilt') or {}
    fo=m6.get('flight_outcome') or {};io_=m6.get('ident_outcome') or {}
    direc=m6.get('direction') or {}
    if m6.get('kind')=='p6_ident':
        i=int(np.searchsorted(s,t0));direc={'planned_axis_ned':list(axis),'speed_along_axis_at_origin_m_s':float(v_u[i]) if i<len(s) else None}
        tail=np.flatnonzero((s>=t0)&(np.abs(v_u)>0.3))
        if len(tail):vv=R['vel'][tail];direc['realized_deg_mean_moving']=float(math.degrees(math.atan2(vv[:,1].mean(),vv[:,0].mean())))
    summary={'run':run.name,'run_directory':os.path.relpath(run,ROOT),'batch':batch,'stage':stage,'kind':meta['experiment_type'],'condition':cfg.get('p1_condition'),
        'treatment':cfg.get('p2_treatment'),'treatment_parameters':cfg.get('p2_treatment_parameters'),'sim_seed':(cfg.get('p4_independence') or {}).get('sim_seed'),
        'planned_speed_m_s':cfg.get('p1_speed_m_s'),'motion_axis_ned':list(axis),'condition_spec':cfg.get('p5_condition_spec') or cfg.get('p6_condition_spec'),
        'profile':cfg.get('p2_profile'),'direction':direc,
        'batch_status':{k:row.get(k) for k in ['status','accepted','flight_failure','infrastructure_ok']} if row else None,
        'outcome':io_.get('class') if m6.get('kind')=='p6_ident' else fo.get('outcome'),'flight_failure_reasons':fo.get('reasons'),'ident_exceeded_45':io_.get('ident_exceeded_45'),
        'aborted':m6.get('aborted'),'abort_reason':m6.get('failure_reason'),
        'max_tilt_deg':tt.get('max_tilt_deg'),'max_tilt_at_s':tt.get('max_tilt_at_s'),'first_at_or_above_45_s':tt.get('first_at_or_above_45_s'),
        'max_altitude_loss_m':m.get('max_altitude_loss_m'),'max_angular_rate_rad_s':m.get('max_angular_rate_rad_s'),'motor_saturation_any_s':m.get('motor_saturation_any_s'),
        'time_origin':{'px4_us':t0,'definition':t0_def},'events':evs,'reconstruction':R['resid'],
        'trace':{'file':'trace.csv.gz','rows':int(len(idx)),'rows_full_rate':int(len(s)),'downsampled':thinned,'bytes':len(blob),
                 'downsampling_rule':f'{THIN_HZ} Hz outside +-{EVENT_KEEP_S} s of the events' if thinned else None,'columns':COLS},
        'sources':{'unclipped_error':'vehicle_local_position sample used by RAPTOR (research_timing.local_position_sample) minus RAPTOR target (external setpoint read / research_target row)',
                   'clipped_error':'research_memory.policy_input [0:2] position, [12:14] velocity (target-yaw FLU frame)','acceleration':'vehicle_local_position ax, ay, az of the same sample (EKF2)',
                   'tilt':'vehicle_attitude','metrics':'p6-metrics.json'}}
    (d/'summary.json').write_text(json.dumps(summary,indent=1,ensure_ascii=False,allow_nan=False,default=float)+'\n')
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batches',nargs='+',type=Path);p.add_argument('--out',type=Path,default=ROOT/'export');a=p.parse_args()
    out=a.out.resolve();out.mkdir(exist_ok=True);mf=out/'manifest.json'
    man=json.loads(mf.read_text()) if mf.exists() else {'runs':{}}
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain','--','tools/p6_export.py'],cwd=ROOT,text=True).strip())
    bad=[]
    for b in a.batches:
        b=b.resolve();res=json.loads((b/'results.json').read_text());cand=json.loads((b/'candidate.json').read_text());stage=b.name.split('-')[-1]
        for row in res['runs']:
            run=ROOT/row['directory']
            if row.get('status')=='NOT_RUN' or not (run/'flight.ulg').exists() or not (run/'p6-metrics.json').exists():continue
            sm=export_run(row['directory'],out,str(b.relative_to(ROOT)),row,stage)
            r=sm['reconstruction']
            if r['components_over_1e-4']:bad.append((run.name,r['components_over_1e-4']))
            man['runs'][run.name]={'export':f'{run.name}/','batch':str(b.relative_to(ROOT)),'stage':stage,'run_directory':row['directory'],'kind':row['kind'],'condition':row['condition'],
                'treatment':row['treatment'],'sim_seed':row.get('sim_seed'),'outcome':sm['outcome'],'accepted':row.get('accepted'),'flight_failure':row.get('flight_failure'),
                'candidate_project_commit':cand['project_head'],'trace_bytes':sm['trace']['bytes'],'reconstruction_components_over_1e-4':r['components_over_1e-4']}
            print(run.name,sm['outcome'],sm['trace']['bytes'],r['position_max_abs'],r['velocity_max_abs'],r['components_over_1e-4'],flush=True)
    man.update({'updated_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'export_script':'tools/p6_export.py','export_script_sha256':sha(ROOT/'tools/p6_export.py'),
        'export_script_commit':head,'export_script_modified_since_commit':dirty,'description':(__doc__ or '').strip(),
        'total_bytes':sum(f.stat().st_size for f in out.rglob('*') if f.is_file() and f.name!='manifest.json')})
    man['runs']=dict(sorted(man['runs'].items()));mf.write_text(json.dumps(man,indent=1,ensure_ascii=False)+'\n')
    print('runs',len(man['runs']),'bytes',man['total_bytes'],'reconstruction mismatches',bad)
    return 0
if __name__=='__main__':raise SystemExit(main())
