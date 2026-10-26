import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,'tools')
from p3_memory import load_policy,gru_step
P=load_policy();d=dict(np.load('data/p11-20261025-development/dev11-complete-timing-on/observation/synchronized.npz'))
W=P['Wh'];norm=lambda a:float(np.max(np.sum(np.abs(a),axis=1)))
L=1+.5*norm(W[16:32])+norm(W[32:])+.25*norm(W[:16])*(norm(W[32:])+float(np.max(np.abs(P['bh'][32:]))))
ids=np.unique(np.linspace(0,len(d['input'])-1,128).astype(int));values=[];eps=1e-5
for i in ids:
 h=d['h_before'][i];x=d['input'][i];J=np.column_stack([(gru_step(P,h+eps*np.eye(16)[k],x)-gru_step(P,h-eps*np.eye(16)[k],x))/(2*eps) for k in range(16)])
 values.append(float(np.linalg.norm(J,2)))
r={'policy_sha256':P['sha256'],'domain':'hidden in [-1,1]^16, arbitrary network input; original reset and convex GRU update preserve this domain without out-of-domain memory injection',
 'global_hidden_infinity_lipschitz_coarse':L,'derivation':'|dhprime/dh|inf <= 1 + .5||Wh_z||inf + ||Wh_n||inf + .25||Wh_r||inf (||Wh_n||inf+|bh_n|inf), via sigmoid derivative<=.25, tanh<=1, |h-n|<=2. Conservative analytic bound, not a contraction certificate.',
 'sample_local_Jh_spectral_norm':{'n':len(values),'min':min(values),'max':max(values),'median':float(np.median(values)),'finite_difference_epsilon':eps},
 'classification':'global bound source/math checked; finite-difference local norms only sampled evidence. Bound>1 does not refute another weighted contraction or hybrid storage inequality.',
 'state_interface':'must include action-history mean, previous action, sampler/hold and target modes with GRU; isolated h bound alone is not full incremental gain'}
Path('data/p11-20261025-preparation/local-network-check.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
