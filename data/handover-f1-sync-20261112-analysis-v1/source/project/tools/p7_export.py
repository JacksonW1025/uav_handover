#!/usr/bin/env python3
"""Export P7 runs in the P6 format (tools/p6_export.py; config p7.export) plus the rate-limited recovery.

Per run export/<run directory name>/:
  trace.csv.gz  the P6 columns (see tools/p6_export.py; same definitions, same reconstruction from RAPTOR's own inputs and
                the same validation against research_memory.policy_input), with target_mode 'recovery' in cycles where the
                network observed the virtual target (research_recovery STEP row of that cycle), plus:
    vt_active                    1 when the network observed the virtual target in this cycle
    tgt_p_u, tgt_p_w             position of the target the network observed (external setpoint / capture / T1 profile /
                                 virtual target) relative to the line centre (RAPTOR's hover capture), on u / w
    tgt_v_u, tgt_v_w             its velocity on u / w
    traj_p_u, traj_v_u           the original time-parameterized trajectory at this cycle (latest logged setpoint row
                                 advanced by its velocity; exact on the cruise and inside interruptions), relative to the
                                 line centre
    p_u, p_w                     vehicle position (the sample RAPTOR used) relative to the line centre
  summary.json  the P6 summary plus events 'recovery_start' / 'recovery_end' (with reason) and a 'recovery' list per resume:
                times of capture, resume, recovery start and end, catch-up duration (end CONVERGED - start), the target
                jump the network saw, and the lag behind the original trajectory over the 6 s after the resume (maximum and
                value at the window end; p7-metrics lag block).
export/manifest.json: the P6 manifest, entries added per run (export_script recorded per entry); top-level 'p7' block.
"""
import argparse,datetime,gzip,io,json,math,os,subprocess
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_metrics import tilt_deg
import p6_export
from p6_export import uw,from_target_frame,time_origin,gap_windows,sha
from p5_metrics import receptions,setpoint_rows
ROOT=Path(__file__).resolve().parents[1]
TOPICS=p6_export.TOPICS+['research_recovery']
COLS=p6_export.COLS+['vt_active','tgt_p_u','tgt_p_w','tgt_v_u','tgt_v_w','traj_p_u','traj_v_u','p_u','p_w']
MAX_BYTES,THIN_HZ,EVENT_KEEP_S=p6_export.MAX_BYTES,p6_export.THIN_HZ,p6_export.EVENT_KEEP_S

def reconstruct(T):
    """P6 reconstruction, then the recovery cycles: target = the virtual target of that cycle's research_recovery STEP row
    (horizontal virtual target, vertical setpoint), residual recomputed over all rows."""
    R=p6_export.reconstruct(T);s=R['s'];P=R['pos']-R['e'];V=R['vel']-R['ev'];vt=np.zeros(len(s),bool)
    rc=T.get('research_recovery')
    if rc is not None:
        k=np.flatnonzero(np.asarray(rc['kind'])==2);ts=np.asarray(rc['timestamp_sample'],np.int64)[k]
        pos={int(t):i for t,i in zip(ts,k)};q=np.flatnonzero(np.isin(s,ts))
        for j in q:
            i=pos[int(s[j])];P[j]=[float(rc[f'target_position[{c}]'][i]) for c in range(3)];V[j]=[float(rc[f'target_velocity[{c}]'][i]) for c in range(3)];vt[j]=True
        R['mode']=np.where(vt,'recovery',R['mode'])
    ok,pin,Y=R['ok'],R['pin'],R['yaw'];e=R['pos']-P;ev=R['vel']-V;c_,s_=np.cos(Y),np.sin(Y)
    to_t=lambda x:np.stack([c_*x[:,0]+s_*x[:,1],s_*x[:,0]-c_*x[:,1],-x[:,2]],1)
    pf,vf=to_t(e),to_t(ev)
    up=ok[:,None]&(np.abs(pin[:,0:3])<0.5*(1-1e-6));uv=ok[:,None]&(np.abs(pin[:,12:15])<1.0*(1-1e-6))
    rp=np.abs(pf-pin[:,0:3])[up];rv=np.abs(vf-pin[:,12:15])[uv]
    R['resid']={'position_max_abs':float(rp.max()) if rp.size else None,'velocity_max_abs':float(rv.max()) if rv.size else None,
           'components_over_1e-4':int((rp>1e-4).sum()+(rv>1e-4).sum()),'components_checked':int(rp.size+rv.size),'rows':int(len(s)),'rows_unmatched':int((~ok).sum()),
           'rows_with_clipping':int((~(up.all(1)&uv.all(1))&ok).sum()),'rows_on_virtual_target':int(vt.sum()),
           'virtual_target_components_over_1e-4':int(((np.abs(pf-pin[:,0:3])>1e-4)&up)[vt].sum()+((np.abs(vf-pin[:,12:15])>1e-4)&uv)[vt].sum())}
    R.update({'e':e,'ev':ev,'pf':pf,'vf':vf,'P':P,'V':V,'vt':vt})
    return R

def export_run(run,out,batch,row,stage):
    run=ROOT/run;cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text())
    m7=json.loads((run/'p7-metrics.json').read_text());events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
    u=ULog(str(run/'flight.ulg'),TOPICS);T={d.name:d.data for d in u.data_list if d.multi_id==0}
    R=reconstruct(T);s=R['s'];axis=np.asarray(cfg['p2_profile']['motion_axis_ned'],float);perp=np.array([-axis[1],axis[0]])
    origin=np.asarray(next(e for e in events if e['event']=='p1_reference_origin')['origin_ned_m'],float)
    t0,t0_def=time_origin(m7);t0=int(t0) if t0 is not None else int(s[0])
    att=T['vehicle_attitude'];at=np.asarray(att['timestamp'],np.int64);ia=np.maximum(np.searchsorted(at,s,side='right')-1,0)
    tilt=tilt_deg(np.stack([np.asarray(att[f'q[{i}]'],float) for i in range(4)],1)[ia])
    lp=T['vehicle_local_position'];lts=np.asarray(lp['timestamp_sample'],np.int64);z0=float(np.asarray(lp['z'],float)[max(int(np.searchsorted(lts,t0,side='right'))-1,0)])
    ep_u,ep_w=uw(R['e'],axis);ev_u,ev_w=uw(R['ev'],axis);a_u,a_w=uw(R['acc'],axis);v_u,v_w=uw(R['vel'],axis)
    cp=from_target_frame(R['pin'][:,0],R['pin'][:,1],R['yaw']);cv=from_target_frame(R['pin'][:,12],R['pin'][:,13],R['yaw'])
    cpu,cpw=uw(cp,axis);cvu,cvw=uw(cv,axis)
    gaps=gap_windows(m7);ga=np.zeros(len(s),int)
    for a,b in gaps:ga[(s>=a)&(s<b)]=1
    sp=T['trajectory_setpoint'];spt,spp,spv=setpoint_rows(sp,receptions(T['raptor_status'],sp))
    i=np.maximum(np.searchsorted(spt,s,side='right')-1,0);traj=spp[i]+spv[i]*((s-spt[i])/1e6)[:,None]
    rel=lambda x:(x[:,:2]-origin[:2])
    data={'t_s':(s-t0)/1e6,'px4_us':s,'ep_u':ep_u,'ep_w':ep_w,'ev_u':ev_u,'ev_w':ev_w,'ep_u_clip':cpu,'ep_w_clip':cpw,'ev_u_clip':cvu,'ev_w_clip':cvw,
          'ep_f_clip':R['pin'][:,0],'ep_l_clip':R['pin'][:,1],'ev_f_clip':R['pin'][:,12],'ev_l_clip':R['pin'][:,13],'ep_f':R['pf'][:,0],'ep_l':R['pf'][:,1],'ev_f':R['vf'][:,0],'ev_l':R['vf'][:,1],
          'ep_z':R['e'][:,2],'ev_z':R['ev'][:,2],'a_u':a_u,'a_w':a_w,'a_z':R['acc'][:,2],'v_u':v_u,'v_w':v_w,'tilt_deg':tilt,'alt_loss_m':R['pos'][:,2]-z0,
          'target_yaw_rad':R['yaw'],'target_mode':R['mode'],'gap_active':ga,'recon_ok':R['ok'].astype(int),
          'vt_active':R['vt'].astype(int),'tgt_p_u':rel(R['P'])@axis[:2],'tgt_p_w':rel(R['P'])@perp,'tgt_v_u':R['V'][:,:2]@axis[:2],'tgt_v_w':R['V'][:,:2]@perp,
          'traj_p_u':rel(traj)@axis[:2],'traj_v_u':spv[i][:,:2]@axis[:2],'p_u':rel(R['pos'])@axis[:2],'p_w':rel(R['pos'])@perp}
    ev=[];rec=(m7.get('p7') or {}).get('recovery') or {};lag={x['gap']:x for x in (m7.get('p7') or {}).get('lag') or []};recs={x['gap']:x for x in rec.get('recoveries') or []}
    v=float(cfg['p1_speed_m_s']);a_t=float(cfg['p2_treatment_parameters']['rtdec']);rlist=[]
    for k,g in enumerate(m7.get('gaps') or []):
        cap=g.get('capture')
        if cap:ev.append(('capture',cap['px4_us'],{'gap':k,'mode':cap['mode'],'decel_m_s2':cap['decel_m_s2'],'captured_speed_m_s':float(np.hypot(*cap['vehicle_velocity_ned_m_s'][:2]))}))
        r=g.get('resume') or {};info={'gap':k,'silence_s':g.get('silence_s'),'planned_D_s':g.get('planned_D_s')}
        if r:
            mode=(cap or {}).get('mode');lagc=-float(r['offset_at_capture_along_axis_m']);Dc=float(g['planned_D_s'])-0.2
            formula=lagc+v*Dc if mode==0 else (lagc+.5*a_t*Dc*Dc if Dc<v/a_t else lagc+v*Dc-v*v/(2*a_t))
            info.update({'setpoint_jump_along_axis_m':r['jump_along_axis_m'],'setpoint_velocity_jump_along_axis_m_s':r['velocity_jump_along_axis_m_s'],'prediction_exact_m':r['prediction_m'],
                'prediction_formula_m':formula,'lag_at_capture_m':lagc,'capture_to_resume_s':r['capture_to_resume_s']})
        ev.append(('resume',g['first_reception_px4_us'],info))
        rc=recs.get(g['index'],{})
        if rc.get('start_px4_us') is not None:ev.append(('recovery_start',rc['start_px4_us'],{'gap':k,'observed_jump_along_axis_m':rc.get('observed_jump_along_axis_m')}))
        if rc.get('end_px4_us') is not None:ev.append(('recovery_end',rc['end_px4_us'],{'gap':k,'reason':rc.get('end'),'catch_up_s':rc.get('catch_up_s')}))
        lg=lag.get(g['index'],{})
        rlist.append({'gap':k,'capture_px4_us':(cap or {}).get('px4_us'),'capture_t_s':((cap or {}).get('px4_us',t0)-t0)/1e6 if cap else None,
            'resume_px4_us':g['first_reception_px4_us'],'resume_t_s':(g['first_reception_px4_us']-t0)/1e6,
            'recovery_start_t_s':(rc['start_px4_us']-t0)/1e6 if rc.get('start_px4_us') is not None else None,
            'recovery_end_t_s':(rc['end_px4_us']-t0)/1e6 if rc.get('end_px4_us') is not None else None,'recovery_end_reason':rc.get('end'),
            'catch_up_s':rc.get('catch_up_s'),'recovery_duration_s':rc.get('duration_s'),'acceleration_limited_s':(rc.get('replay') or {}).get('limited_s'),
            'observed_jump_along_axis_m':rc.get('observed_jump_along_axis_m'),'observed_velocity_jump_along_axis_m_s':rc.get('observed_velocity_jump_along_axis_m_s'),
            'setpoint_jump_along_axis_m':(g.get('resume') or {}).get('jump_along_axis_m'),
            'lag_window_s':lg.get('window_s'),'max_along_track_lag_m':lg.get('max_along_track_lag_m'),'max_along_track_lag_at_s':lg.get('max_along_track_lag_at_s'),
            'max_horizontal_distance_m':lg.get('max_horizontal_distance_m'),'along_track_lag_at_window_end_m':lg.get('along_track_lag_at_window_end_m'),
            'horizontal_distance_at_window_end_m':lg.get('horizontal_distance_at_window_end_m'),'lag_window_truncated':lg.get('truncated'),'lag_window_cut_by_next_interruption':lg.get('cut_by_next_interruption')})
    og=(m7.get('p6') or {}).get('open_gap') or {}
    if og.get('open_gap') and og.get('capture'):
        ev.append(('capture',og['capture']['px4_us'],{'gap':og.get('gap_index'),'mode':og['capture']['mode'],'captured_speed_m_s':og['capture']['captured_speed_m_s'],'open_gap':True}))
    if og.get('failure_reason') or m7.get('aborted'):
        fa=next((e for e in events if e['event']=='failure'),None);ev.append(('runner_abort',int(og.get('raptor_last_active_px4_us') or s[-1]),{'reason':fa['reason'] if fa else None,'time':'last RAPTOR-active status row' if og.get('raptor_last_active_px4_us') else 'last RAPTOR inference'}))
    se=next((e for e in events if e['event']=='p5_stream_ended'),None)
    if se:ev.append(('stream_end',int(se['end_bound_px4_us']),{}))
    keys=['ep_u','ev_u','ep_w','ev_w','a_u','a_w','ep_u_clip','ev_u_clip','ep_w_clip','ev_w_clip','tilt_deg','alt_loss_m','v_u','tgt_p_u','tgt_v_u','traj_p_u','p_u']
    def state(i):return None if i<0 or i>=len(s) else {'t_s':float(data['t_s'][i]),'target_mode':str(R['mode'][i]),**{k:float(data[k][i]) for k in keys}}
    evs=[]
    for name,t,info in sorted(ev,key=lambda x:x[1]):
        i=int(np.searchsorted(s,t,side='left'))
        if name=='resume':
            j=np.flatnonzero((s>=t)&np.isin(R['mode'],['external','recovery']));i=int(j[0]) if len(j) else i
        evs.append({'event':name,'px4_us':int(t),'t_s':(t-t0)/1e6,**info,'state_before':state(i-1),'state_at_or_after':state(i)})
    def csv(idx):
        b=io.StringIO();b.write(','.join(COLS)+'\n')
        for i in idx:b.write(','.join(f'{data[c][i]:.7g}' if isinstance(data[c][i],(float,np.floating)) else str(data[c][i]) for c in COLS)+'\n')
        return gzip.compress(b.getvalue().encode(),compresslevel=9,mtime=0)
    idx=np.arange(len(s));blob=csv(idx);thinned=False
    if len(blob)>MAX_BYTES:
        near=np.zeros(len(s),bool)
        for e in evs:near|=np.abs(s-e['px4_us'])<=EVENT_KEEP_S*1e6
        bucket=(s//int(1e6/THIN_HZ));first=np.r_[True,bucket[1:]!=bucket[:-1]]
        idx=np.flatnonzero(near|first);blob=csv(idx);thinned=True
    d=out/run.name;d.mkdir(parents=True,exist_ok=True);(d/'trace.csv.gz').write_bytes(blob)
    wh=m7.get('whole') or {};tt=(m7.get('p6') or {}).get('tilt') or {};fo=m7.get('flight_outcome') or {}
    summary={'run':run.name,'run_directory':os.path.relpath(run,ROOT),'batch':batch,'stage':stage,'kind':meta['experiment_type'],'condition':cfg.get('p1_condition'),
        'treatment':cfg.get('p2_treatment'),'treatment_parameters':cfg.get('p2_treatment_parameters'),'sim_seed':(cfg.get('p4_independence') or {}).get('sim_seed'),
        'planned_speed_m_s':cfg.get('p1_speed_m_s'),'motion_axis_ned':list(axis),'line_centre_ned_m':list(origin),'condition_spec':cfg.get('p5_condition_spec'),
        'profile':cfg.get('p2_profile'),'direction':m7.get('direction'),
        'batch_status':{k:row.get(k) for k in ['status','accepted','flight_failure','infrastructure_ok']} if row else None,
        'outcome':fo.get('outcome'),'flight_failure_reasons':fo.get('reasons'),'aborted':m7.get('aborted'),'abort_reason':m7.get('failure_reason'),
        'max_tilt_deg':tt.get('max_tilt_deg'),'max_tilt_at_s':tt.get('max_tilt_at_s'),'first_at_or_above_45_s':tt.get('first_at_or_above_45_s'),
        'max_altitude_loss_m':wh.get('max_altitude_loss_m'),'max_angular_rate_rad_s':wh.get('max_angular_rate_rad_s'),'motor_saturation_any_s':wh.get('motor_saturation_any_s'),
        'max_horizontal_radius_m':wh.get('max_horizontal_radius_m'),
        'recovery_rate_m_s2':rec.get('rate_m_s2'),'recovery':rlist,
        'time_origin':{'px4_us':t0,'definition':t0_def},'events':evs,'reconstruction':R['resid'],
        'trace':{'file':'trace.csv.gz','rows':int(len(idx)),'rows_full_rate':int(len(s)),'downsampled':thinned,'bytes':len(blob),
                 'downsampling_rule':f'{THIN_HZ} Hz outside +-{EVENT_KEEP_S} s of the events' if thinned else None,'columns':COLS},
        'sources':{'unclipped_error':'vehicle_local_position sample used by RAPTOR (research_timing.local_position_sample) minus the target RAPTOR observed (external setpoint read / research_target capture or T1 row / research_recovery STEP row)',
                   'clipped_error':'research_memory.policy_input [0:2] position, [12:14] velocity (target-yaw FLU frame)','acceleration':'vehicle_local_position ax, ay, az of the same sample (EKF2)',
                   'trajectory':'latest logged trajectory_setpoint row advanced by its velocity','tilt':'vehicle_attitude','metrics':'p7-metrics.json'}}
    (d/'summary.json').write_text(json.dumps(summary,indent=1,ensure_ascii=False,allow_nan=False,default=float)+'\n')
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batches',nargs='+',type=Path);p.add_argument('--out',type=Path,default=ROOT/'export');a=p.parse_args()
    out=a.out.resolve();out.mkdir(exist_ok=True);mf=out/'manifest.json'
    man=json.loads(mf.read_text()) if mf.exists() else {'runs':{}}
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain','--','tools/p7_export.py'],cwd=ROOT,text=True).strip())
    bad=[]
    for b in a.batches:
        b=b.resolve();res=json.loads((b/'results.json').read_text());cand=json.loads((b/'candidate.json').read_text());stage='p7-'+b.name.split('-')[-1]
        for row in res['runs']:
            run=ROOT/row['directory']
            if row.get('status')=='NOT_RUN' or not (run/'flight.ulg').exists() or not (run/'p7-metrics.json').exists():continue
            sm=export_run(row['directory'],out,str(b.relative_to(ROOT)),row,stage);r=sm['reconstruction']
            if r['components_over_1e-4']:bad.append((run.name,r['components_over_1e-4']))
            man['runs'][run.name]={'export':f'{run.name}/','batch':str(b.relative_to(ROOT)),'stage':stage,'run_directory':row['directory'],'kind':row['kind'],'condition':row['condition'],
                'treatment':row['treatment'],'sim_seed':row.get('sim_seed'),'outcome':sm['outcome'],'accepted':row.get('accepted'),'flight_failure':row.get('flight_failure'),
                'candidate_project_commit':cand['project_head'],'trace_bytes':sm['trace']['bytes'],'reconstruction_components_over_1e-4':r['components_over_1e-4'],'export_script':'tools/p7_export.py'}
            print(run.name,sm['outcome'],sm['trace']['bytes'],r['position_max_abs'],r['velocity_max_abs'],r['components_over_1e-4'],r['rows_on_virtual_target'],flush=True)
    man['p7']={'updated_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'export_script':'tools/p7_export.py','export_script_sha256':sha(ROOT/'tools/p7_export.py'),
        'export_script_commit':head,'export_script_modified_since_commit':dirty,'description':(__doc__ or '').strip(),
        'runs':sorted(k for k,v in man['runs'].items() if v.get('export_script')=='tools/p7_export.py')}
    man['total_bytes']=sum(f.stat().st_size for f in out.rglob('*') if f.is_file() and f.name!='manifest.json')
    man['runs']=dict(sorted(man['runs'].items()));mf.write_text(json.dumps(man,indent=1,ensure_ascii=False)+'\n')
    print('runs',len(man['runs']),'p7 runs',len(man['p7']['runs']),'bytes',man['total_bytes'],'reconstruction mismatches',bad)
    return 0
if __name__=='__main__':raise SystemExit(main())
