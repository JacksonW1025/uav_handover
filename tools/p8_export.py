#!/usr/bin/env python3
"""Export P8 runs in the P6 format (tools/p6_export.py; same reconstruction from RAPTOR's own inputs, same validation
against research_memory.policy_input, same column definitions) plus the vertical channel and the jump events.

A (identification, kind p6_ident). Per run export/<run directory name>/:
  trace.csv.gz  one row per active RAPTOR inference, the P6 columns (see tools/p6_export.py) plus:
    alt_m                altitude above the local origin (-z of the vehicle_local_position sample RAPTOR used)
    v_z                  vertical velocity of that sample (vz, NED, down positive)
    action_mean          mean of the 4 network outputs of this RAPTOR cycle (research_timing.action, [-1, 1])
    motor_cmd_mean       mean of the 4 motor commands with this cycle's sample time (actuator_motors.control, [0, 1];
                         empty when the log has no actuator_motors row for the sample)
    p_u, p_w             vehicle position (the sample RAPTOR used) relative to the line centre (RAPTOR's hover capture)
    tgt_p_u, tgt_p_w     position of the target RAPTOR used, relative to the line centre
  summary.json  the P6 summary plus 'p8' (p8-metrics p8 block: jump timing and size, realized cruise, lag and catch-up,
                vertical maxima, task criterion) and the event 'jump' (first RAPTOR cycle on the jumped setpoint).
export/manifest.json: the P6 manifest, entries added per run (export_script recorded per entry); top-level 'p8' block.
"""
import argparse,datetime,gzip,io,json,math,os,subprocess
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_metrics import tilt_deg
import p6_export
from p6_export import uw,from_target_frame,time_origin,gap_windows,sha
ROOT=Path(__file__).resolve().parents[1]
TOPICS=p6_export.TOPICS+['research_timing','actuator_motors']
COLS=p6_export.COLS+['alt_m','v_z','action_mean','motor_cmd_mean','p_u','p_w','tgt_p_u','tgt_p_w']
MAX_BYTES,THIN_HZ,EVENT_KEEP_S=p6_export.MAX_BYTES,p6_export.THIN_HZ,p6_export.EVENT_KEEP_S

def vertical_columns(T,s):
    tm=T['research_timing'];c=np.asarray(tm['executor_called']).astype(bool);tts=np.asarray(tm['timestamp_sample'],np.int64)[c]
    act=np.stack([np.asarray(tm[f'action[{k}]'],float)[c] for k in range(4)],1).mean(1)
    i=np.minimum(np.searchsorted(tts,s),len(tts)-1);a=np.where(tts[i]==s,act[i],np.nan)
    am=T['actuator_motors'];ats=np.asarray(am['timestamp_sample'],np.int64);o=np.argsort(ats,kind='stable');ats=ats[o]
    mv=np.stack([np.asarray(am[f'control[{k}]'],float)[o] for k in range(4)],1).mean(1)
    j=np.minimum(np.searchsorted(ats,s),len(ats)-1);m=np.where(ats[j]==s,mv[j],np.nan)
    return a,m

def export_run(run,out,batch,row,stage):
    run=ROOT/run;cfg=json.loads((run/'config.json').read_text());meta=json.loads((run/'metadata.json').read_text())
    m6=json.loads((run/'p8-metrics.json').read_text());events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
    u=ULog(str(run/'flight.ulg'),TOPICS);T={d.name:d.data for d in u.data_list if d.multi_id==0}
    R=p6_export.reconstruct(T);s=R['s'];axis=np.asarray(cfg['p2_profile']['motion_axis_ned'],float)
    t0,t0_def=time_origin(m6);t0=int(t0) if t0 is not None else int(s[0])
    att=T['vehicle_attitude'];at=np.asarray(att['timestamp'],np.int64);ia=np.maximum(np.searchsorted(at,s,side='right')-1,0)
    tilt=tilt_deg(np.stack([np.asarray(att[f'q[{i}]'],float) for i in range(4)],1)[ia])
    lp=T['vehicle_local_position'];lts=np.asarray(lp['timestamp_sample'],np.int64);z0=float(np.asarray(lp['z'],float)[max(int(np.searchsorted(lts,t0,side='right'))-1,0)])
    ep_u,ep_w=uw(R['e'],axis);ev_u,ev_w=uw(R['ev'],axis);a_u,a_w=uw(R['acc'],axis);v_u,v_w=uw(R['vel'],axis)
    cp=from_target_frame(R['pin'][:,0],R['pin'][:,1],R['yaw']);cv=from_target_frame(R['pin'][:,12],R['pin'][:,13],R['yaw'])
    cpu,cpw=uw(cp,axis);cvu,cvw=uw(cv,axis)
    gaps=gap_windows(m6);ga=np.zeros(len(s),int)
    for a,b in gaps:ga[(s>=a)&(s<b)]=1
    origin=np.asarray(next(e for e in events if e['event']=='p1_reference_origin')['origin_ned_m'],float)
    p_u,p_w=uw(R['pos']-origin,axis);tg_u,tg_w=uw(R['pos']-R['e']-origin,axis);act,mot=vertical_columns(T,s)
    data={'t_s':(s-t0)/1e6,'px4_us':s,'ep_u':ep_u,'ep_w':ep_w,'ev_u':ev_u,'ev_w':ev_w,'ep_u_clip':cpu,'ep_w_clip':cpw,'ev_u_clip':cvu,'ev_w_clip':cvw,
          'ep_f_clip':R['pin'][:,0],'ep_l_clip':R['pin'][:,1],'ev_f_clip':R['pin'][:,12],'ev_l_clip':R['pin'][:,13],'ep_f':R['pf'][:,0],'ep_l':R['pf'][:,1],'ev_f':R['vf'][:,0],'ev_l':R['vf'][:,1],
          'ep_z':R['e'][:,2],'ev_z':R['ev'][:,2],'a_u':a_u,'a_w':a_w,'a_z':R['acc'][:,2],'v_u':v_u,'v_w':v_w,'tilt_deg':tilt,'alt_loss_m':R['pos'][:,2]-z0,
          'target_yaw_rad':R['yaw'],'target_mode':R['mode'],'gap_active':ga,'recon_ok':R['ok'].astype(int),
          'alt_m':-R['pos'][:,2],'v_z':R['vel'][:,2],'action_mean':act,'motor_cmd_mean':mot,'p_u':p_u,'p_w':p_w,'tgt_p_u':tg_u,'tgt_p_w':tg_w}
    p8=m6.get('p8') or {};ev=[('family_start',t0,{})]
    sw=next((e for e in events if e['event']=='p6_chase_switch'),None)
    if sw:ev.append(('chase_deceleration_start',t0+int(round(float(sw['family_time_s'])*1e6)),{'reason':sw['reason'],'runner_lag_m':sw['along_axis_lag_m']}))
    j=p8.get('jump') or {}
    if j.get('jump_setpoint_px4_us'):ev.append(('jump',int(j['jump_setpoint_px4_us']),{'jump_m':j.get('jump_m'),'planned_jump_m':j.get('planned_jump_m'),'raptor_first_read_px4_us':j.get('raptor_first_read_px4_us')}))
    if m6.get('aborted'):
        fa=next((e for e in events if e['event']=='failure'),None);ev.append(('runner_abort',int(s[-1]),{'reason':fa['reason'] if fa else None,'time':'last RAPTOR inference'}))
    se=next((e for e in events if e['event']=='p6_stream_ended'),None)
    if se:ev.append(('stream_end',int(se['end_bound_px4_us']),{}))
    keys=['ep_u','ev_u','ep_w','ev_w','a_u','a_w','ep_u_clip','ev_u_clip','ep_w_clip','ev_w_clip','tilt_deg','alt_loss_m','v_u','alt_m','v_z','action_mean']
    def state(i):return None if i<0 or i>=len(s) else {'t_s':float(data['t_s'][i]),'target_mode':str(R['mode'][i]),**{k:float(data[k][i]) for k in keys}}
    evs=[]
    for name,t,info in sorted(ev,key=lambda x:x[1]):
        i=int(np.searchsorted(s,t,side='left'))
        if name=='jump':
            # The jumped setpoint is logged on arrival and read by RAPTOR in a later cycle: first cycle whose target is it.
            k=np.flatnonzero((s>=t)&(np.abs(tg_u-tg_u[max(i-1,0)])>0.5*float(j['planned_jump_m'])));i=int(k[0]) if len(k) else i
        evs.append({'event':name,'px4_us':int(t),'t_s':(t-t0)/1e6,**info,'state_before':state(i-1),'state_at_or_after':state(i)})
    def csv(idx):
        b=io.StringIO();b.write(','.join(COLS)+'\n')
        for i in idx:
            b.write(','.join(('' if not np.isfinite(data[c][i]) else f'{data[c][i]:.7g}') if isinstance(data[c][i],(float,np.floating)) else str(data[c][i]) for c in COLS)+'\n')
        return gzip.compress(b.getvalue().encode(),compresslevel=9,mtime=0)
    idx=np.arange(len(s));blob=csv(idx);thinned=False
    if len(blob)>MAX_BYTES:
        near=np.zeros(len(s),bool)
        for e in evs:near|=np.abs(s-e['px4_us'])<=EVENT_KEEP_S*1e6
        bucket=(s//int(1e6/THIN_HZ));first=np.r_[True,bucket[1:]!=bucket[:-1]]
        idx=np.flatnonzero(near|first);blob=csv(idx);thinned=True
    d=out/run.name;d.mkdir(parents=True,exist_ok=True);(d/'trace.csv.gz').write_bytes(blob)
    m=m6.get('whole') or {};tt=m6.get('tilt') or {};io_=m6.get('ident_outcome') or {}
    i=int(np.searchsorted(s,t0));direc={'planned_axis_ned':list(axis),'speed_along_axis_at_origin_m_s':float(v_u[i]) if i<len(s) else None}
    tail=np.flatnonzero((s>=t0)&(np.abs(v_u)>0.3))
    if len(tail):vv=R['vel'][tail];direc['realized_deg_mean_moving']=float(math.degrees(math.atan2(vv[:,1].mean(),vv[:,0].mean())))
    summary={'run':run.name,'run_directory':os.path.relpath(run,ROOT),'batch':batch,'stage':stage,'kind':meta['experiment_type'],'condition':cfg.get('p1_condition'),
        'treatment':cfg.get('p2_treatment'),'treatment_parameters':cfg.get('p2_treatment_parameters'),'sim_seed':(cfg.get('p4_independence') or {}).get('sim_seed'),
        'planned_speed_m_s':cfg.get('p1_speed_m_s'),'motion_axis_ned':list(axis),'condition_spec':cfg.get('p6_condition_spec'),
        'profile':cfg.get('p2_profile'),'direction':direc,'line_centre_ned_m':list(origin),
        'batch_status':{k:row.get(k) for k in ['status','accepted','flight_failure','infrastructure_ok']} if row else None,
        'outcome':io_.get('class'),'ident_exceeded_45':io_.get('ident_exceeded_45'),'task_criterion':p8.get('task_criterion'),
        'aborted':m6.get('aborted'),'abort_reason':m6.get('failure_reason'),
        'max_tilt_deg':tt.get('max_tilt_deg'),'max_tilt_at_s':tt.get('max_tilt_at_s'),'first_at_or_above_45_s':tt.get('first_at_or_above_45_s'),
        'max_altitude_loss_m':(p8.get('vertical') or {}).get('max_altitude_loss_m'),'max_altitude_loss_at_s':(p8.get('vertical') or {}).get('max_altitude_loss_at_s'),
        'max_angular_rate_rad_s':m.get('max_angular_rate_rad_s'),'motor_saturation_any_s':m.get('motor_saturation_any_s'),
        'p8':p8,'time_origin':{'px4_us':t0,'definition':t0_def},'events':evs,'reconstruction':R['resid'],
        'trace':{'file':'trace.csv.gz','rows':int(len(idx)),'rows_full_rate':int(len(s)),'downsampled':thinned,'bytes':len(blob),
                 'downsampling_rule':f'{THIN_HZ} Hz outside +-{EVENT_KEEP_S} s of the events' if thinned else None,'columns':COLS,
                 'rows_without_motor_row':int(np.isnan(mot).sum()),'rows_without_action':int(np.isnan(act).sum())},
        'sources':{'unclipped_error':'vehicle_local_position sample used by RAPTOR (research_timing.local_position_sample) minus RAPTOR target (external setpoint read / research_target row)',
                   'clipped_error':'research_memory.policy_input [0:2] position, [12:14] velocity (target-yaw FLU frame)','acceleration':'vehicle_local_position ax, ay, az of the same sample (EKF2)',
                   'altitude':'-z of the same vehicle_local_position sample (EKF2, local origin at the spawn point)','vertical_velocity':'vz of the same sample (NED, down positive)',
                   'thrust':'action_mean: research_timing.action[0..3] of the cycle (network output in [-1, 1]); motor_cmd_mean: actuator_motors.control[0..3] with the same timestamp_sample ([0, 1], the motor order differs from the action order, the mean does not)',
                   'tilt':'vehicle_attitude','metrics':'p8-metrics.json'}}
    (d/'summary.json').write_text(json.dumps(summary,indent=1,ensure_ascii=False,allow_nan=False,default=float)+'\n')
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batches',nargs='+',type=Path);p.add_argument('--out',type=Path,default=ROOT/'export');a=p.parse_args()
    out=a.out.resolve();out.mkdir(exist_ok=True);mf=out/'manifest.json'
    man=json.loads(mf.read_text()) if mf.exists() else {'runs':{}}
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain','--','tools/p8_export.py'],cwd=ROOT,text=True).strip())
    bad=[];added=[]
    for b in a.batches:
        b=b.resolve();res=json.loads((b/'results.json').read_text());cand=json.loads((b/'candidate.json').read_text());stage='p8-'+b.name.split('-')[-1]
        for row in res['runs']:
            run=ROOT/row['directory']
            if row.get('status')=='NOT_RUN' or not (run/'flight.ulg').exists() or not (run/'p8-metrics.json').exists():continue
            sm=export_run(row['directory'],out,str(b.relative_to(ROOT)),row,stage);r=sm['reconstruction']
            if r['components_over_1e-4']:bad.append((run.name,r['components_over_1e-4']))
            man['runs'][run.name]={'export':f'{run.name}/','batch':str(b.relative_to(ROOT)),'stage':stage,'run_directory':row['directory'],'kind':row['kind'],'condition':row['condition'],
                'treatment':row['treatment'],'sim_seed':row.get('sim_seed'),'outcome':sm['outcome'],'accepted':row.get('accepted'),'flight_failure':row.get('flight_failure'),
                'task_criterion_exceeded':(sm.get('task_criterion') or {}).get('exceeded'),
                'candidate_project_commit':cand['project_head'],'trace_bytes':sm['trace']['bytes'],'reconstruction_components_over_1e-4':r['components_over_1e-4'],'export_script':'tools/p8_export.py'}
            added.append(run.name)
            print(run.name,sm['outcome'],sm['trace']['bytes'],r['position_max_abs'],r['velocity_max_abs'],r['components_over_1e-4'],flush=True)
    blk=man.get('p8') or {}
    blk.update({'updated_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'export_script':'tools/p8_export.py','export_script_sha256':sha(ROOT/'tools/p8_export.py'),
        'export_script_commit':head,'export_script_modified_since_commit':dirty,'description':(__doc__ or '').strip(),
        'runs':sorted(set(blk.get('runs',[]))|set(added))})
    man['p8']=blk;man['total_bytes']=sum(f.stat().st_size for f in out.rglob('*') if f.is_file() and f.name!='manifest.json')
    man['runs']=dict(sorted(man['runs'].items()));mf.write_text(json.dumps(man,indent=1,ensure_ascii=False)+'\n')
    print('runs',len(man['runs']),'p8 runs',len(blk['runs']),'bytes',man['total_bytes'],'reconstruction mismatches',bad)
    return 0
if __name__=='__main__':raise SystemExit(main())
