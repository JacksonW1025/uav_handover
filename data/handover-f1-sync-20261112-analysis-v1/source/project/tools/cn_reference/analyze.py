"""Read-only A/B/C evidence. CLI creates a new analysis directory, never a flight."""
import argparse,csv,itertools,json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from analyze import clean
from output_chain import read_trace
from cn_single.analyze import analyze as single_analyze

def load(p,default=None):return json.loads(p.read_text()) if p.exists() else default

def lines(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()] if p.exists() else []

def row(z,i):return clean({k:v[i] for k,v in z.items()})

def vector(r,k,n=3):
    a=[r.get(f'{k}[{i}]') for i in range(n)] if r else []
    return a if len(a)==n and all(v is not None and np.isfinite(v) for v in a) else None

def snapshot(d,t):
    if t is None:return None
    out={'anchor_native_us':int(t),'selection':'last sample at or before anchor, age explicit'}
    for k in ['vehicle_local_position','vehicle_attitude','vehicle_angular_velocity','trajectory_setpoint','vehicle_local_position_setpoint','research_p11','research_memory','actuator_motors','rate_ctrl_status','vehicle_control_mode','setpoint_config','position_controller_status','raptor_status','research_target']:
        z=d.get(k,{});ts=z.get('timestamp',[]);i=int(np.searchsorted(ts,t,side='right'))-1
        out[k]={'age_us':int(t-int(ts[i])),'row':row(z,i)} if i>=0 else None
    return out

def host_bracket(p,host,field='run_wall_ns'):
    if host is None or field not in p:return None
    wall=np.asarray(p[field]);good=np.flatnonzero(wall>0);lo=good[wall[good]<=host];hi=good[wall[good]>=host]
    return {'host_monotonic_ns':int(host),'p11_host_field':field,'native_lower_us':int(p['timestamp'][lo[-1]]) if len(lo) else None,'native_upper_us':int(p['timestamp'][hi[0]]) if len(hi) else None,'method':'observed P11 bracket; no DDS UTC or interpolation'}

def window(d,start,seconds):
    if start is None:return None
    end=start+int(seconds*1e6);out={'start_native_us':int(start),'end_native_us':int(end),'requested_duration_s':seconds};data={};complete=True;finite=True
    for k in ['vehicle_local_position','vehicle_attitude','vehicle_angular_velocity','actuator_motors']:
        z=d.get(k,{});t=np.asarray(z.get('timestamp',[]),dtype=np.int64);ix=np.flatnonzero((t>=start)&(t<=end));data[k]=(z,ix);g=np.diff(t[ix])
        ok=bool(len(ix)>1 and t[ix[0]]-start<=20000 and end-t[ix[-1]]<=20000 and np.all(g<=20000));complete &= ok
        out[k+'_coverage']={'samples':len(ix),'complete':ok,'max_gap_us':int(g.max()) if len(g) else None,'median_period_us':float(np.median(g)) if len(g) else None}
    l,li=data['vehicle_local_position'];a,ai=data['vehicle_attitude'];m,mi=data['actuator_motors'];w,wi=data['vehicle_angular_velocity']
    if len(li):
        alt=-l['z'][li];i=int(np.searchsorted(l['timestamp'],start,side='right'))-1;baseline=float(-l['z'][i]) if i>=0 and start-int(l['timestamp'][i])<=20000 else None
        out.update(entry_altitude_m=baseline,min_altitude_m=float(alt.min()),max_altitude_loss_m=float(max(0,baseline-alt.min())) if baseline is not None else None);finite &= bool(np.isfinite(alt).all())
    if len(ai):
        tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]'][ai]**2+a['q[2]'][ai]**2),-1,1)));out['max_tilt_deg']=float(tilt.max());finite &= bool(np.isfinite(tilt).all())
    if len(mi):
        v=np.array([m[f'control[{j}]'][mi] for j in range(4)]).T;prev=mi[0]-1;extended=np.vstack([np.array([m[f'control[{j}]'][prev] for j in range(4)]),v]) if prev>=0 else v;steps=np.diff(extended,axis=0)
        out.update(motor_min=float(v.min()),motor_max=float(v.max()),max_motor_sample_step=float(np.abs(steps).max()) if len(steps) else None,motor_rail_samples=int(np.any((v<=.001)|(v>=.999),axis=1).sum()));finite &= bool(np.isfinite(v).all())
    if len(wi):
        v=np.array([w[f'xyz[{j}]'][wi] for j in range(3)]);out['max_angular_rate_component_rad_s']=float(np.abs(v).max());finite &= bool(np.isfinite(v).all())
    out['observations_finite']=bool(finite and all(len(ix)>0 for _,ix in data.values()));out['complete']=bool(complete and out['observations_finite'] and out.get('entry_altitude_m') is not None)
    fail=any(out.get(k) is not None and out[k]>limit for k,limit in [('max_tilt_deg',45),('max_altitude_loss_m',1)])
    out['local_task_envelope']='FAILURE' if fail else ('SUCCESS' if out['complete'] else 'UNKNOWN')
    return clean(out)

def input_clipping(p,ix):
    if not len(ix):return None
    yaw=p['target_yaw'][ix];c=np.cos(yaw);s=np.sin(yaw)
    def error(name):
        e=np.array([p[f'{name}[{j}]'][ix]-p[f'network_target_{name}[{j}]'][ix] for j in range(3)]).T
        return np.column_stack([c*e[:,0]+s*e[:,1],s*e[:,0]-c*e[:,1],-e[:,2]])
    ep=error('position');ev=error('velocity');pin=np.array([p[f'policy_input[{j}]'][ix] for j in range(22)]).T
    finite=bool(np.isfinite(ep).all() and np.isfinite(ev).all() and np.isfinite(pin).all())
    residual=np.concatenate([(np.clip(ep,-.5,.5)-pin[:,:3]).ravel(),(np.clip(ev,-1,1)-pin[:,12:15]).ravel()])
    return {'finite':finite,'position_limit_m':.5,'velocity_limit_m_s':1.,'position_clipped_by_component':np.count_nonzero(np.abs(ep)>.5,axis=0).tolist() if finite else None,'velocity_clipped_by_component':np.count_nonzero(np.abs(ev)>1,axis=0).tolist() if finite else None,'position_clipped_samples':int(np.any(np.abs(ep)>.5,axis=1).sum()) if finite else None,'velocity_clipped_samples':int(np.any(np.abs(ev)>1,axis=1).sum()) if finite else None,'max_abs_raw_position_error_target_flu':np.abs(ep).max(0).tolist(),'max_abs_raw_velocity_error_target_flu':np.abs(ev).max(0).tolist(),'reconstruction_max_abs_residual':float(np.max(np.abs(residual))),'reference':'exact P11 state minus consumed target, target-yaw FLU, mc_raptor observe() .5m/1m_s per-axis limits'}

def match_first_send(p,indices,send,atol=1e-5):
    """First observed read matching the runner's first payload, after send began.

    external_valid alone also includes inherited classic trajectory samples. A
    missing sender match is missing evidence, never an assumed reference receipt.
    """
    if not send or send.get('before_ns') is None or 'read_wall_ns' not in p:return None
    try:
        expected=np.asarray(send['position']+send['velocity'],dtype=np.float64)
        if expected.shape!=(6,) or not np.isfinite(expected).all():return None
        actual=np.column_stack([p[f'external_{k}[{j}]'] for k in ['position','velocity'] for j in range(3)])
    except (KeyError,TypeError,ValueError):return None
    indices=np.asarray(indices,dtype=int)
    if not len(indices):return None
    valid=np.asarray(p.get('active',[]),bool)[indices]&np.asarray(p.get('external_valid',[]),bool)[indices]
    valid &= np.asarray(p['read_wall_ns'])[indices]>=send['before_ns']
    valid &= np.all(np.isfinite(actual[indices]),axis=1)&np.all(np.isclose(actual[indices],expected,rtol=0,atol=atol),axis=1)
    found=indices[valid]
    return int(found[0]) if len(found) else None

def owner_boundary_step(d,pub):
    """Exact published controls, preferring owner-tagged research_actuator.

    Do not substitute the next actuator_motors row when the logger omitted the
    boundary. Per-physics motor consumption remains a separate trace measure.
    """
    motors=d.get('actuator_motors',{});mt=np.asarray(motors.get('timestamp',[]));mi=np.flatnonzero(mt==pub)
    out={'owner_publication_us':int(pub),'actuator_motors_exact_publication_logged':bool(len(mi)), 'exact_publication_timestamp_match':False,'finite':False}
    own=d.get('research_actuator',{});ot=np.asarray(own.get('actuator_timestamp',[]));ix=np.flatnonzero((ot==pub)&(np.asarray(own.get('owner',[]))==1))
    source=None;before=None;after=None;times=None;z=None
    if len(ix):
        after=int(ix[0]);previous=np.flatnonzero(ot<pub)
        if len(previous):before=int(previous[-1]);source='research_actuator.control[0:4]';times=ot;z=own
    if source is None and len(mi):
        after=int(mi[0]);previous=np.flatnonzero(mt<pub)
        if len(previous):before=int(previous[-1]);source='actuator_motors.control[0:4]';times=mt;z=motors
    if source is None:
        out['limitation']='No exact publication and preceding controls available; later logged command is not substituted.'
        return out
    vb=vector(row(z,before),'control',4);va=vector(row(z,after),'control',4)
    out.update(source=source,previous_motor_timestamp_us=int(times[before]),first_motor_timestamp_us=int(times[after]),previous_sample_age_us=int(pub-int(times[before])),exact_publication_timestamp_match=int(times[after])==pub,before=vb,after=va)
    if source.startswith('research_actuator'):out.update(previous_owner=int(own['owner'][before]),first_owner=int(own['owner'][after]))
    if vb is not None and va is not None:
        delta=np.asarray(va)-vb;out.update(signed_step_by_motor=delta.tolist(),max_abs_step=float(np.abs(delta).max()),finite=True)
    if len(mi) and va is not None:
        logged=vector(row(motors,int(mi[0])),'control',4)
        out['cross_topic_exact_controls_match']=logged is not None and np.array_equal(np.asarray(logged,np.float32),np.asarray(va,np.float32))
    else:out['cross_topic_exact_controls_match']=None
    out['limitation']=None if len(mi) else 'actuator_motors ULog omitted the boundary sample. Exact controls are retained in owner-tagged research_actuator; motor application is independently measured from raw Gazebo traces.'
    return out

def analyze(folder,arm):
    folder=Path(folder);arm=arm.upper()
    if arm not in ['A','B','C']:raise ValueError('arm must be A/B/C')
    out={'arm':arm,'source_run':str(folder),'status':'NOT_RUN','errors':[],'native_timeline':{},'host_timing':{},'snapshots':{},'windows':{},'first_motor_application':{},'gap':[],'evidence_completion':{'complete':False,'missing':['flight.ulg']}}
    if not (folder/'flight.ulg').exists():return out
    out['status']='INCOMPLETE'
    try:
        u=ULog(str(folder/'flight.ulg'));d={x.name:x.data for x in u.data_list if x.multi_id==0};events=lines(folder/'events.jsonl');sends=lines(folder/'cn-setpoints.jsonl');meta=load(folder/'metadata.json',{})
    except Exception as exc:out['errors'].append(f'input: {exc}');return out
    p=d.get('research_p11',{});pt=np.asarray(p.get('timestamp',[]));tl=out['native_timeline'];ht=out['host_timing'];out['ulog_dropouts']=len(u.dropouts);out['ulog_sha256']=meta.get('ulog_sha256');out['execution']=load(folder/'validation.json');out['arm_result']=load(folder.parent/'result.json')
    trigger=next((e for e in events if e.get('event')=='cn_trigger_state'),None);out['trigger_event']=trigger
    requests=[e for e in events if e.get('event')=='handover_requested' and e.get('subject') is True and e.get('to_controller')=='N'];out['subject_requests']=requests
    control=next((e for e in events if e.get('event')=='cn_control_trigger'),None);req=requests[0] if requests else control;bound=(req or {}).get('end_bound_px4_us');tl['request_native_lower_bound_us']=bound
    ht['trigger']=host_bracket(p,(trigger or {}).get('monotonic_ns'));ht['request']=host_bracket(p,(req or {}).get('monotonic_ns'))
    trig=(ht['trigger'] or {}).get('native_lower_us');trig=trig if trig is not None else bound
    if arm=='A' and bound is not None:trig=bound
    tl['trigger_snapshot_anchor_us']=trig;tl['trigger_anchor_note']='A native control bound; B/C observed host-trigger P11 lower bracket (fallback request lower bound), not exact trigger time'
    s=d.get('vehicle_status',{});st=np.asarray(s.get('timestamp',[]));mode=meta.get('raptor_mode_id');entry=None
    if arm!='A' and mode is not None:
        ix=np.flatnonzero((np.asarray(s.get('nav_state',[]))==mode)&(st>=(bound or 0)))
        if len(ix):entry=int(s.get('nav_state_timestamp',st)[ix[0]])
    tl['native_nav_entry_us']=entry;anchor=trig if arm=='A' else entry;out['snapshots']={'trigger':snapshot(d,trig),'nav_entry':snapshot(d,entry)}
    cmd=d.get('vehicle_command',{});ct=np.asarray(cmd.get('timestamp',[]));ix=np.flatnonzero((ct>=(bound or 0))&(np.asarray(cmd.get('command',[]))==100001)&(np.asarray(cmd.get('param1',[]))==mode)) if arm!='A' and bound is not None else []
    if len(ix):
        i=int(ix[0]);out['native_mode_command']=row(cmd,i);tl['mode_command_us']=int(ct[i]);ack=d.get('vehicle_command_ack',{});at=np.asarray(ack.get('timestamp',[]));ax=np.flatnonzero((at>=ct[i])&(np.asarray(ack.get('command',[]))==100001))
        if len(ax):out['native_mode_ack']=row(ack,int(ax[0]));tl['mode_ack_us']=int(at[ax[0]])
    out['mode_events']=[e for e in events if e.get('event') in ['mode_confirmed','command_ack'] and e.get('monotonic_ns',0)>=(req or {}).get('monotonic_ns',0)]
    active=np.asarray(p.get('active',[]),bool);ai=np.flatnonzero(active&(pt>=(entry or bound or 0))) if arm!='A' else []
    if len(ai):
        i=int(ai[0]);tl['first_active_observation_us']=int(pt[i]);out['first_active_observation']=row(p,i);valid=ai[np.asarray(p['external_valid'][ai],bool)]
        if len(valid):
            vi=int(valid[0]);tl['first_active_valid_any_source_read_us']=int(pt[vi]);out['first_valid_any_source_observation']=row(p,vi);ht['first_valid_any_source_read_wall_ns']=int(p['read_wall_ns'][vi])
        vi=match_first_send(p,ai,sends[0] if sends else None)
        out['external_reference_receipt_identification']={'method':'active and external_valid, read_wall_ns >= first send before_ns, all six position/velocity components match with rtol=0 atol=1e-5','matched':vi is not None,'limit':'Payload and same-host clock identification; no sequence ID is carried through the interface. First any-source valid read is reported separately.'}
        if vi is not None:
            tl['first_active_valid_external_read_us']=int(pt[vi]);tl['first_runner_reference_read_us']=int(pt[vi]);out['first_valid_external_observation']=row(p,vi);ht['first_valid_read_wall_ns']=int(p['read_wall_ns'][vi])
        own=d.get('research_actuator',{});ot=np.asarray(own.get('timestamp',[]));ix=np.flatnonzero((np.asarray(own.get('owner',[]))==1)&(ot>=(entry or 0)))
        if len(ix):tl['first_neural_publication_us']=int(own['actuator_timestamp'][ix[0]])
    pub=tl.get('first_neural_publication_us')
    if pub is not None:out['owner_boundary_motor_step']=owner_boundary_step(d,pub)
    if pub is not None:
        own=d['research_actuator'];samples=np.unique(own['actuator_timestamp'][own['owner']==1])
        for path in sorted((folder/'gz-motor').glob('motor-*.bin')):
            try:
                motor,z,partial=read_trace(path);ix=np.flatnonzero((z['sim_us']>=pub)&np.isin(z['applied_sample_us'],samples))
                if len(ix):
                    i=int(ix[0]);native=int(z['sim_us'][i]);read=tl.get('first_active_valid_external_read_us');out['first_motor_application'][str(motor)]={'sim_us':native,'sample_us':int(z['applied_sample_us'][i]),'first_publication_applied':int(z['applied_sample_us'][i])==pub,'partial_tail_bytes':partial,'to_first_valid_read_ms':(read-native)/1000 if read is not None else None}
            except Exception as exc:out['errors'].append(f'{path.name}: {exc}')
    if sends:
        out['first_external_send']=sends[0];ht['first_send']=host_bracket(p,sends[0].get('before_ns'));ht['first_send_end']=host_bracket(p,sends[0].get('after_ns'));read=out.get('first_valid_external_observation')
        if read:
            ht['first_send_end_to_read_ms']=(ht['first_valid_read_wall_ns']-sends[0]['after_ns'])/1e6
            out['first_send_read_position_velocity_float32_match']=all(vector(read,'external_'+k) is not None and np.array_equal(np.asarray(sends[0][k],np.float32),np.asarray(vector(read,'external_'+k),np.float32)) for k in ['position','velocity'])
    ht['clock_note']='CLOCK_MONOTONIC mapping via P11 only; host delay is not DDS transport latency.'
    for n in [1,2]:out['windows'][f'first_{n}s']=window(d,anchor,n)
    if anchor is not None:
        ix=np.flatnonzero(active&(pt>=anchor)&(pt<=anchor+2000000))
        if len(ix):
            inp=np.array([p[f'policy_input[{j}]'][ix] for j in range(22)]).T;act=np.array([p[f'executor_action[{j}]'][ix] for j in range(4)]).T
            out['input_clipping']=input_clipping(p,ix)
            out['clipping']={'samples':len(ix),'policy_input_min_by_component':inp.min(0).tolist(),'policy_input_max_by_component':inp.max(0).tolist(),'executor_action_min_by_motor':act.min(0).tolist(),'executor_action_max_by_motor':act.max(0).tolist(),'executor_action_at_rail_samples':int(np.any(np.abs(act)>=.999999,axis=1).sum()),'note':'Observed rail occupancy, not proof of clipping; unclipped network action is not logged.'}
    if p and entry is not None:
        stale=np.asarray(p['stale'],bool);edges=np.flatnonzero(stale[1:]!=stale[:-1])+1
        for i in edges:
            if stale[i] and active[i] and pt[i]>entry+1000000:
                ends=edges[(edges>i)&(~stale[edges])&active[edges]];j=int(ends[0]) if len(ends) else None
                out['gap'].append({'stale_capture_us':int(pt[i]),'last_valid_read_us':int(p['last_valid_read_us'][i]),'resume_us':int(pt[j]) if j is not None else None,'consumed_interval_ms':(int(pt[j])-int(p['last_valid_read_us'][i]))/1000 if j is not None else None,'stale_duration_ms':(int(pt[j])-int(pt[i]))/1000 if j is not None else None})
    out['snapshots']['first_valid_any_source_read']=snapshot(d,tl.get('first_active_valid_any_source_read_us'))
    out['snapshots']['first_valid_read']=snapshot(d,tl.get('first_active_valid_external_read_us'))
    out['snapshots']['after_entry_100ms']=snapshot(d,entry+100000 if entry is not None else None)
    out['gap_send_events']=[e for e in events if e.get('event') in ['cn_gap_started','cn_gap_ended']];out['failures']=[e for e in events if e.get('event')=='failure']
    if arm!='A':
        try:
            out['full_neural_analysis']=single_analyze(folder)
            nt=out['full_neural_analysis'].get('native_timeline',{})
            nt['first_active_valid_any_source_read_us']=nt.pop('first_active_valid_external_read_us',None)
            nt['first_active_valid_external_read_us']=tl.get('first_active_valid_external_read_us')
            nt['external_reference_receipt_note']='Sender-matched receipt; original first any-source external_valid row is retained separately. Frozen/task metrics unchanged.'
        except Exception as exc:out['errors'].append(f'cn_single analyzer: {exc}')
    else:out['control_subject_window']=window(d,trig,2.2);out['control_note']='Classic Mission local control, no neural frozen recovery outcome; output-chain status is not an A gate.'
    missing=[]
    if len(u.dropouts):missing.append('zero ULog dropouts')
    starts=[e for e in events if e.get('event')=='process_started'];stops=[e for e in events if e.get('event')=='process_stopped']
    out['process_completion']={'started':starts,'stopped':stops}
    for e in starts:
        matched=[v for v in stops if v.get('pid')==e.get('pid') and v.get('name')==e.get('name')]
        if not matched:missing.append('process stopped: '+e.get('name','unknown'))
        elif matched[-1].get('exit_code') not in ([0] if e.get('name') in ['px4','gazebo'] else [0,-2]):missing.append('acceptable process exit: '+e.get('name','unknown'))
    for name in ['px4','gazebo']:
        if not any(e.get('name')==name for e in starts):missing.append(name+' process lifecycle')
    if not any(e.get('event')=='ready' and e.get('condition')=='landing' for e in events):missing.append('landed observed')
    if trigger is None:missing.append('trigger event')
    if anchor is None:missing.append('native subject anchor')
    if state(out['snapshots'].get('trigger')) is None:missing.append('finite trigger state snapshot')
    for label,w in out['windows'].items():
        if not w or not w['complete']:missing.append(label+' complete finite coverage')
    if arm!='A':
        for k in ['mode_command_us','mode_ack_us','native_nav_entry_us','first_active_observation_us','first_neural_publication_us','first_active_valid_external_read_us']:
            if tl.get(k) is None:missing.append(k)
        if len(requests)!=1:missing.append('exactly one subject C to N')
        if state(out['snapshots'].get('nav_entry')) is None:missing.append('finite nav-entry state snapshot')
        for label in ['first_send','first_send_end']:
            bracket=ht.get(label) or {}
            if bracket.get('native_lower_us') is None or bracket.get('native_upper_us') is None:missing.append(label+' native mapping bracket')
        first=out.get('first_active_observation',{})
        for name,n in [('position',3),('velocity',3),('attitude',4),('angular_velocity',3),('network_target_position',3),('network_target_velocity',3),('gru_before',16),('gru_after',16),('previous_action_before',4),('executor_action',4)]:
            if vector(first,name,n) is None:missing.append('finite activation '+name)
        if not sends:missing.append('external send')
        elif sends[0].get('profile_s')!=0:missing.append('first profile_s exactly zero')
        if set(out['first_motor_application'])!={'0','1','2','3'}:missing.append('four motor applications')
        if 'full_neural_analysis' not in out:missing.append('frozen/task analysis')
        if (out.get('native_mode_ack') or {}).get('result')!=0:missing.append('accepted native mode ACK')
        if any(v['partial_tail_bytes'] for v in out['first_motor_application'].values()):missing.append('complete motor trace tails')
        if out.get('input_clipping',{}).get('finite') is not True:missing.append('finite P11 state and policy inputs')
        if out.get('full_neural_analysis',{}).get('missing_topics',['unknown']):missing.append('required neural topics')
        if out.get('first_send_read_position_velocity_float32_match') is not True:missing.append('first send/read exact position velocity signature')
        if ht.get('first_send_end_to_read_ms') is None or ht['first_send_end_to_read_ms']<0:missing.append('nonnegative send to read host delay')
        if entry is None or tl.get('first_active_valid_external_read_us',-1)<entry or tl.get('first_active_valid_external_read_us',-1)<tl.get('first_active_observation_us',0):missing.append('valid read after native entry and active')
        send_upper=(ht.get('first_send') or {}).get('native_upper_us')
        if send_upper is not None and entry is not None and send_upper<entry:missing.append('no first send before native nav entry')
        step=out.get('owner_boundary_motor_step',{})
        if not step.get('exact_publication_timestamp_match') or not step.get('finite') or step.get('previous_sample_age_us',float('inf'))>20000:missing.append('exact finite owner boundary motor step')
        if step.get('cross_topic_exact_controls_match') is False:missing.append('owner boundary topic controls disagree')
        if not any(e.get('event')=='cn_reference_finished' for e in events):missing.append('reference finished')
    if arm=='A':
        if not out['control_subject_window'] or not out['control_subject_window']['complete']:missing.append('complete 2.2s classic window')
        if not any(e.get('event')=='cn_classic_control_finished' for e in events):missing.append('classic control finished')
        mask=(st>=trig)&(st<=trig+2200000) if trig is not None else np.zeros(len(st),bool)
        out['classic_mission_nav_only']=bool(mask.any() and np.all(s['nav_state'][mask]==3))
        if not out['classic_mission_nav_only']:missing.append('classic Mission navigation throughout subject window')
        owner=d.get('research_actuator',{})
        out['classic_no_neural_or_external']=bool(not requests and not np.any(active) and not np.any(np.asarray(owner.get('owner',[]))==1) and not sends)
        if not out['classic_no_neural_or_external']:missing.append('A contains neural request/activity/ownership or external stream')
        if not p or not owner:missing.append('A neural inactivity evidence topics')
    if not any(e.get('event')=='ready' and e.get('condition')=='disarmed' for e in events):missing.append('disarmed observed')
    if out['errors']:missing.append('analysis errors')
    out['evidence_completion']={'complete':not missing,'missing':missing,'note':'Evidence gate only; negative outcomes remain reportable.'};out['status']='MEASURED' if not missing else 'INCOMPLETE'
    return clean(out)

def state(s):
    if not s:return None
    def r(k):return (s.get(k) or {}).get('row')
    l=r('vehicle_local_position');a=r('vehicle_attitude');w=r('vehicle_angular_velocity')
    if not l or not a or not w:return None
    v={'position':[l.get(k) for k in ['x','y','z']],'velocity':[l.get(k) for k in ['vx','vy','vz']],'quaternion':vector(a,'q',4),'angular_rate':vector(w,'xyz')}
    if any(x is None or any(t is None or not np.isfinite(t) for t in x) for x in v.values()):return None
    v['max_age_us']=max(s[k]['age_us'] for k in ['vehicle_local_position','vehicle_attitude','vehicle_angular_velocity']);return v

def compare(x,y):
    thresholds={'position_m':.2,'velocity_m_s':.2,'attitude_deg':5.,'angular_rate_rad_s':.3};out={'thresholds':thresholds,'status':'UNKNOWN','interpretation':'Descriptive balance check, not causal equivalence'}
    if x is None or y is None:return out
    for k,src in [('position_m','position'),('velocity_m_s','velocity'),('angular_rate_rad_s','angular_rate')]:out[k]=float(np.linalg.norm(np.array(x[src])-y[src]))
    q1=np.array(x['quaternion']);q2=np.array(y['quaternion']);norm=np.linalg.norm(q1)*np.linalg.norm(q2)
    if norm<=0:return out
    out['attitude_deg']=float(np.degrees(2*np.arccos(np.clip(abs(np.dot(q1,q2))/norm,0,1))));out['max_sample_age_us']=max(x['max_age_us'],y['max_age_us']);out['status']='UNKNOWN' if out['max_sample_age_us']>20000 else ('MATCH' if all(out[k]<=v for k,v in thresholds.items()) else 'MISMATCH');return out

def arm_mapping(entries=None):
    mapping={a:a for a in 'ABC'}
    items=entries.items() if isinstance(entries,dict) else [x.split('=',1) for x in (entries or [])]
    seen=set()
    for a,name in items:
        if a not in mapping or a in seen or not name or Path(name).name!=name or name in ['.','..']:
            raise ValueError('Use unique logical arms A/B/C and single-directory attempt names, e.g. A=A2 B=B2 C=C2')
        seen.add(a);mapping[a]=name
    return mapping

def combined(root,output,selection=None):
    mapping=arm_mapping(selection)
    root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=False);arms={a:analyze(root/mapping[a]/'flight',a) for a in 'ABC'}
    for a,r in arms.items():r['selected_attempt']=mapping[a]
    summary={'selected_attempts':mapping,'selection_note':'Explicit attempt selection; unselected attempts remain in the all-attempt audit. Different candidates are not causal matched ablations.','scope':'Single seed20261109 descriptive SITL comparison; old raw evidence unchanged','arms':arms,'trigger_pairwise':{},'BC_nav_entry_match':compare(state(arms['B']['snapshots'].get('nav_entry')),state(arms['C']['snapshots'].get('nav_entry')))}
    summary['candidate_pairwise_equal']={}
    for a,b in itertools.combinations('ABC',2):
        summary['trigger_pairwise'][a+b]=compare(state(arms[a]['snapshots'].get('trigger')),state(arms[b]['snapshots'].get('trigger')))
        x=load(root/mapping[a]/'candidate-before.json');y=load(root/mapping[b]/'candidate-before.json')
        summary['candidate_pairwise_equal'][a+b]=(x==y if x is not None and y is not None else None)
    (output/'summary.json').write_text(json.dumps(clean(summary),indent=2,allow_nan=False)+'\n')
    fields=['arm','selected_attempt','status','evidence_complete','frozen_outcome','task_outcome','first_motor_to_reference_ms']+[f'first_{n}s_{k}' for n in [1,2] for k in ['max_tilt_deg','min_altitude_m','max_altitude_loss_m']]+['missing']
    with (output/'three-arm.csv').open('x') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for arm,r in arms.items():
            full=r.get('full_neural_analysis') or {};delays=[v['to_first_valid_read_ms'] for v in r['first_motor_application'].values() if v['to_first_valid_read_ms'] is not None]
            v={'arm':arm,'selected_attempt':mapping[arm],'status':r['status'],'evidence_complete':r['evidence_completion']['complete'],'frozen_outcome':full.get('frozen_primary_outcome',{}).get('status','NOT_APPLICABLE' if arm=='A' else 'UNKNOWN'),'task_outcome':full.get('task_outcome',{}).get('status','NOT_APPLICABLE' if arm=='A' else 'UNKNOWN'),'first_motor_to_reference_ms':max(delays) if delays else None,'missing':'; '.join(r['evidence_completion']['missing'])}
            for n in [1,2]:
                for k in ['max_tilt_deg','min_altitude_m','max_altitude_loss_m']:v[f'first_{n}s_{k}']=(r['windows'].get(f'first_{n}s') or {}).get(k)
            writer.writerow(v)
    overlay(arms,output/'BC-local-overlay.png');return summary

def overlay(arms,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(4,1,figsize=(11,12),sharex=True,constrained_layout=True);plotted=[]
    for arm in 'BC':
        r=arms[arm];entry=r['native_timeline'].get('native_nav_entry_us')
        if entry is None:continue
        try:
            u=ULog(str(Path(r['source_run'])/'flight.ulg'));d={x.name:x.data for x in u.data_list if x.multi_id==0};p=d['research_p11'];t=(p['timestamp'].astype(np.int64)-entry)/1e6;q=(t>=-.2)&(t<=2)
            l=d['vehicle_local_position'];lt=(l['timestamp'].astype(np.int64)-entry)/1e6;lm=(lt>=-.2)&(lt<=2);a=d['vehicle_attitude'];at=(a['timestamp'].astype(np.int64)-entry)/1e6;am=(at>=-.2)&(at<=2);tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]']**2+a['q[2]']**2),-1,1)))
            axes[0].plot(at[am],tilt[am],label=arm+' full-rate attitude');axes[1].plot(lt[lm],-l['z'][lm],label=arm+' altitude');axes[1].plot(t[q],-p['network_target_position[2]'][q],'--',label=arm+' target altitude');axes[2].plot(t[q],p['velocity[0]'][q],label=arm+' Vn');axes[2].plot(t[q],p['network_target_velocity[0]'][q],'--',label=arm+' target Vn')
            m=d['actuator_motors'];mt=(m['timestamp'].astype(np.int64)-entry)/1e6;mm=(mt>=-.2)&(mt<=2)
            for j in range(4):axes[3].plot(mt[mm],m[f'control[{j}]'][mm],label=f'{arm} motor{j}',alpha=.65)
            plotted.append(arm)
        except (KeyError,ValueError,OSError):continue
    missing=[a for a in 'BC' if a not in plotted]
    for ax,label in zip(axes,['Tilt (deg)','Altitude (m)','North velocity (m/s)','Normalized motor command']):
        ax.set_ylabel(label);ax.grid(alpha=.25)
        if ax.lines:ax.legend(fontsize=8,ncol=2)
    axes[-1].set_xlabel('Native time from each RAPTOR nav entry (s)');fig.suptitle('B/C local takeover overlay'+(' | unavailable: '+', '.join(missing) if missing else ''))
    if missing:axes[0].text(.5,.5,'Missing arms: '+', '.join(missing)+' (NOT_RUN or incomplete evidence)',transform=axes[0].transAxes,ha='center')
    fig.savefig(path,dpi=160);plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--arms',nargs='+',metavar='A=A2');a=p.parse_args();combined(a.root,a.output,a.arms)
