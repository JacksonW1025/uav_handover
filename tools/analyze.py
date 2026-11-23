#!/usr/bin/env python3
"""Analyze a new run's ULog, apply frozen thresholds, and plot evidence."""
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np
from pyulog import ULog

def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [clean(v) for v in value]
    if isinstance(value,(float,np.floating)):return float(value) if math.isfinite(value) else None
    if isinstance(value,np.integer):return int(value)
    return value

def write(path,value):path.write_text(json.dumps(clean(value),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def stats(a):
    a=np.asarray(a);a=a[np.isfinite(a)]
    return {'count':len(a),'mean':float(np.mean(a)),'p95':float(np.percentile(a,95)),'p99':float(np.percentile(a,99)),'max':float(np.max(a))} if len(a) else None

def analyze(folder):
    folder=folder.resolve();ulog=ULog(str(folder/'flight.ulg'))
    cfg=json.loads((folder/'config.json').read_text());meta=json.loads((folder/'metadata.json').read_text())
    validation=json.loads((folder/'validation.json').read_text())
    events=[json.loads(s) for s in (folder/'events.jsonl').read_text().splitlines()]
    samples=[json.loads(s) for s in (folder/'telemetry.jsonl').read_text().splitlines()]
    topics={d.name:d.data for d in ulog.data_list if d.multi_id==0}
    write(folder/'ulog-topics.json',{f'{d.name}/{d.multi_id}':{'instance':d.multi_id,'samples':len(d.data['timestamp']),'fields':list(d.data)} for d in ulog.data_list})
    required=['vehicle_local_position','vehicle_attitude','vehicle_angular_velocity','vehicle_status','vehicle_control_mode','trajectory_setpoint','rate_ctrl_status','actuator_motors']
    missing=[n for n in required if n not in topics or not len(topics[n]['timestamp'])]
    metrics={'ulog_start_us':ulog.start_timestamp,'ulog_end_us':ulog.last_timestamp,'dropouts':len(ulog.dropouts),'missing_topics':missing,'windows':{},'unavailable':{}}
    local=topics.get('vehicle_local_position',{})
    if not local:raise RuntimeError('no local position in ULog')
    t=local['timestamp'];pos=np.stack([local[k] for k in ['x','y','z']],axis=1)
    vel=np.stack([local[k] for k in ['vx','vy','vz']],axis=1)
    # DDS rewrites timestamps into Agent UTC. Match the exact serialized position
    # vector back to its uORB sample; interpolate in simulation time, not wall time.
    lookup={tuple(map(float,row)):int(stamp) for row,stamp in zip(pos,t)}
    anchors=[(s['monotonic_ns'],lookup[tuple(s['position'])]) for s in samples if tuple(s['position']) in lookup]
    if len(anchors)<2:raise RuntimeError('cannot align ROS telemetry with this ULog')
    metrics['time_alignment']={'method':'exact position-vector matches, monotonic->ULog interpolation',
                               'matched_samples':len(anchors),'telemetry_samples':len(samples),'sampling_uncertainty_s':0.1}
    def px4_time(monotonic):
        return float(np.interp(monotonic,[a[0] for a in anchors],[a[1] for a in anchors]))
    windows=[]
    for i,e in enumerate(events):
        if e['event']=='hover_started':
            finish=next((x for x in events[i+1:] if x['event']=='hover_ended'),None)
            if finish:
                a,b=px4_time(e['monotonic_ns']),px4_time(finish['monotonic_ns'])
                windows.append((e['label'],a,b))
    for index,(label,a,b) in enumerate(windows):
        mask=(t>=a)&(t<=b)
        reference=np.array([0,0,-cfg['altitude_m']])
        error=np.linalg.norm(pos[mask]-reference,axis=1)
        attitude=topics['vehicle_attitude'];at=attitude['timestamp'];am=(at>=a)&(at<=b)
        q=np.stack([attitude[f'q[{i}]'] for i in range(4)],axis=1)
        tilt=np.degrees(np.arccos(np.clip(1-2*(q[am,1]**2+q[am,2]**2),-1,1)))
        if 'vehicle_attitude_setpoint' in topics:
            sp=topics['vehicle_attitude_setpoint'];indices=np.clip(np.searchsorted(sp['timestamp'],at[am],side='right')-1,0,len(sp['timestamp'])-1)
            qref=np.stack([sp[f'q_d[{i}]'][indices] for i in range(4)],axis=1)
            attitude_error=2*np.degrees(np.arccos(np.clip(abs(np.sum(q[am]*qref,axis=1)),0,1)))
        else:attitude_error=np.array([])
        ang=topics['vehicle_angular_velocity'];angmask=(ang['timestamp']>=a)&(ang['timestamp']<=b)
        omega=np.stack([ang[f'xyz[{i}]'][angmask] for i in range(3)],axis=1)
        m={'start_us':a,'end_us':b,'duration_s':(b-a)/1e6,'position_error_m':stats(error),'velocity_error_m_s':stats(np.linalg.norm(vel[mask],axis=1)),'tilt_deg':stats(tilt),'attitude_error_deg':stats(attitude_error),'angular_rate_rad_s':stats(np.linalg.norm(omega,axis=1))}
        if 'vehicle_rates_setpoint' in topics:
            rates=topics['vehicle_rates_setpoint'];indices=np.clip(np.searchsorted(rates['timestamp'],ang['timestamp'][angmask],side='right')-1,0,len(rates['timestamp'])-1)
            omega_ref=np.stack([rates[k][indices] for k in ['roll','pitch','yaw']],axis=1)
            m['angular_rate_error_rad_s']=stats(np.linalg.norm(omega-omega_ref,axis=1))
        minimum=cfg['neural_s'] if label.startswith('neural') else cfg['hover_s']
        m['minimum_duration_s']=minimum
        m['status']='PASS' if (b-a)/1e6>=minimum and len(error)>0 and np.all(np.isfinite(error)) and np.max(error)<=cfg['hover_max_error_m'] and len(tilt)>0 and np.max(tilt)<=cfg['hover_max_tilt_deg'] else 'FAIL'
        metrics['windows'][label+'_'+str(index)]=m
    motors=topics['actuator_motors'];mt=motors['timestamp'];mv=np.stack([motors[f'control[{i}]'] for i in range(4)],axis=1)
    armed=topics['vehicle_status'];ast=armed['timestamp'];astate=armed['arming_state']
    armed_mask=astate[np.clip(np.searchsorted(ast,mt,side='right')-1,0,len(ast)-1)]==2
    finite=np.all(np.isfinite(mv[armed_mask]));within=np.all((mv[armed_mask]>=0)&(mv[armed_mask]<=1))
    metrics['armed_motor_values_valid']=bool(finite and within)
    metrics['actuator_step']=stats(np.max(np.abs(np.diff(mv,axis=0)),axis=1))
    metrics['handovers']=[]
    for i,e in enumerate(events):
        if e['event']=='handover_requested':
            confirmation=next((x for x in events[i+1:] if x['event']=='mode_confirmed'),None)
            if confirmation:
                metrics['handovers'].append({'from':e['from_controller'],'to':e['to_controller'],'request_to_mode_confirmation_ms':(confirmation['monotonic_ns']-e['monotonic_ns'])/1e6,'confirmation_px4_us':confirmation['px4_timestamp']})
    if meta['variant']=='raptor':
        for n in ['raptor_status','raptor_input','route_observability','research_timing','research_actuator','research_state_response']:
            if n not in topics:missing.append(n)
        r=topics.get('raptor_status',{})
        metrics['raptor_active_samples']=int(np.count_nonzero(r.get('active',[])))
        active=r.get('active',np.array([],dtype=bool)).astype(bool)
        if active.any():
            metrics['active_loop_interval_us']=stats(np.diff(r['timestamp'])[active[1:] & active[:-1]])
        timing=topics.get('research_timing',{})
        if timing:
            tm=timing['control_step'].astype(bool)
            metrics['inference_duration_us']=stats(timing['inference_duration_us'][tm])
            metrics['inference_nonfinite_count']=int(np.count_nonzero(~timing['output_finite'][tm].astype(bool)))
            metrics['executor_warning_count']=int(np.count_nonzero(~timing['executor_ok'][tm].astype(bool)))
            metrics['inference_timing_status']='PASS' if metrics['inference_duration_us'] and metrics['inference_duration_us']['p99']<=cfg['inference_p99_us'] and metrics['inference_nonfinite_count']==0 else 'FAIL'
            metrics['control_period_us']=stats(np.diff(timing['timestamp'][tm]))
            metrics['control_period_jitter_std_us']=float(np.std(np.diff(timing['timestamp'][tm])))
            metrics['observation_age_us']={}
            for sensor in ['vehicle_local_position','vehicle_attitude','vehicle_angular_velocity']:
                st=topics[sensor]['timestamp'];idx=np.searchsorted(st,timing['timestamp'],side='right')-1
                valid=idx>=0
                metrics['observation_age_us'][sensor]=stats(timing['timestamp'][valid]-st[idx[valid]])
        owner=topics.get('research_actuator',{})
        metrics['ownership_windows']={}
        if owner:
            changes=np.flatnonzero(np.diff(owner['owner'])!=0)+1
            expected_transitions=len(metrics['handovers'])
            metrics['ownership_transition_validation']={'expected':expected_transitions,'actual':len(changes),
                'status':'PASS' if len(changes)==expected_transitions else 'FAIL'}
            metrics['actuator_owner_transitions']=[{'px4_us':int(owner['actuator_timestamp'][i]),'from':int(owner['owner'][i-1]),'to':int(owner['owner'][i])} for i in changes]
            for transition in metrics['actuator_owner_transitions']:
                stamp=transition['px4_us'];idx=int(np.searchsorted(mt,stamp))
                if 0<idx<len(mt):transition['max_motor_step']=float(np.max(np.abs(mv[idx]-mv[idx-1])))
                desired=meta['raptor_mode_id'] if transition['to']==1 else 4
                candidates=np.flatnonzero(armed['nav_state']==desired)
                if len(candidates) and 'nav_state_timestamp' in armed:
                    nearest=candidates[np.argmin(np.abs(armed['nav_state_timestamp'][candidates].astype(np.int64)-stamp))]
                    transition['mode_change_us']=int(armed['nav_state_timestamp'][nearest])
                    transition['mode_to_actuator_owner_us']=int(stamp-transition['mode_change_us'])
                if 'settling_band_m' in cfg:
                    after=np.flatnonzero(t>=stamp)
                    error=np.linalg.norm(pos-np.array([0,0,-cfg['altitude_m']]),axis=1)
                    transition['settling_time_s']=None
                    for j in after:
                        end=int(np.searchsorted(t,t[j]+cfg['settling_dwell_s']*1e6))
                        if end<len(t) and end>j and np.all(error[j:end]<=cfg['settling_band_m']):
                            transition['settling_time_s']=float((t[j]-stamp)/1e6);break
            for index,(label,a,b) in enumerate(windows):
                mask=(owner['timestamp']>=a)&(owner['timestamp']<=b)
                expected=1 if label.startswith('neural') else 2
                actual=owner['owner'][mask]
                metrics['ownership_windows'][label+'_'+str(index)]={'expected_owner':expected,'samples':int(len(actual)),
                    'status':'PASS' if len(actual) and np.all(actual==expected) else 'FAIL'}
            # Each ownership event contains the exact actuator_motors publication timestamp.
            stamps=set(map(int,mt));matched=sum(int(v) in stamps for v in owner['actuator_timestamp'])
            metrics['ownership_log_matching']={'events':len(owner['timestamp']),'matched_actuator_samples':matched}
        state_events=[e['response'] for e in events if e['event']=='state_operation']
        response=topics.get('research_state_response',{})
        if response:
            logged={(int(req),int(target),int(op),int(res)) for req,target,op,res in zip(response['request_id'],response['target'],response['operation'],response['result'])}
            missing_states=[e['request_id'] for e in state_events if (e['request_id'],e['target'],e['operation'],e['result']) not in logged]
            metrics['state_log_validation']={'operations':len(state_events),'missing_requests':missing_states,'status':'PASS' if not missing_states else 'FAIL'}
            snapshots={};held={};state_errors=[]
            request=topics.get('research_state_request',{})
            request_index={int(v):i for i,v in enumerate(request.get('request_id',[]))}
            for e in state_events:
                target=e['target'];op=e['operation'];values=np.array(e['values']);ok=e['result']==0
                if e['applied_us']<e['request_id']:state_errors.append('application precedes request')
                if ok and op==2:snapshots[target]=values
                if ok and op==5 and (target not in snapshots or not np.allclose(values,snapshots[target],atol=1e-6,rtol=0)):state_errors.append('snapshot/restore mismatch')
                if ok and op==3 and not np.allclose(values[:20 if target==1 else 3],0,atol=1e-7,rtol=0):state_errors.append('reset did not clear memory')
                if ok and op==6:
                    idx=request_index.get(e['request_id'])
                    if idx is None:state_errors.append('inject request absent from ULog')
                    else:
                        requested=np.array([request[f'values[{i}]'][idx] for i in range(len(values))])
                        if not np.allclose(values,requested,atol=1e-6,rtol=0):state_errors.append('injected values differ from applied values')
                if target in held and (op in [1,7] or not ok) and not np.allclose(values,held[target],atol=1e-6,rtol=0):state_errors.append('held state changed')
                if ok and (op==4 or (e['holding'] and op in [3,5,6])):held[target]=values
                if ok and op==7:held.pop(target,None)
            metrics['state_values_validation']={'errors':state_errors,'status':'PASS' if not state_errors else 'FAIL'}
    if 'settling_band_m' not in cfg:metrics['unavailable']['settling_time']='this run did not predefine a settling band and dwell time'
    metrics['safety_failure_events']=sum(e['event']=='failure' for e in events)
    resources=folder/'resources.jsonl'
    if resources.exists():
        resource_data=[json.loads(s) for s in resources.read_text().splitlines()]
        metrics['host_resources']={'cpu_percent':stats([s['host_cpu_percent'] for s in resource_data]),
            'min_available_memory_bytes':min(s['host_memory_available_bytes'] for s in resource_data) if resource_data else None}
    import re
    gz_stats=folder/'logs/gz-stats.log'
    if gz_stats.exists():metrics['gazebo_real_time_factor']=stats([float(s) for s in re.findall(r'real_time_factor: ([0-9.e+-]+)',gz_stats.read_text())])
    tegra=folder/'logs/tegrastats.log'
    if tegra.exists():
        text=tegra.read_text();metrics['temperature_c']=stats([float(s) for s in re.findall(r'tj@([0-9.]+)C',text)])
        metrics['board_power_mw']=stats([float(s) for s in re.findall(r'\bVIN ([0-9.]+)mW',text)])
    # ULog time units are microseconds; plots use relative simulation seconds.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(6,1,figsize=(11,17),sharex=True)
    # PX4 timestamps are uint64: timestamps preceding the first ULog message
    # must become negative seconds, not wrap to 2**64 and destroy plot limits.
    def seconds(stamps):return (stamps.astype(np.float64)-ulog.start_timestamp)/1e6
    time_s=seconds(t)
    axes[0].plot(time_s,pos);axes[0].set_ylabel('NED position [m]');axes[0].legend(['N','E','D'])
    axes[1].plot(time_s,np.linalg.norm(pos-np.array([0,0,-cfg['altitude_m']]),axis=1));axes[1].set_ylabel('Position error [m]')
    att=topics['vehicle_attitude'];q=np.stack([att[f'q[{i}]'] for i in range(4)],axis=1)
    axes[2].plot(seconds(att['timestamp']),np.degrees(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1))));axes[2].set_ylabel('Tilt [deg]')
    ang=topics['vehicle_angular_velocity'];axes[3].plot(seconds(ang['timestamp']),np.stack([ang[f'xyz[{i}]'] for i in range(3)],axis=1));axes[3].set_ylabel('Angular rate [rad/s]')
    axes[4].plot(seconds(mt),mv);axes[4].set_ylabel('Motor commands [0,1]')
    axes[5].step(seconds(ast),armed['nav_state'],where='post');axes[5].set_ylabel('Navigation state');axes[5].set_xlabel('PX4 / simulation time [s]')
    axes[5].set_xlim(0,(ulog.last_timestamp-ulog.start_timestamp)/1e6)
    for e in events:
        if e['event']=='handover_requested' and samples:
            x=(px4_time(e['monotonic_ns'])-ulog.start_timestamp)/1e6
            for ax in axes:ax.axvline(x,color='red',alpha=.5,linestyle='--')
    for ax in axes:ax.grid(alpha=.3)
    fig.tight_layout();fig.savefig(folder/'overview.png',dpi=120);plt.close(fig)
    fig=plt.figure(figsize=(7,6));ax=fig.add_subplot(111,projection='3d')
    ax.plot(pos[:,0],pos[:,1],-pos[:,2]);ax.set_xlabel('North [m]');ax.set_ylabel('East [m]');ax.set_zlabel('Height [m]')
    fig.tight_layout();fig.savefig(folder/'trajectory.png',dpi=120);plt.close(fig)
    execution=validation.get('execution_status','PASS' if validation.get('reason') is None and validation.get('checks',{}).get('flight_sequence')=='PASS' else validation['status'])
    validation['execution_status']=execution
    passed=execution=='PASS' and not missing and metrics['armed_motor_values_valid'] and bool(windows) and all(m['status']=='PASS' for m in metrics['windows'].values())
    if meta['variant']=='raptor':
        passed=passed and metrics.get('raptor_active_samples',0)>0 and metrics.get('inference_timing_status')=='PASS' and bool(metrics['ownership_windows']) and all(v['status']=='PASS' for v in metrics['ownership_windows'].values()) and metrics.get('ownership_transition_validation',{}).get('status')=='PASS' and metrics.get('state_log_validation',{}).get('status')=='PASS' and metrics.get('state_values_validation',{}).get('status')=='PASS'
    metrics['status']='PASS' if passed else 'FAIL'
    write(folder/'metrics.json',metrics)
    validation['analysis_status']=metrics['status'];validation['status']=metrics['status'];validation['missing_topics']=missing
    write(folder/'validation.json',validation)
    print(json.dumps(clean(metrics),indent=2));return 0 if passed else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path)
    sys.exit(analyze(p.parse_args().run))
