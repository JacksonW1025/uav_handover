#!/usr/bin/env python3
"""Additional P9 fixed-window measurements. Never changes frozen p5/p7 outputs."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_metrics import tilt_deg
from p5_metrics import receptions, setpoint_rows
from p9_predict import reference
from p9_model import write, sha


def catch_up(t,d,dv,start,window=10.,dwell=.5):
    w=(t>=start)&(t<=start+window+1e-8)
    tt=t[w];ok=(d[w]<=.2)&(dv[w]<=.1);begin=None;previous=None
    for stamp,good in zip(tt,ok):
        if not good or (previous is not None and stamp-previous>.02):begin=None
        if good and begin is None:begin=stamp
        if good and stamp-begin>=dwell-1e-8:return float(begin-start)
        previous=stamp
    return None


def analyze(run):
    run=Path(run);cfg=json.loads((run/'config.json').read_text())
    base=json.loads((run/'p7-metrics.json').read_text())
    events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
    origin=np.array(next(e['origin_ned_m'] for e in events if e['event']=='p1_reference_origin'))
    p=cfg['p2_profile'];speed=cfg['p1_speed_m_s'];axis=np.array(p['motion_axis_ned'])
    topics=['raptor_status','trajectory_setpoint','vehicle_local_position','vehicle_attitude','research_recovery']
    u=ULog(str(run/'flight.ulg'),topics);T={d.name:d.data for d in u.data_list if d.multi_id==0}
    spt,spp,spv=setpoint_rows(T['trajectory_setpoint'],receptions(T['raptor_status'],T['trajectory_setpoint']))
    first=(base.get('gaps') or [{}])[0].get('last_reception_px4_us')
    if first is None:first=((base.get('p6') or {}).get('open_gap') or {}).get('last_arrival_px4_us')
    if first is None:raise ValueError('no observed first interruption; fixed-window origin cannot be established')
    # Recover the BASE clock from moving setpoints preceding the first actual gap.
    # This keeps single-event controls on the exact same absolute trajectory.
    along=(spp-origin)@axis
    base_point=p['start_offset_m']+.5*speed*p['accel_s']+speed*1.
    at_speed=np.abs(spv@axis-speed)<1e-4
    use=at_speed&(spt<=first)&(spt>=first-500000)
    if use.sum()<3:raise ValueError('insufficient cruise setpoints for fixed-window native-clock origin')
    origins=spt[use]-(along[use]-base_point)/speed*1e6
    t0=float(np.median(origins));spread=float(np.max(origins)-np.min(origins))
    lp=T['vehicle_local_position'];ts=(np.asarray(lp['timestamp_sample'],float)-t0)/1e6
    pos=np.column_stack([lp[k] for k in ['x','y','z']]);vel=np.column_stack([lp[k] for k in ['vx','vy','vz']])
    w=(ts>=0)&(ts<=16.)
    if not w.any():raise ValueError('no fixed-window state samples')
    arr_t=ts[w];observed_end=float(arr_t[-1]);complete=observed_end>=15.98
    z0=float(np.interp(0.,ts,pos[:,2]));loss=pos[w,2]-z0
    att=T['vehicle_attitude'];ats=(np.asarray(att['timestamp'],float)-t0)/1e6
    at=(ats>=0)&(ats<=min(16.,observed_end));tilt=tilt_deg(np.column_stack([att[f'q[{i}]'] for i in range(4)]))
    peak=float(tilt[at].max()) if at.any() else None
    # The complete planned path is identical across all formal conditions.
    offset=float(p['pre_gap_s'])-1.;spec=cfg['p5_condition_spec'];last=spec['gaps']['windows_s'][-1][1]
    end_cruise=offset+last+float(p['post_gap_s'])
    sr=np.array([reference(float(t),speed,end_cruise) for t in arr_t])
    target=origin[:2]+axis[:2][None,:]*(base_point+sr[:,0,None])
    tv=axis[:2][None,:]*sr[:,1,None]
    delta=target-pos[w,:2];lag=delta@axis[:2];distance=np.linalg.norm(delta,axis=1);dv=np.linalg.norm(tv-vel[w,:2],axis=1)
    recovery=[]
    for g in base.get('gaps') or []:
        start=(g['first_reception_px4_us']-t0)/1e6
        a=(arr_t>=start)&(arr_t<=start+6.)
        if not a.any():continue
        cu=catch_up(arr_t,distance,dv,start)
        six_complete=bool(arr_t[a][-1]>=start+5.98)
        recovery.append({'index':g['index'],'resume_from_base_s':float(start),
                         'max_lag_6s_m':float(lag[a].max()),'lag_at_6s_m':float(lag[a][-1]) if six_complete else None,
                         'window_6s_complete':six_complete,'observed_6s_until_s':float(arr_t[a][-1]-start),
                         'vehicle_catch_up_10s_s':cu,'vehicle_catch_up_censored':cu is None,
                         'catch_up_observed_until_s':min(10.,max(0.,observed_end-start)),
                         'within_task_cost':bool(six_complete and lag[a].max()<=4.5 and abs(lag[a][-1])<=.5 and cu is not None)})
    # Strict task text uses >45; >=45 is retained separately for conservative/historical comparison.
    max_loss=max(0.,float(loss.max()));task_fail=bool(peak is not None and peak>45. or max_loss>1.)
    reasons=(['tilt_gt_45'] if peak is not None and peak>45. else [])+(['altitude_loss_gt_1'] if max_loss>1. else [])
    fo=base.get('flight_outcome') or {}
    final=next((r for r in recovery if r['index']==int(base['planned_gaps'])-1),None)
    cost='UNOBSERVED_FINAL_RESUME'
    if final is not None:
        violation=bool(lag.max()>4.5 or (final['window_6s_complete'] and abs(final['lag_at_6s_m'])>.5)
                       or (final['catch_up_observed_until_s']>=9.98 and final['vehicle_catch_up_10s_s'] is None))
        if violation:cost='FAILURE'
        elif complete and final['within_task_cost']:cost='SUCCESS'
        else:cost='CENSORED'
    result={'status':'MEASURED' if spread<=30000 and len(arr_t)>0 else 'INCOMPLETE',
            'run':str(run),'clock_origin_native_us':t0,'clock_origin_spread_us':spread,
            'clock_origin_method':'median native read time minus cruise setpoint geometric phase; no UTC clock',
            'window_planned_s':[0.,16.],'window_observed_s':[float(arr_t[0]),observed_end],'complete_window':complete,
            'aborted':bool(base.get('aborted')),'censored':not complete,
            'max_tilt_deg':peak,'max_altitude_loss_m':max_loss,
            'planned_interruptions':int(base['planned_gaps']),'closed_observed_interruptions':len(base.get('gaps') or []),
            'open_gap':bool(((base.get('p6') or {}).get('open_gap') or {}).get('open_gap')),
            'tilt_ge_45_failure':None if peak is None else peak>=45.,'altitude_failure':max_loss>1.,
            'tilt_full_window_outcome':'FAILURE' if peak is not None and peak>=45. else ('SUCCESS' if complete else 'CENSORED'),
            'task_failure':task_fail,'task_reasons':reasons,
            'task_outcome':'FAILURE' if task_fail else ('SUCCESS' if complete else 'CENSORED'),
            'frozen_primary_outcome':fo.get('outcome'),'frozen_primary_reasons':fo.get('reasons'),
            'frozen_primary_source':'p7-metrics.json (frozen p6/p5 analysis; original first-actual-gap window)',
            'max_lag_m':float(lag.max()),'max_horizontal_distance_m':float(distance.max()),
            'integrated_abs_lag_m_s':float(np.trapz(np.abs(lag),arr_t)), 'recoveries':recovery,
            'final_task_cost_outcome':cost,
            'source_hashes':{n:sha(run/n) for n in ['flight.ulg','config.json','p7-metrics.json','events.jsonl']}}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    out=analyze(a.run);write(a.run/'p9-metrics.json',out);print(json.dumps(out,indent=2));return out['status']!='MEASURED'


if __name__=='__main__':raise SystemExit(main())
