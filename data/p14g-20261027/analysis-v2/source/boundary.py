"""H1 conditional delivery-boundary responses, no actual future input."""
import sys,json,time,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *
from p14g.partition import resume_zones,member
from p14g.cell import Delivery,Word

def main():
 out=Path(sys.argv[1]);register(out,'H1: two release-times straddlingallowedread by0.19ms; whole response notpurecapturephase',CPU_s=60);limit(60)
 # Model remains the source/state observer. Only the planned cell publisher is selected.
 import p14g.model as M
 M.Delivery=Delivery;P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));rows=[];start=time.perf_counter()
 for n in cases():
  d=json.load(open(B/'inputs-v1'/n/'input.json'));d['initial']['p14g_innovation']['mode']='held'
  if not d['plan']['windows_profile_s']:rows.append({'id':n,'status':'NO_EVENT_CONTROL','not_invented_resume':True});continue
  i=d['initial'];b=d['plan']['windows_profile_s'][0][1];reads=[i['profile_s']+.004*k for k in range(1,500) if (i['call_index']+k-1)%2==0];R0=next(r for r in reads if r>b+.0002);result=[]
  for side in [-1,1]:
   pub=R0+side*.00019;q=copy.deepcopy(d);q['plan']['p14g_cell']={'publish_s':pub,'delivery_s':pub,'first_allowed_read_s':R0 if side<0 else R0+.008};r=M.forecast(q,{},P,observer_library=OLD/'offline-build-v2/libop.bin',word=Word(),limit=b+.5);tr=r['trace'];stale=tr[:,34].astype(bool);j=int(np.flatnonzero(~stale & np.r_[False,stale[:-1]] & (tr[:,0]>=b))[0]);result.append({'side':side,'P':pub,'D':pub,'read_boundary':R0,'actual_predicted_resume':float(tr[j,0]),'first_action':tr[j,8:12].tolist(),'cached_tilt_peak_next0.5s':float(max(tr[tr[:,0]>=b,7])),'COM_loss_peak_next0.5s':float(max(r['states'][tr[:,0]>=b,2]-i['physical_H0_NED_z'])),'conditional_source_point':True})
  rows.append({'id':n,'rows':result,'read_jump_s':result[1]['actual_predicted_resume']-result[0]['actual_predicted_resume'],'first_action_L2_change':float(np.linalg.norm(np.array(result[1]['first_action'])-result[0]['first_action'])),'same_discrete_cell_does_not_mean_same_full_trajectory':True})
 write(out/'result.json',{'rows':rows,'elapsed_s':time.perf_counter()-start,'future_actual_used':False,'conditions':'10ms host service, zero transport, source normal sample/native4ms,PH1read. One plannedcell representative per side. Fullzone timewidth notpropagated asuncertainty.'})
if __name__=='__main__':main()
