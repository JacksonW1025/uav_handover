"""Complete serialized conditional successor, without rerunning dynamics.

The first edge version carried queue/timing in the live loop but omitted some
fields in checkpoint metadata. Reconstruct them from the SAME declared plan,
not actual future data. Physical/history generators are unchanged references.
"""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import write,sha
from p11.models import reference

def discrete(doc,steps):
 i=doc['initial'];p=doc['plan'];index=i['call_index'];count=i['history_count'];last_read=i['last_read_us'];last_send=i['last_send_profile_s'];pending=None;table=np.array(p['profile']['table'])
 for k in range(1,steps+1):
  t=i['profile_s']+.004*k;now=i['native_us']+4000*k;inside=any(a<=t<b for a,b in p['windows_profile_s'])
  if 0<=t<p['stream_end_profile_s'] and not inside and t-last_send>=p['publish_period_s']-1e-10:pending=reference(t,p['profile'],table);last_send=t
  commit=index%2==0;allowed=p['p12_phase']==0 or p['p12_phase']==1 and commit or p['p12_phase']==2 and not commit
  if pending is not None and allowed:pending=None;last_read=now
  count=0 if commit else count+1;index+=1
 return {'last_sample_us':int(i['sample_us']+4000*steps),'native_us':int(i['native_us']+4000*steps),'profile_s':float(i['profile_s']+.004*steps),'index':int(index),'count':int(count),'last_valid_read_native_us':int(last_read),'last_send_profile_s':float(last_send),'target_pending_slot':None if pending is None else {'p':pending[0].tolist(),'v':pending[1].tolist(),'yaw':float(pending[2])},'stale':bool(i['native_us']+4000*steps-last_read>200000),'force_sync':2,'initialized':True,'activation_external_seen':True,'LP_update_phase_us':int(i['lp_phase_us']),'mode':'NEURAL_ACTIVE','clock_word_condition':'nominal4ms only; no actual future stamps','next_call_commit':bool(index%2==0)}

def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);base=ROOT/'data/p14-motion-20261027';edge=json.load(open(base/'delivery-v5/map-edge.json'));doc=json.load(open(ROOT/edge['input']['initial']));tube=json.load(open(base/'tubes-final-v2/03-p13-F2-b1-AB-short-r0.001-joint-group1-obs0-joinbox0/tube.json'));checks=[]
 for label,stage in edge['output']['stages'].items():
  live=tube['regions'][label];d=discrete(doc,live['metrics']['call']);assert d['index']==live['index'] and d['count']==live['count'] and d['last_valid_read_native_us']==live['last_read_native_us'] and d['stale']==live['stale']
  prefix=[x for x in tube['rows'] if x['t']<=live['t']];lower=max(0,doc['initial']['physical_D0_m']-.00001,max(x['L_interval_m'][0] for x in prefix))
  stage['successor_discrete']=d;stage['history_D_outer_relation']={'interval_m':[lower,live['D_upper_m']],'constraints':['D>=p_COM_NED_z-H0_NED_z','D>=0','D_next>=D_previous'],'past_failure_latch':'never cleared by capture/resume','representation':'monotone scalar interval + current-state relational constraint; full past-max generator correlation NOT retained','effect':'conservative projection, not exact reachable set; existing internal-state generators retained'}
  # JSON round trip includes the actual pending slot, not only its emptiness.
  assert json.loads(json.dumps(d))==d
  checks.append({'stage':label,'live_loop_discrete_fields_match':True,'JSON_roundtrip_equal':True,'pending_slot_present':d['target_pending_slot'] is not None})
 edge['schema']='conditional-moving-event-map-edge-2';edge['previous_version']='delivery-v5/map-edge.json';edge['serialization_correction']='explicit queue/last-send/sample/native/control phase added; all numerical bounds/arrays unchanged';edge['successor_arrays']='same shared center/G files from v5; local chart sidecar is optional, primary physical quaternion + unit-group condition retained';edge['edge_composition']['D_representation']='monotone interval with D>=currentL constraint; no claim all path-D correlations retained'
 write(out/'map-edge.json',edge);write(out/'serialization-audit.json',{'checks':checks,'model_or_threshold_change':False,'original_live_composition_unchanged':True,'new_SITL':0,'source_sha256':sha(Path(__file__))});print('SERIALIZATION_VERIFIED',checks)

if __name__=='__main__':main()
