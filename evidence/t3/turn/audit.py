#!/usr/bin/env python3
"""Supplement immutable score evidence with state, capture, motors, cleanup. New output only."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
sys.path.insert(0,str(Path(__file__).parent));import score as s
sys.path.insert(0,str(s.ROOT/'tools'));from output_chain import read_trace
m=s.m

def at(d,name,t):
 z=d.get(name,{});ts=np.asarray(z.get('timestamp',[]));ii=np.flatnonzero(ts<=t)
 if not len(ii):return None
 i=int(ii[-1]);return dict(age_us=int(t-ts[i]),row=m.row(z,i))
def audit(score_dir,out):
 r=m.load(score_dir/'score.json');f=Path(r['run']);u=ULog(str(f/'flight.ulg'));d={z.name:z.data for z in u.data_list if z.multi_id==0};ev=m.lines(f/'events.jsonl');meta=m.load(f/'metadata.json');cfg=m.load(f/'config.json');spec=cfg['explore'];start=r['start_native_us'];end=r['end_native_us'];req=r['request_lower_us']
 a=dict(score_file=str(score_dir/'score.json'),score_sha256=s.sha(score_dir/'score.json'),ulog_hash_matches_metadata=r['ulog_sha256']==meta.get('ulog_sha256'),candidate_unchanged=m.load(f.parent/'result.json',{}).get('candidate_unchanged'),spec=spec,request_state=m.state(m.snapshot(d,req)),request_snapshot=m.snapshot(d,req),start_state=r['pre_state'],start_us=start,request_us=req,parameters=[e for e in ev if e['event']=='hundred_parameters_before_arming'],reference_end_events=[e for e in ev if e['event']=='hundred_declared_reference_end_before_request'],memory_at_request=at(d,'research_memory',req),memory_before_start=at(d,'research_memory',start-1),first_neural_consumption=None)
 p=d['research_p11'];pt=p['timestamp'];ix=np.flatnonzero((pt>=start)&(pt<=end)&(p['active']==1)&(p['native_step']==1))
 if len(ix):a['first_neural_consumption']=m.row(p,int(ix[0]))
 q=d.get('research_target',{});qt=np.asarray(q.get('timestamp',[]));qi=np.flatnonzero((qt>=req)&(qt<=start+100000)&(np.asarray(q.get('kind',[]))==1)&(np.asarray(q.get('activation',[]))==1))
 a['activation_capture_rows']=[m.row(q,int(i)) for i in qi]
 native=(spec.get('handover_reference')=='native');zero=bool(len(qi)==1 and np.all(s.vector(q,'velocity')[qi[0]]==0) and q['mode'][qi[0]]==0)
 sends=m.lines(f/'explore-setpoints.jsonl');last_send_ns=max([x.get('after_ns',0) for x in sends],default=None)
 a['native_capture_semantics']=dict(expected=native,zero_velocity_activation_verified=zero,post_request_external_sends=sum(x.get('before_ns',0)>next((e['monotonic_ns'] for e in ev if e['event'] in ['handover_requested','lyapunov_classic_capture_requested'] and e.get('subject',True)),10**30) for x in sends),note='Base analyzer recognizes only exact reference_kind=native_capture, while this native_capture_after_classic_stream_end deliberately has no sender-matched active external reference; keep that original missing field but evaluate activation capture directly.')
 a['original_missing']=m.load(score_dir/'original-analysis.json').get('evidence_completion',{}).get('missing')
 owner=d['research_actuator'];ot=owner['actuator_timestamp'];ov=owner['owner'];incoming=1 if r['controller']=='neural' else 2;samples=ot[(ot>=start)&(ot<=end)&(ov==incoming)]
 a['owner_values_subject']=np.unique(ov[(ot>=start)&(ot<=end)]).tolist();a['four_motor_applications']={}
 for path in sorted((f/'gz-motor').glob('motor-*.bin')):
  motor,z,tail=read_trace(path);mi=np.flatnonzero((z['sim_us']>=start)&(z['sim_us']<=end)&np.isin(z['applied_sample_us'],samples))
  if len(mi):
   j=int(mi[0]);a['four_motor_applications'][str(motor)]=dict(first_sim_us=int(z['sim_us'][j]),sample_us=int(z['applied_sample_us'][j]),delay_us=int(z['sim_us'][j])-start,partial_tail_bytes=tail)
 a['four_motors_observed']=len(a['four_motor_applications'])==4
 land=d.get('vehicle_land_detected',{});lt=np.asarray(land.get('timestamp',[]));li=np.flatnonzero((lt>end)&np.asarray(land.get('landed',[]),bool));vs=d['vehicle_status'];st=vs['timestamp'];di=np.flatnonzero((st>end)&(vs['arming_state']!=2))
 a['completion']=dict(first_landed_native_us=int(lt[li[0]]) if len(li) else None,first_disarmed_native_us=int(st[di[0]]) if len(di) else None,normal_landing_ready=any(e['event']=='ready' and e.get('condition')=='landing' for e in ev),normal_disarmed_ready=any(e['event']=='ready' and e.get('condition')=='disarmed' for e in ev),emergency_landing_incomplete=[e for e in ev if e['event']=='explore_emergency_landing_incomplete'],process_stops=[e for e in ev if e['event']=='process_stopped'],cleanup_error=m.load(f.parent/'result.json',{}).get('cleanup_error'))
 a['note']='Post-subject landing/disarm observed independently; no preflight landed sample counted. No flight spawned and no old evidence changed.'
 if out.exists():raise RuntimeError('refuse existing output')
 s.write(out,a);return a
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--score-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);x=ap.parse_args();a=audit(x.score_dir,x.out);print(json.dumps(dict(four_motors=a['four_motors_observed'],hash_match=a['ulog_hash_matches_metadata'],zero_capture=a['native_capture_semantics']['zero_velocity_activation_verified'],completion=a['completion']),ensure_ascii=False))
