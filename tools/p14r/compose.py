"""Actual serialization/continuation of source point maps through2/3/4 events.
Continuous tubes stop at their recorded domain loss; these nominal continuations
are diagnostic map structure and do not relabel TOP as a safety certificate.
"""
import sys,json,copy,time
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
from p14r.model import forecast
from p14r.delivery import Word

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);doc=json.load(open(R/'data/p14r-20261027/source-inputs-v3/d02/input.json'));P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));lib=R/'data/p14r-20261027/offline-build-v2/libop.bin';a,b=doc['plan']['full_source_windows_profile_s'][:2];duration=a[1]-a[0];gap=.5;windows=[[a[0]+n*(duration+gap),a[1]+n*(duration+gap)] for n in range(4)];doc['plan']['windows_profile_s']=windows;doc['plan']['full_source_windows_profile_s']=windows;end=windows[-1][1]+2;doc['plan']['stream_end_profile_s']=max(end+.5,doc['plan']['stream_end_profile_s']);doc['plan']['horizon_profile_s']=end
 stages=[x[1]+.2 for x in windows];write(out/'before-compute.json',{'depths':[2,3,4],'events':windows,'same_initial_and_plan':True,'source':sha(Path(__file__)),'word':{'publisher':'4ms nominal service, immediate gap exit, latest value','producer':'PRE, fixed causal nominal; no future actual cache'},'model_scope':'conditional source point; tube failure retained separately; not event safety guarantee','joint_internal_state':'live target/profile/history/queue+OP ring/integrals+physical buffer+gyro delays retained','D':'physical and LP separate, no reset','new_SITL':0})
 st=time.perf_counter();full=forecast(doc,{},P,observer_library=lib,limit=end,checkpoint_times=stages);write(out/'full-summary.json',{k:v for k,v in full.items() if not isinstance(v,np.ndarray)});np.savez_compressed(out/'full.npz',**{k:v for k,v in full.items() if isinstance(v,np.ndarray)})
 rows=[]
 for n,cp in enumerate(full['checkpoints']):
  successor=copy.deepcopy(doc);successor['initial']=cp['initial'];write(out/f'edge-{n+1}-successor.json',successor);continued=forecast(successor,{},P,observer_library=lib,limit=end);j=np.flatnonzero(full['trace'][:,0]>=cp['actual_time']-1e-9)[0];m=min(len(continued['trace']),len(full['trace'])-j);error={key:float(np.max(abs(continued[key][:m]-full[key][j:j+m]))) for key in ['trace','states']};rows.append({'depth_at_checkpoint':n+1,'time':cp['actual_time'],'comparison_rows':m,'split_run_vs_uninterrupted':error,'physical_D0_m':cp['initial']['physical_D0_m'],'LP_D0_m':cp['initial']['LP_D0_m'],'NN_count_index':[cp['initial']['history_count'],cp['initial']['call_index']],'queues':{'publisher_transit':len(cp['initial']['delivery_live']['transit']),'target_pending':cp['initial']['controller_live']['pending'] is not None,'observer_publications':len(cp['initial']['observer_live']['queue'])},'stop':continued['stop'],'type':'nominal serialized map continuation, no set containment beyond tube domain'})
 write(out/'composition.json',{'rows':rows,'full_stop':full['stop'],'target_events':full['target_events'],'elapsed_s':time.perf_counter()-st,'all_checkpoint_continuations_close':all(max(r['split_run_vs_uninterrupted'].values())<1e-8 for r in rows),'future_actual_used':False,'handover_predecessor':'real C->N source operator independently audited in handover-v1, warm-up empirical prefix links to this initial region; classic active flow not silently simulated'})
if __name__=='__main__':main()
