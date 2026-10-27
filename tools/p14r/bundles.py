"""B finite-source support propagation, not an all-initial-set certificate.
The24 old-runtime points have no restorable OP buffer; keep that distinction
from the3 new-runtime diagnostic points instead of inventing hidden states.
"""
import sys,json,copy,time
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
from p14r.model import forecast
from p11.models import speeds

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);base=R/'data/p14r-20261027';plan=json.load(open(base/'B-bundle-plan-v2.json'));P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));rows=[];st=time.perf_counter()
 write(out/'before-compute.json',{'support_plan':sha(base/'B-bundle-plan-v2.json'),'per_family':12,'selection':'pre-event class round-robin fixed before propagation, not outcomes','future_model':'old complementary observer baseline for old66 support: OP buffer unavailable; new source-OP empirical points separately in compose/source comparisons','depths':[2,3,4],'rotor_phase':'all original4 values retained, never omitted or initialized to common phase','first_source_error_correction':'pending generated NN command separate from last consumed motor, previous code retained','no_claim_of_reachable_hull_or_future_support':True,'source':sha(Path(__file__))})
 for family in ['F2','F4']:
  ref='p13-F2-b1-AB-short' if family=='F2' else 'p13-F4-b1-AB-medium';template=json.load(open(R/'data/p14-motion-20261027/inputs-v3'/ref/'edge-input.json'));a=template['plan']['full_source_windows_profile_s'][0];duration=a[1]-a[0];windows=[[a[0]+n*(duration+.5),a[1]+n*(duration+.5)] for n in range(4)]
  for ident in plan['selected'][family]:
   doc=copy.deepcopy(template);i=json.load(open(base/'B-joint-support-v1'/ident/'initial.json'))['initial'];i['last_consumed_command']=i['pending_command'];i['pending_command']=np.asarray(speeds(np.array(i['previous'])),np.float32).astype(float).tolist();doc['initial']=i;doc['plan']['windows_profile_s']=doc['plan']['full_source_windows_profile_s']=windows;doc['plan']['stream_end_profile_s']=max(doc['plan']['stream_end_profile_s'],windows[-1][1]+2.5);end=windows[-1][1]+2;doc['plan']['horizon_profile_s']=end
   r=forecast(doc,{},P,limit=end,checkpoint_times=[b+.2 for a,b in windows]);tr=r['trace'];states=r['states'];check=[]
   for depth in [2,3,4]:
    limit=windows[depth-1][1]+.2;use=tr[:,0]<=limit;last=float(tr[use,0][-1]);loss=states[use,2]-i['physical_H0_NED_z'];check.append({'depth':depth,'requested_end':limit,'actual_end':last,'complete':last>=limit-.004001,'physical_D_upper_of_points_m':float(max(i['physical_D0_m'],max(loss))),'nominal_max_tilt_deg':float(max(tr[use,7])),'event_captures':sum(e['kind']=='CAPTURE' and e['sample_us']<=i['sample_us']+(limit-i['profile_s'])*1e6 for e in r['target_events'])})
   row={'id':ident,'family':family,'discrete_initial_count_index':[i['history_count'],i['call_index']],'phase_mod2':i['call_index']%2,'rotor_phase':i['rotor_phase'],'stops':r['stop'],'depths':check,'set_role':'individual empirically reachable observed initial point; own causal conditional nominal flow. Finite union cannot certify between points or unmodelled defects','OP_initial':'unavailable in old logs, old observer approximation explicitly retained','elapsed_s':None};write(out/ident/'result.json',row);np.savez_compressed(out/ident/'trajectory.npz',trace=tr,states=states);rows.append(row);print('B_BUNDLE',ident,r['stop'],flush=True)
 write(out/'summary.json',{'rows':rows,'elapsed_s':time.perf_counter()-st,'support_count':len(rows),'nonzero_initial_widths':'see observed inventory66 and new sourceOP seed-direction tube; not discarded by finite union','all_states_carried_between_events':True,'failure_D_latch_not_reset':True})
if __name__=='__main__':main()
