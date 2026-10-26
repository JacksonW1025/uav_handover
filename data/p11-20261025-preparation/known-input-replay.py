"""Post-hoc physics replay using actual command history; NEVER a causal forecast."""
import argparse,json,sys,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from p11.models import plant,speeds,motor_step,R,G
from p11.score import so3
from p9_model import write

def replay(case,models):
 d=dict(np.load(case/'packed/measurement.npz'));t=d['profile_s'];plan=json.loads((case/'packed/prediction-input.json').read_text())['plan'];start=int(np.searchsorted(t,plan['common_first_gap_profile_s']));report={}
 for name in ['M1','M2']:
  mod=models[name];cmd=np.array([speeds(a) for a in d['action']]);rot=cmd.copy()
  for k in range(1,len(t)):rot[k]=motor_step(rot[k-1],cmd[max(0,k-2)])
  windows={}
  for horizon in [.004,.5,2.,None]:
   errors=[];ang=[];used=0
   starts=range(start,len(t)-2, max(1,round((horizon or (t[-1]-t[start]))/.004)))
   for i in starts:
    end=len(t)-1 if horizon is None else min(len(t)-1,i+max(1,round(horizon/.004)))
    p=d['position'][i].copy();v=d['velocity'][i].copy();q=d['attitude'][i].copy();w=d['omega'][i].copy()
    for j in range(i+1,end+1):
     u=rot[j-1] if name=='M2' else cmd[max(0,j-2)]
     p,v,q,w,a=plant(p,v,q,w,u,mod)
     if not np.all(np.isfinite(np.r_[p,v,q,w])) or np.linalg.norm(p)>1e3:break
     errors.append([np.linalg.norm(p-d['position'][j]),np.linalg.norm(v-d['velocity'][j])]);ang.append(float(so3(q[None,:],d['attitude'][j][None,:])[0]));used+=1
    if horizon is None:break
   e=np.array(errors);windows[str(horizon)]={'rows':used,'p_rmse_m':float(np.sqrt(np.mean(e[:,0]**2))) if used else None,'v_rmse_m_s':float(np.sqrt(np.mean(e[:,1]**2))) if used else None,'SO3_rmse_deg':float(np.sqrt(np.mean(np.array(ang)**2))) if used else None}
  report[name]=windows
 return report

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--formal',type=Path,required=True);a.add_argument('--output',type=Path,required=True);z=a.parse_args()
 models=json.loads((z.formal/'models/models.json').read_text());plan=json.loads(Path('config/p11.json').read_text());r={}
 for row in plan['rows']:
  case=z.formal/row['id']
  if (case/'packed/measurement.npz').exists():r[row['id']]=replay(case,models)
 write(z.output,{'schema':'p11-known-command-physics-1','cases':r,'interpretation':'actual future commands allowed ONLY here. Initial state reset per fixed short window; full rollout reset only once. LP observed states vs effective plant, no estimator hidden-state reconstruction; complete task right censoring retained. M0 is evaluated via original known-target lightweight interface separately, not assigned a motor interface.'})
