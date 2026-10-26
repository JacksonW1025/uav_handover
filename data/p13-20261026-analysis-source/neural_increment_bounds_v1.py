"""Actual frozen weights, analytic global incremental bound (not sampled Jacobian).
Real-weight GRU map only; floating inference error is an additional unproved
future budget, not filled with observed replay residual. Conservatism retained.
"""
import sys,json,math
from pathlib import Path
from fractions import Fraction as F
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p9_model import write,sha
P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'))
def mat(x):return [[F(float(v)) for v in row] for row in x]
def mul(A,B):return [[sum((a*b for a,b in zip(row,col)),F(0)) for col in zip(*B)] for row in A]
def plus(A,B):return [[a+b for a,b in zip(x,y)] for x,y in zip(A,B)]
def scale(A,c):return [[x*c for x in row] for row in A]
def diagleft(d,A):return [[c*x for x in row] for c,row in zip(d,A)]
def mv(A,v):return [sum((a*b for a,b in zip(row,v)),F(0)) for row in A]
def up(v):
 x=float(v)
 return math.nextafter(x,math.inf) if F(x)<v else x
W0=mat(abs(P['W0']));Wi=mat(abs(P['Wi']));Wh=mat(abs(P['Wh']));W2=mat(abs(P['W2']));N=[sum(row,F(0))+F(abs(float(b))) for row,b in zip(Wh[32:],P['bh'][32:])]
Ar=scale(mul(Wi[:16],W0),F(1,4));Br=scale(Wh[:16],F(1,4));Az=scale(mul(Wi[16:32],W0),F(1,4));Bz=scale(Wh[16:32],F(1,4));An=plus(mul(Wi[32:],W0),diagleft(N,Ar));Bn=plus(Wh[32:],diagleft(N,Br));A=plus(An,scale(Az,F(2)));B=plus(plus(Bn,scale(Bz,F(2))),[[F(int(i==j)) for j in range(16)] for i in range(16)])
# |dh_tmp|<=A|dx22|+B|dh|; ReLU1,tanh1,sigmoid1/4.
# Noncommit holds h but uses this tmp state for output; action/mean update every call.
scenarios=[]
for eps in [F(1,10**12),F(1,10**6),F(1,1000)]:
 for first_commit in [False,True]:
  h=[eps]*16;prev=[eps]*4;mean=[eps]*4;count=0;rows=[]
  for j in range(8):
   mean=[(count*a+b)/(count+1) for a,b in zip(mean,prev)];x=[F(0)]*18+mean;tmp=[min(F(2),a+b) for a,b in zip(mv(A,x),mv(B,h))];action=[min(F(2),x) for x in mv(W2,tmp)];commit=(j%2==0)==first_commit
   if commit:h=tmp;count=0
   else:count+=1
   prev=action;rows.append({'output_call':j+1,'commit':commit,'action_bound_inf':up(max(action)),'hidden_bound_inf':up(max(h)),'mean_bound_inf':up(max(mean))})
  scenarios.append({'initial_memory_action_error':up(eps),'same_exogenous_inputs18':True,'first_commit':first_commit,'first_action_bound_reaches_absolute2_call':next((x['output_call'] for x in rows if x['action_bound_inf']>=2),None),'rows':rows})
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);write(out/'bounds.json',{'schema':'p13-weight-source-increment-bounds-1','policy_arrays_sha256':sha(R/'data/p13-20261026-freeze/models/policy.npz'),'derivation':'ReLU1, sigmoid1/4, tanh1; N=abs(Wh_n)1+abs(bh_n); An=abs(Wi_n)abs(W0)+diag(N)Ar; Bn=abs(Wh_n)+diag(N)Br; A=An+2Az; B=Bn+I+2Bz; clip nonexpansive. Mean convex update and exact commit modes are retained.','coefficient_arithmetic':'exact rational arithmetic on stored float32 weights, final floats rounded upward','A_inf_exact':str(max(sum(row,F(0)) for row in A)),'A_inf_upper':up(max(sum(row,F(0)) for row in A)),'B_inf_exact':str(max(sum(row,F(0)) for row in B)),'B_inf_upper':up(max(sum(row,F(0)) for row in B)),'W2_inf_upper':up(max(sum(row,F(0)) for row in W2)),'scenarios':scenarios,'result':'valid conservative real-network bound rapidly becomes uninformative, does not prove actual neural divergence or refute contraction in a coupled restricted domain','full_flight_causal_intervention':False,'future_FP_error_budget':'NOT_PROVEN, no observed maximum promoted','complete_event_certificate':'NOT_ESTABLISHED; first explicit inequality degenerates to action absolute bound before useful full feedback propagation','A4':'NOT_PROVEN_EXCLUDED'})
print('A/B/W2',up(max(sum(r,F(0)) for r in A)),up(max(sum(r,F(0)) for r in B)),up(max(sum(r,F(0)) for r in W2)));print([(x['initial_memory_action_error'],x['first_commit'],x['first_action_bound_reaches_absolute2_call']) for x in scenarios])
