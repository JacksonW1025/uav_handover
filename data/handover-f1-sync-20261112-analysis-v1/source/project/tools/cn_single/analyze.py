"""Native-clock, one-case descriptive evidence. Never substitutes old flights."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from analyze import clean


def longest_continuous(timestamps, good, max_gap_us=20000):
    """Observed duration only; missing intervals never manufacture continuity."""
    best=0.;start=None;previous=None
    for t,ok in zip(timestamps,good):
        if not ok or (previous is not None and t-previous>max_gap_us):start=None
        if ok:
            if start is None:start=t
            best=max(best,(int(t)-int(start))/1e6)
        previous=t
    return best


def classify_task(metrics):
    if not metrics or not metrics.get('observations_finite',False):return 'UNKNOWN'
    values=[metrics.get('max_tilt_deg'),metrics.get('max_altitude_loss_m')]
    if any(x is None or not np.isfinite(x) for x in values):return 'UNKNOWN'
    return 'FAILURE' if values[0]>45 or values[1]>1 else 'SUCCESS'


def analyze(folder):
    meta=json.loads((folder/'metadata.json').read_text())
    u=ULog(str(folder/'flight.ulg'))
    d={x.name:x.data for x in u.data_list if x.multi_id==0}
    events=[json.loads(s) for s in (folder/'events.jsonl').read_text().splitlines()]
    required=['vehicle_status','vehicle_control_mode','vehicle_command','vehicle_command_ack','vehicle_local_position','vehicle_attitude','actuator_motors','vehicle_angular_velocity','research_actuator','research_output','research_p11','research_timing','mission_result','health_report','failsafe_flags','register_ext_component_reply','arming_check_reply']
    out={'scope':'single descriptive case, no seed generalization or causal ablation',
         'missing_topics':[n for n in required if n not in d], 'ulog_dropouts':len(u.dropouts),
         'ulog_sha256':meta.get('ulog_sha256'),'raptor_mode_id':meta['raptor_mode_id'],
         'flight_execution':json.loads((folder/'validation.json').read_text()),
         'subject_requests':[e for e in events if e['event']=='handover_requested' and e.get('subject') is True],
         'non_subject_recovery_requests':[e for e in events if e['event']=='handover_requested' and e.get('subject') is False],
         'native_timeline':{}, 'flight_metrics':None}
    timeline=out['native_timeline']
    status=d.get('vehicle_status')
    entry=None;exit_time=None
    if status is not None:
        changes=np.r_[0,np.flatnonzero(np.diff(status['nav_state'])!=0)+1]
        out['navigation_transitions']=[{'timestamp_us':int(status['timestamp'][i]),'nav_state':int(status['nav_state'][i]),'arming_state':int(status['arming_state'][i])} for i in changes]
        out['actual_neural_entries']=sum(int(status['nav_state'][i])==meta['raptor_mode_id'] for i in changes)
        idx=np.flatnonzero(status['nav_state']==meta['raptor_mode_id'])
        if len(idx):
            first=int(idx[0]);entry=int(status.get('nav_state_timestamp',status['timestamp'])[first])
            timeline['native_nav_entry_us']=entry
            endidx=np.flatnonzero((status['timestamp']>entry)&(status['nav_state']!=meta['raptor_mode_id']))
            exit_time=int(status['timestamp'][endidx[0]]) if len(endidx) else int(u.last_timestamp)
    for topic in ['register_ext_component_reply','arming_check_reply','health_report','failsafe_flags','mission_result']:
        if topic not in d:continue
        t=d[topic];indices=list(range(min(len(t['timestamp']),10)))
        if entry is not None:
            k=int(np.searchsorted(t['timestamp'],entry));indices=sorted(set(indices+list(range(max(0,k-2),min(k+3,len(t['timestamp']))))))
        out[topic+'_selected_rows']=[{key:clean(val[i]) for key,val in t.items()} for i in indices]
    if entry is not None:
        owner=d.get('research_actuator',{});oi=np.flatnonzero((owner.get('owner',np.array([]))==1)&(owner.get('timestamp',np.array([]))>=entry))
        own=owner.get('owner',np.array([]));out['actual_neural_owner_entries']=int(np.count_nonzero((own[1:]==1)&(own[:-1]!=1)))+(int(own[0]==1) if len(own) else 0)
        if len(oi):
            i=oi[0];timeline['first_neural_publication_us']=int(owner['actuator_timestamp'][i]);timeline['first_neural_owner_evidence_us']=int(owner['timestamp'][i])
            timeline['mode_to_neural_publication_us']=timeline['first_neural_publication_us']-entry
        p11=d.get('research_p11',{});ai=np.flatnonzero(p11.get('active',np.array([],dtype=bool)))
        if len(ai):
            timeline['first_active_observation_us']=int(p11['timestamp'][ai[0]])
            valid=ai[p11['external_valid'][ai].astype(bool)]
            if len(valid):timeline['first_active_valid_external_read_us']=int(p11['timestamp'][valid[0]])
            out['active_stale_samples']=int(np.count_nonzero(p11['stale'][ai]));out['active_invalid_setpoint_total_last']=int(p11['invalid_total'][ai[-1]])
            out['activation_observation']={k:clean(v[ai[0]]) for k,v in p11.items()}
        l=d.get('vehicle_local_position');a=d.get('vehicle_attitude');m=d.get('actuator_motors')
        if l is not None and a is not None and m is not None:
            mask=(l['timestamp']>=entry)&(l['timestamp']<=exit_time)
            am=(a['timestamp']>=entry)&(a['timestamp']<=exit_time)
            mm=(m['timestamp']>=entry)&(m['timestamp']<=exit_time)
            if mask.any() and am.any() and mm.any():
                tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]'][am]**2+a['q[2]'][am]**2),-1,1)))
                altitude=-l['z'][mask];mot=np.array([m[f'control[{i}]'][mm] for i in range(4)]).T
                metrics={'duration_s':(exit_time-entry)/1e6,'max_tilt_deg':float(tilt.max()),'entry_altitude_m':float(altitude[0]),'min_altitude_m':float(altitude.min()),'max_altitude_m':float(altitude.max()),'max_altitude_loss_m':float(max(0,altitude[0]-altitude.min())),
                         'max_radius_m':float(np.hypot(l['x'][mask],l['y'][mask]).max()),'max_horizontal_speed_m_s':float(np.hypot(l['vx'][mask],l['vy'][mask]).max()),
                         'motor_all_finite':bool(np.isfinite(mot).all()),'motor_min':float(np.nanmin(mot)),'motor_max':float(np.nanmax(mot)),
                         'max_motor_sample_step':float(np.nanmax(np.abs(np.diff(mot,axis=0)))) if len(mot)>1 else None}
                metrics['observations_finite']=bool(np.isfinite(tilt).all() and np.isfinite(altitude).all() and np.isfinite(np.array([l[k][mask] for k in ['x','y','z','vx','vy','vz']])).all() and np.isfinite(mot).all())
                metrics['task_failure']=metrics['max_tilt_deg']>45 or metrics['max_altitude_loss_m']>1
                metrics['motor_continuous_saturation_s']=longest_continuous(m['timestamp'][mm],np.any((mot>=.999)|(mot<=.001),axis=1))
                ang=d.get('vehicle_angular_velocity',{});at=ang.get('timestamp',np.array([]));aq=(at>=entry)&(at<=exit_time)
                metrics['max_angular_rate_component_rad_s']=float(np.max(np.abs(np.array([ang[f'xyz[{i}]'][aq] for i in range(3)])))) if aq.any() else None
                out['flight_metrics']=metrics
        if 'research_p11' in d:
            z=d['research_p11'];q=z['active'].astype(bool)&z['native_step'].astype(bool)
            if q.any():
                err=np.array([z[f'position[{i}]'][q]-z[f'network_target_position[{i}]'][q] for i in range(3)]).T
                n=np.linalg.norm(err,axis=1)
                out['active_target_position_error_m']={'rmse':float(np.sqrt(np.mean(n*n))),'max':float(n.max()),'samples':int(len(n)),'reference':'exact controller-consumed P11 target, not send-side trajectory'}
    # Frozen primary and task criterion are separate. Unknown never becomes PASS.
    f=out['flight_metrics'];reasons=[];unknown=[]
    if f:
        if not f['observations_finite']:unknown.append('nonfinite observations; invalid evidence')
        if f['max_tilt_deg']>=45 or f['max_radius_m']>=10 or f['max_altitude_m']>=8 or f['min_altitude_m']<=.2:reasons.append('safety envelope or ground')
        if f['max_angular_rate_component_rad_s'] is None:unknown.append('angular rate')
        elif f['max_angular_rate_component_rad_s']>=8:reasons.append('angular rate')
        if f['motor_continuous_saturation_s']>=.5:reasons.append('motor saturation >=0.5s')
    else:unknown.append('flight metrics')
    p11=d.get('research_p11',{})
    if entry is not None and p11:
        start=timeline.get('first_neural_publication_us',entry)
        mask=p11['active'].astype(bool)&p11['native_step'].astype(bool)&(p11['timestamp']>=start)&(p11['timestamp']<=start+10_000_000)
        pos=np.array([p11[f'position[{i}]'][mask]-p11[f'network_target_position[{i}]'][mask] for i in range(3)]).T
        vel=np.array([p11[f'velocity[{i}]'][mask]-p11[f'network_target_velocity[{i}]'][mask] for i in range(3)]).T
        omg=np.array([p11[f'angular_velocity[{i}]'][mask] for i in range(3)]).T
        good=(np.linalg.norm(pos,axis=1)<=.2)&(np.linalg.norm(vel,axis=1)<=.1)&(np.linalg.norm(omg,axis=1)<=.1)
        dwell=longest_continuous(p11['timestamp'][mask],good)
        out['frozen_joint_recovery']={'observed_dwell_s':dwell,'required_dwell_s':2.,'horizon_s':10.,'max_continuity_gap_s':.02,'reference':'P11 exact active controller target'}
        if dwell<2.:
            if exit_time<start+10_000_000:unknown.append('recovery observation shorter than10s')
            else:reasons.append('no 2s joint recovery within10s')
    else:unknown.append('recovery samples')
    if any(e['event']=='failure' and 'safety:' in str(e.get('reason','')) for e in events):reasons.append('runner safety abort')
    out['frozen_primary_outcome']={'status':'UNKNOWN' if f and not f['observations_finite'] else ('FAILURE' if reasons else ('UNKNOWN' if unknown else 'SUCCESS')),'reasons':reasons,'unknown':unknown,
        'interpretation':'original frozen thresholds; moving reference can intentionally fail the stationary-style joint recovery test'}
    out['task_outcome']={'status':classify_task(f),'criteria':'tilt>45deg OR altitude loss>1m during subject neural interval'}
    out['completion']={'exactly_one_subject_C_to_N':len(out['subject_requests'])==1,
        'reference_completed':any(e['event']=='cn_reference_finished' for e in events),
        'landing_requested':any(e['event']=='landing_requested' for e in events),
        'disarmed_observed':any(e['event']=='ready' and e.get('condition')=='disarmed' for e in events),
        'failures':[e for e in events if e['event']=='failure'],
        'px4_exit_codes':[e['exit_code'] for e in events if e['event']=='process_stopped' and e['name']=='px4']}
    out['status']='MEASURED' if entry is not None and f is not None and f['observations_finite'] else 'INCOMPLETE'
    return clean(out)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    with a.output.open('x') as f:json.dump(analyze(a.run),f,indent=2,allow_nan=False);f.write('\n')
