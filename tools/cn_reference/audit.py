"""Post-stop all-attempt raw audit. New outputs only, no simulation or run mutation."""
import argparse,gzip,hashlib,json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from analyze import clean
from cn_reference.analyze import lines,load,row,snapshot,window,analyze


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return {'bytes':path.stat().st_size,'sha256':h.hexdigest()}


def attempts(root,ledger):
    """Every start intent, ordered; directory identity comes from the recorded output."""
    found={}
    for event in ledger:
        if event.get('event')!='START_INTENT':continue
        output=event.get('output');path=Path(output) if output else root/str(event.get('attempt',event.get('arm','unknown')))/'flight'
        if not path.is_absolute():
            path=ROOT/path if output and str(path).startswith('data/') else root/path
        path=path.resolve()
        try:path.relative_to(root.resolve())
        except ValueError:raise ValueError('Ledger output is outside audit root: '+str(path))
        name=path.parent.name if path.name=='flight' else path.name
        if name not in found:found[name]={'flight':path,'start_intents':[],'arm':event.get('arm',name[:1])}
        found[name]['start_intents'].append(event)
    return found


def cost_total(records):
    totals={};missing={}
    for key in ['wall_s','cpu_s']:
        values=[];absent=[]
        for name,record in records.items():
            value=(record or {}).get(key)
            if isinstance(value,(int,float)) and np.isfinite(value):values.append(value)
            else:absent.append(name)
        totals[key]=sum(values);missing[key]=absent
    return {'recorded_total':totals,'missing_by_metric':missing,'complete':not any(missing.values())}


def local_evidence(d,start,end,path):
    topics=['vehicle_status','vehicle_local_position','vehicle_attitude','vehicle_angular_velocity','trajectory_setpoint','vehicle_local_position_setpoint','rate_ctrl_status','vehicle_control_mode','position_controller_status','actuator_motors','research_p11','research_memory','research_actuator','research_output','research_timing','raptor_status','research_target','vehicle_command','vehicle_command_ack']
    counts={}
    with gzip.open(path,'wt') as out:
        for topic in topics:
            z=d.get(topic,{});ts=np.asarray(z.get('timestamp',[]));ix=np.flatnonzero((ts>=start-200000)&(ts<=end))
            # Include predecessor to reconstruct sample-and-hold at lower bound.
            pred=int(np.searchsorted(ts,start-200000,side='left'))-1
            if pred>=0:ix=np.unique(np.r_[pred,ix])
            counts[topic]=len(ix)
            for i in ix:out.write(json.dumps({'topic':topic,**row(z,int(i))},allow_nan=False)+'\n')
    return {'file':path.name,'start_native_us':int(start-200000),'end_native_us':int(end),'topic_rows':counts,**digest(path)}


def audit(root,output):
    root=Path(root).resolve();output=Path(output);ledger=lines(root/'attempts.jsonl');listed=attempts(root,ledger)
    output.mkdir(parents=True,exist_ok=False)
    starts=[e for e in ledger if e.get('event')=='START_INTENT']
    result={'analysis_source':{'analyzer':digest(ROOT/'tools/cn_reference/analyze.py') if (ROOT/'tools/cn_reference/analyze.py').exists() else None,'audit':digest(Path(__file__))},'physical_start_count':len(starts),'count_note':'START_INTENT ledger count; each remains counted including failed/incomplete starts','physical_start_cap':None,'budget_note':'Original three-start budget superseded by user continuation; historical budget fields retained in ledger','starts':starts,'arms':{},'attempt_order':list(listed),'raw_manifest':{},'old_raw_preserved':[],'cost':{}}
    costs={};analyses={}
    for name,entry in listed.items():
        f=entry['flight'];r=load(f.parent/'result.json',{}) or {};arm=entry['arm'];costs[name]=r.get('execution_cost');analyses[name]=r.get('analysis')
        if not costs[name]:
            ends=[e for e in ledger if e.get('event')=='PHYSICAL_END' and (e.get('attempt')==name or e.get('output')==str(f) or (e.get('arm')==name))]
            if ends:costs[name]={k:ends[-1].get(k) for k in ['wall_s','cpu_s']}
        a={'logical_arm':arm,'source_run':str(f),'start_intents':entry['start_intents'],'status':r.get('status','UNKNOWN'),'failure_reason':r.get('reason'),'execution_cost':costs[name],'analysis_cost':analyses[name],'errors':[]}
        result['arms'][name]=a
        for path in [f.parent/'result.json',f.parent/'candidate-before.json',f.parent/'candidate-after.json']+[f/n for n in ['flight.ulg','telemetry.jsonl','resources.jsonl','events.jsonl','cn-setpoints.jsonl','metadata.json','config.json','logs/commands.log','logs/px4.log']]+sorted((f/'gz-motor').glob('motor-*.bin')):
            if path.exists():result['raw_manifest'][str(path.relative_to(root))]=digest(path)
        if not (f/'flight.ulg').exists():a.update(status='NO_ULOG',reason='Recorded start has no ULog; not counted as an unattempted arm');continue
        try:u=ULog(str(f/'flight.ulg'));d={z.name:z.data for z in u.data_list if z.multi_id==0}
        except Exception as exc:a['errors'].append('ULog: '+str(exc));continue
        ev=lines(f/'events.jsonl');meta=load(f/'metadata.json',{}) or {};recorded_measurement=load(f/'cn-reference-measurement.json',{}) or {}
        a['recorded_evidence_completion']=recorded_measurement.get('evidence_completion')
        a['recorded_measurement_status']=recorded_measurement.get('status')
        a['recorded_native_timeline']=recorded_measurement.get('native_timeline')
        try:measurement=analyze(f,arm)
        except Exception as exc:
            measurement={};a['errors'].append('current raw reanalysis: '+str(exc))
        a['current_measurement_status']=measurement.get('status','UNKNOWN')
        a['current_native_timeline']=measurement.get('native_timeline')
        a['measurement_verdict_source']='Read-only raw reanalysis with current analyzer; per-flight recorded verdict retained unchanged and separately.'
        begun=[e for e in ev if e.get('event')=='process_started'];stopped=[e for e in ev if e.get('event')=='process_stopped'];p=d.get('research_p11',{});own=d.get('research_actuator',{});s=d.get('vehicle_status',{});land=d.get('vehicle_land_detected',{})
        before=load(f.parent/'candidate-before.json');after=load(f.parent/'candidate-after.json')
        a.update(ulog_dropouts=len(u.dropouts),sim_seed=meta.get('sim_seed'),flown_commit=meta.get('project_commit'),candidate_before_after_equal=(before==after if before is not None and after is not None else None),active_samples=int(np.count_nonzero(p['active'])) if 'active' in p else None,neural_owner_samples=int(np.count_nonzero(own['owner']==1)) if 'owner' in own else None,process_started=begun,process_stopped=stopped,all_recorded_pids_absent=all(not Path('/proc',str(e['pid'])).exists() for e in begun) if begun else None,subject_event_counts={key:sum(e.get('event')==key for e in ev) for key in ['cn_trigger_state','handover_requested','cn_first_external_publish','cn_reference_finished']},evidence_completion=measurement.get('evidence_completion'))
        for topic in ['vehicle_status','vehicle_local_position','vehicle_land_detected']:
            z=d.get(topic,{});a['final_'+topic]=row(z,len(z['timestamp'])-1) if len(z.get('timestamp',[])) else None
        if len(s.get('timestamp',[])):
            changes=np.r_[0,np.flatnonzero(np.diff(s['nav_state'])!=0)+1];a['nav_transitions']=[row(s,int(i)) for i in changes]
            armed=np.flatnonzero(s['arming_state']==2);last=int(s['timestamp'][armed[-1]]) if len(armed) else 0;ix=np.flatnonzero((s['timestamp']>last)&(s['arming_state']!=2));a['disarmed_after_flight_native_us']=int(s['timestamp'][ix[0]]) if len(ix) and len(armed) else None
        if len(land.get('timestamp',[])):
            air=np.flatnonzero(~land['landed'].astype(bool));last=int(land['timestamp'][air[-1]]) if len(air) else 0;ix=np.flatnonzero((land['timestamp']>last)&land['landed'].astype(bool));a['landed_after_flight_native_us']=int(land['timestamp'][ix[0]]) if len(ix) and len(air) else None
        for topic in ['mission','mission_result']:
            z=d.get(topic,{});a[topic+'_rows']=[row(z,i) for i in range(len(z.get('timestamp',[])))]
        a['upload']={key:[e for e in ev if e.get('event')==event] for key,event in [('starts','cn_mission_upload_started'),('item_sends','cn_mission_item_sent'),('acks','cn_mission_ack')]}
        a['failures']=[e for e in ev if e.get('event')=='failure'];tl=measurement.get('native_timeline',{});start=tl.get('trigger_snapshot_anchor_us') if arm=='A' else tl.get('native_nav_entry_us')
        a['native_nav_entry_us']=tl.get('native_nav_entry_us');full=measurement.get('full_neural_analysis') or {};a['frozen_primary_outcome']=full.get('frozen_primary_outcome');a['task_outcome']=full.get('task_outcome')
        if start is not None:
            a['actual_subject_start']=snapshot(d,start);a['local_2_2s']=window(d,start,2.2);a['controller_state_limit']='Full logged P11 GRU/actions and classic rate controller state retained. Complete classic velocity integrator may be unavailable; missing topics are explicit.'
            a['local_source_evidence']=local_evidence(d,start,start+2200000,output/(name+'-local-topic-rows.jsonl.gz'))
            if arm=='A':
                l=d.get('vehicle_local_position',{});ts=np.asarray(l.get('timestamp',[]));ix=np.flatnonzero((ts>=start)&(ts<=start+2200000));w=a['local_2_2s']
                if len(ix):w.update(max_altitude_m=float((-l['z'][ix]).max()),max_radius_m=float(np.hypot(l['x'][ix],l['y'][ix]).max()))
                violations=[k for k,limit in [('max_tilt_deg',45),('max_angular_rate_component_rad_s',8),('max_altitude_m',8),('max_radius_m',10)] if w.get(k) is not None and w[k]>=limit]
                if w.get('min_altitude_m') is not None and w['min_altitude_m']<=.2:violations.append('ground altitude')
                w['local_physical_envelope']='FAILURE' if violations else ('SUCCESS' if w['complete'] and w.get('max_radius_m') is not None else 'UNKNOWN');w['physical_failure_reasons']=violations
            a['additional_controller_state']={k:a['actual_subject_start'].get(k) for k in ['rate_ctrl_status','vehicle_control_mode','setpoint_config','position_controller_status','raptor_status']}
    original=load(ROOT/'data/cn-single-20261109-final-v1/raw-evidence-manifest.json',{}) or {}
    for run,entries in original.items():
        for name,v in entries.items():
            path=ROOT/'data'/run/name;current=digest(path) if path.exists() else None
            result['old_raw_preserved'].append({'path':str(path.relative_to(ROOT)),'matches':current is not None and current['sha256']==v['sha256'],'sha256':current['sha256'] if current else None})
    result['old_raw_all_match']=all(v['matches'] for v in result['old_raw_preserved']) if result['old_raw_preserved'] else None
    result['cost']={'physical':cost_total(costs),'per_attempt_analysis':cost_total(analyses),'offline_test_cost_records':{p.name:load(p) for p in sorted(root.glob('*tests*cost*.json'))},'unmeasured':'Development, human/tool review, supplemental plotting and API billing not included; not zero'}
    measured=[k for k,v in result['arms'].items() if v.get('native_nav_entry_us') is not None];complete=[k for k,v in result['arms'].items() if (v.get('evidence_completion') or {}).get('complete')]
    result['conclusion']={'actual_neural_handoffs':measured,'evidence_complete_attempts':complete,'comparison_limit':'Explicit selected-attempt report is descriptive. Attempts with changed candidates are not matched causal ablations. All failed and superseded attempts and their costs remain here.','summary':f'{len(starts)} recorded starts; {len(measured)} attempts reached native neural navigation; {len(complete)} attempts have complete measurement evidence.'}
    (output/'audit.json').write_text(json.dumps(clean(result),indent=2,allow_nan=False)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();audit(a.root,a.output)
