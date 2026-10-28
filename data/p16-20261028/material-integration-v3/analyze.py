"""Essential source replay, execution/guard and original task labels only."""
import sys,json,time,resource
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p16.common import *
from p16.quality import label,task
from p12.observe import analyze as observe
from p12.execution import audit as execution
from p12b.audit import audit as native
from p11.pack import measure,source_plan
from p5_metrics import window_basics
from pyulog import ULog

def prefix_truth(run,d,ev,meas,epoch,Bstart):
 # Use the original task H0/native window, with scientific stop before cleanup.
 tt=(d['run_wall_ns'].astype(np.int64)-epoch)/1e9
 failure=next((e for e in ev if e['event']=='failure'),None)
 post=next((e for e in ev if e['event']=='p1_phase_ended' and e.get('label')=='post_stream'),None)
 scored_host_stop=(failure or post or {}).get('monotonic_ns',int(d['run_wall_ns'][-1]))
 jB=int(np.searchsorted(tt,Bstart));B_reached=bool(jB<len(tt) and d['run_wall_ns'][jB]<=scored_host_stop)
 prefix_start=meas['window_native_us'][0]
 prefix_stop=min(meas['window_native_us'][1],int(d['native_us'][jB]) if B_reached else meas['window_native_us'][1])
 cfg=json.load(open(run/'config.json'))
 topics={x.name:x.data for x in ULog(str(run/'flight.ulg'),['vehicle_local_position','vehicle_attitude','vehicle_angular_velocity','actuator_motors']).data_list if x.multi_id==0}
 prefix_measure=window_basics(cfg,topics,prefix_start,prefix_stop,prefix_start)
 tilt=label(prefix_measure['max_tilt_deg'],45,B_reached);height=label(prefix_measure['max_altitude_loss_m'],1,B_reached)
 risks=dict(tilt=tilt,height=height,task=task(tilt,height))
 return dict(risks=risks,measurement=prefix_measure,B_reached=B_reached,window_native_us=[prefix_start,prefix_stop],height_reference_native_us=prefix_start,scored_host_stop_ns=int(scored_host_stop))

def analyze(target,out):
 st=time.perf_counter();cpu=time.process_time();run=target/'run';out.mkdir(exist_ok=False)
 ob=observe(run,out/'observation');ex=execution(run,out/'execution');nt=native(run,out/'native');meas=measure(run,out/'observation/synchronized.npz',out/'measurement');d=np.load(out/'observation/synchronized.npz');ev=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()];epoch=next(x['run_wall_ns'] for x in ev if x['event']=='p12_confirmed_native_stream_anchor');tt=(d['run_wall_ns'].astype(np.int64)-epoch)/1e9;direct_ok=False
 from p12b.read_trace import load
 dr=load(run/'gz-motor/read-p12b.bin');ds=dr['timestamp_sample'][dr['active'].astype(bool)];ds=ds[(ds>=d['sample_us'][0])&(ds<=d['sample_us'][-1])];direct_ok=bool(np.array_equal(ds,d['sample_us']))
 # Known ULog timing auxiliary tail may be absent; canonical P11/direct continuous
 # same-call identity plus no interior gaps is required, not a blanket first/lastrow deletion.
 obok=all(v for k,v in ob['gates'].items() if k!='all_control_calls') and not ob['problems'] and direct_ok
 gates=dict(source_replay=bool(obok),direct_identity=direct_ok,execution=ex['status']=='PASS',native_contract=nt['status']=='PASS',measurement=meas['status']=='MEASURED',runtime_stable=json.load(open(target/'execution.json'))['candidate_unchanged'])
 complete=not meas['censored'];tilt=label(meas['whole']['max_tilt_deg'],45,complete);height=label(meas['whole']['max_altitude_loss_m'],1,complete);risks=dict(tilt=tilt,height=height,task=task(tilt,height));plan=json.load(open(target/'row.json'));cfg=json.load(open(run/'config.json'));origin=next(e for e in ev if e['event']=='p1_reference_origin');planned=source_plan(cfg,origin['origin_ned_m'],origin['yaw_rad']);Bstart=planned['full_source_windows_profile_s'][1][0];A=planned['common_first_gap_profile_s'];before=tt<Bstart;j=max(0,min(len(tt)-1,int(np.searchsorted(tt,A))));H0=-float(d['position'][j,2]);th=np.degrees(np.arccos(np.clip(1-2*(d['attitude'][:,1]**2+d['attitude'][:,2]**2),-1,1)));prefix=before&(tt>=A);prefix_failed=bool(np.any(th[prefix]>45) or np.any(d['position'][prefix,2]+H0>1));captures=[];stale=d['stale'].astype(bool)
 failure=next((e for e in ev if e['event']=='failure'),None);post=next((e for e in ev if e['event']=='p1_phase_ended' and e.get('label')=='post_stream'),None);scored_host_stop=(failure or post or {}).get('monotonic_ns',int(d['run_wall_ns'][-1]))
 for k in np.flatnonzero(np.diff(stale.astype(int))!=0)+1:
  if tt[k]>=A-.05 and d['run_wall_ns'][k]<=scored_host_stop:captures.append(dict(kind='capture' if stale[k] else 'resume',profile_s=float(tt[k]),sample_us=int(d['sample_us'][k]),native_us=int(d['native_us'][k])))
 # Prefix truth uses the same ULog LP/attitude/H0 and native window as the
 # original measurement, not controller-cache height or a new B-local baseline.
 prefix_report=prefix_truth(run,d,ev,meas,epoch,Bstart);B_reached=prefix_report['B_reached'];prefix_measure=prefix_report['measurement'];prefix_risks=prefix_report['risks']
 result=dict(id=target.name,valid=all(gates.values()),gates=gates,**risks,complete=complete,censored=not complete,peak_tilt=meas['whole']['max_tilt_deg'],peak_loss=meas['whole']['max_altitude_loss_m'],peak_scope='exact full measured window only when complete; censored peaks are lowerbounds, never exact safe labels',original_flight=meas['frozen_flight_outcome'],original_measurement=meas,prefix_failed_before_B=True if prefix_risks['task']=='FAIL' else False if prefix_risks['task']=='SUCCESS' else None,prefix_before_B=prefix_risks,prefix_measurement=prefix_measure,prefix_window_native_us=prefix_report['window_native_us'],prefix_coverage_to_B=B_reached,prefix_height_reference='same A task start and ULog LP as original measure; no reset at B',controller_cache_prefix_failed_before_B=prefix_failed,B_plan_reached=B_reached,event_changes=captures,full_state_raw='observation/synchronized.npz retains h/action/LP/cache/native; future scoring only',source_observation_status=ob['status'],optional_physics='P13 direct physical buffer saved separately; task criterion remains LP/attitude, no fabricated missing physical states',cost=dict(CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-st),raw_hashes=dict(ulog=sha(run/'flight.ulg'),direct=sha(run/'gz-motor/read-p12b.bin')))
 write(out/'result.json',result);return result
if __name__=='__main__':
 t=Path(sys.argv[1]);r=analyze(t,Path(sys.argv[2]));print('P16_REVIEW',r['valid'],r['task']);raise SystemExit(0 if r['valid'] else 2)
