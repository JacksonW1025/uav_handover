import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'tools'),str(Path(__file__).parent)]
from height_constraints_v2 import motor_necessary_reserve,sufficient_recovery
from p12.execution import step
from p9_model import write
# Independently integrate the best upright, drag-free command trajectory.
W=.98;L=0.;maximum=0.;rot=np.full(4,750.)
for j in range(100):
 up=8.54858e-6*sum(rot**2)/2.0643076923076924-9.8;W-=up*.004;L+=W*.004;maximum=max(maximum,L);rot=step(rot,np.full(4,1000.),.004)
bound=motor_necessary_reserve(.98,[750]*4,Vrel=0,Ej=0)['necessary_additional_COM_margin_lower_m']
assert bound<=maximum+1e-15 and maximum-bound<1e-12
low=motor_necessary_reserve(.5,[750]*4)['necessary_additional_COM_margin_lower_m'];high=motor_necessary_reserve(.98,[750]*4)['necessary_additional_COM_margin_lower_m'];assert high>low>0
fast=motor_necessary_reserve(.98,[850]*4)['necessary_additional_COM_margin_lower_m'];assert fast<high
latency=motor_necessary_reserve(.98,[750]*4,Vrel=0,Ej=0,first_command=[750]*4)['necessary_additional_COM_margin_lower_m'];assert latency>bound
s=sufficient_recovery(.1,1.2,.98,2,1);assert s['D_upper_m']>=1.2 and s['L_end_upper_m']<.1
out=R/'data/p13-20261026-theory/height-constraints-v2/tests.json';write(out,{'schema':'p13-height-constraint-independent-tests-1','tests':5,'status':'PASS','drag_free_optimal_simulated_reserve_m':maximum,'outward_lower_bound_m':bound,'first_known_command_latency_reserve_m':latency,'retains_irreversible_D':True,'formal_experiment_unchanged':True});print('PASS5',maximum,bound,latency)
