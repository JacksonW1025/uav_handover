"""Read-only independent analysis; immutable per-attempt records, refresh aggregate views."""
import sys,json,csv,hashlib,collections,argparse,math,traceback
from pathlib import Path
import numpy as np
ROOT=Path('/home/car/uav_handover');BATCH=ROOT/'data/handover-mutation-20261111';OUT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(Path(__file__).parent))
import metrics_base as m
from output_chain import read_trace
from pyulog import ULog

def write(path,obj):path.write_text(json.dumps(m.clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def supplement(result,flight):
    if not (flight/'flight.ulg').exists():return result
    u=ULog(str(flight/'flight.ulg'));d={v.name:v.data for v in u.data_list if v.multi_id==0}
    events=m.lines(flight/'events.jsonl');result['parameter_events']=[e for e in events if e['event'] in ['hundred_parameters_before_arming','hundred_rini_after_valid_exit','hundred_reference_transition','physical_variant_configured']]
    result['source_integrity']={'recorded_ulog_sha256':result.get('metadata',{}).get('ulog_sha256'),'computed_ulog_sha256':result.get('ulog_sha256')}
    result['source_integrity']['matches']=result['source_integrity']['recorded_ulog_sha256']==result['source_integrity']['computed_ulog_sha256']
    result['sequence_audit']={'planned':[v[1] for v in result.get('explore',{}).get('switches',[])],'requested':[v['to_controller'] for v in result.get('subject_requests',[])],'actual':['N' if b['owner_boundary']['to']==1 else 'C' for b in result.get('boundaries',[]) if 'owner_boundary' in b]}
    result['sequence_audit']['complete']=result['sequence_audit']['planned']==result['sequence_audit']['requested']==result['sequence_audit']['actual']
    result['target_capture_events']=[m.row(d['research_target'],int(i)) for i in np.flatnonzero(np.asarray(d.get('research_target',{}).get('kind',[]))==1)]
    result['realized_model_properties']=m.load(flight/'realized-model-properties.json')
    result['motor_time_constants_realized']={}
    if result.get('explore',{}).get('physical_variant'):
        from p12.execution import DTYPE
        for path in sorted((flight/'gz-motor').glob('execution-p12-*.bin')):
            z=np.fromfile(path,dtype=DTYPE)
            result['motor_time_constants_realized'][path.name]={'rows':len(z),'tail_bytes':path.stat().st_size%DTYPE.itemsize,'tau_up':np.unique(z['tau_up']).tolist(),'tau_down':np.unique(z['tau_down']).tolist()}
    result['physical_evidence_scope']='Model configuration/hashes, recorded running Gazebo query and per-step motor tau evidence are retained separately. Parameter realization requires checking the query/trace, not merely this design label.' if result.get('explore',{}).get('physical_variant') else 'Stock x500 model'
    motors={};tails={}
    for path in sorted((flight/'gz-motor').glob('motor-*.bin')):
        try:
            motor,z,tail=read_trace(path);motors[motor]=z;tails[motor]=tail
        except Exception as ex:result['errors'].append('motor trace '+path.name+': '+repr(ex))
    owner=d.get('research_actuator',{});ot=np.asarray(owner.get('actuator_timestamp',[]));ov=np.asarray(owner.get('owner',[]))
    for b in result.get('boundaries',[]):
        if 'owner_boundary' not in b:continue
        t=b['owner_boundary']['timestamp_us'];end=b['subject_end_us'];incoming=b['owner_boundary']['to']
        b['post_takeover_states']={}
        for name,at in [('plus_1s',t+1000000),('plus_2s',t+2000000),('subject_end',end)]:
            b['post_takeover_states'][name]={'available_in_subject':at<=end,'native_us':at,'state':m.state(m.snapshot(d,at)) if at<=end else None}
        mem=d.get('research_memory',{});mt=np.asarray(mem.get('timestamp',[]));ix=np.flatnonzero((mt>=t-100000)&(mt<=min(end,t+100000)))
        # Keep actual controller memory events, no invented interpretation of missing fields.
        b['controller_memory_events_near_boundary']=[m.row(mem,int(i)) for i in ix]
        p=d.get('research_p11',{});pt=np.asarray(p.get('timestamp',[]));pi=np.flatnonzero((pt>=t)&(pt<=end)&np.asarray(p.get('active',[]),bool))
        if len(pi):
            first=m.row(p,int(pi[0]));b['first_neural_consumed_state']={key:first[key] for key in first if key.startswith(('network_target','position','velocity','target_yaw','external_valid','stale','read_wall_ns','timestamp'))}
        samples=ot[(ov==incoming)&(ot>=t)&(ot<=end)];applied={}
        for motor,z in motors.items():
            ix=np.flatnonzero((z['sim_us']>=t)&(z['sim_us']<=end)&np.isin(z['applied_sample_us'],samples))
            if len(ix):
                j=int(ix[0]);applied[str(motor)]={'first_sim_us':int(z['sim_us'][j]),'applied_sample_us':int(z['applied_sample_us'][j]),'first_boundary_publication_applied':int(z['applied_sample_us'][j])==t,'delay_from_owner_us':int(z['sim_us'][j])-t,'partial_tail_bytes':tails[motor]}
        b['first_physical_motor_applications']=applied;b['four_motors_observed']=len(applied)==4
        att=d.get('vehicle_attitude',{});at=np.asarray(att.get('timestamp',[]));tilt=np.degrees(np.arccos(np.clip(1-2*(att['q[1]']**2+att['q[2]']**2),-1,1))) if len(at) else np.array([])
        bad=np.flatnonzero((at>=t)&(at<=end)&(tilt>45.))
        b['first_45deg_exceedance_s']=(int(at[bad[0]])-t)/1e6 if len(bad) else None
        b['risk_temporal_class']='within_first_1s' if len(bad) and b['first_45deg_exceedance_s']<=1 else ('within_first_2s' if len(bad) and b['first_45deg_exceedance_s']<=2 else ('later_post_handover' if len(bad) else 'no_observed_45deg_exceedance'))
    return m.clean(result)
