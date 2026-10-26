import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,'tools')
from p3_memory import load_policy
P=load_policy();W0=np.abs(P['W0']);Wi=np.abs(P['Wi']);Wh=np.abs(P['Wh'])
# Rigorous analytic Lipschitz matrices; floating numbers here only evaluate the formula.
# h in [-1,1], independent of x. Candidate hidden recurrent term bounded by row sum+bias.
B=np.sum(Wh[32:],axis=1)+np.abs(P['bh'][32:])
H=np.eye(16)+Wh[32:]+.25*B[:,None]*Wh[:16]+.5*Wh[16:32]
X=(Wi[32:]+.25*B[:,None]*Wi[:16]+.5*Wi[16:32])@W0
A=np.abs(P['W2'])
res={'policy_sha256':P['sha256'],'h_inf_bound':float(H.sum(axis=1).max()),'x_to_h_inf_bound':float(X.sum(axis=1).max()),'h_to_action_bound':float((A@H).sum(axis=1).max()),'x_to_action_bound':float((A@X).sum(axis=1).max()),'first_call_action_bound_for_dx_001_dh_001':float((A@H*.001).sum(axis=1).max()+(A@X*.001).sum(axis=1).max())}
print(json.dumps(res,indent=2));Path('data/p12-20261026-analysis/theory-global-gains.json').write_text(json.dumps(res,indent=2)+'\n')
