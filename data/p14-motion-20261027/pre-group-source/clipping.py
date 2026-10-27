"""Actual axis/timing evidence; no causal percentages or new flights."""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import records,write,sha
from p12c.features import load
from p14.evaluate import stages
from p14_motion.analyze import episodes

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);cfg=json.load(open(ROOT/'config/p14-motion-offline.json'));rows=[]
 for r in records():
  id=r['id'];use=id in cfg['cases'] or r['group']=='formal' and ('-AB-' in id or '-REPAIR-' in id)
  if not use:continue
  d=load(r['target']/'run',r['analysis']);doc=json.load(open(r['packed']/'prediction-input.json'));end=min(doc['plan']['nominal_horizon_profile_s'],json.load(open(r['measured']))['observed_profile_end_s']);windows,ev=stages(d,doc['plan'],id,end);t=d['t'];c=np.cos(d['target_yaw']);s=np.sin(d['target_yaw']);F=np.zeros((len(t),3,3));F[:,0,0]=c;F[:,0,1]=s;F[:,1,0]=s;F[:,1,1]=-c;F[:,2,2]=-1
  pe=np.einsum('nij,nj->ni',F,d['position']-d['target_p']);ve=np.einsum('nij,nj->ni',F,d['velocity']-d['target_v']);m=(t>=0)&(t<=end);phases={}
  for name,w in windows.items():
   z=m&(t>=w[0])&(t<w[1]);v=ve[z];p=pe[z]
   phases[name]={'rows':int(z.sum()),'velocity_max_abs_axes':None if not z.any() else np.max(abs(v),axis=0).tolist(),'position_max_abs_axes':None if not z.any() else np.max(abs(p),axis=0).tolist(),'velocity_clip_rows_axes':np.sum(abs(v)>1,axis=0).tolist(),'position_clip_rows_axes':np.sum(abs(p)>.5,axis=0).tolist(),'velocity_any_clip_duration_s':float(np.sum(np.any(abs(v)>1,axis=1))*.004)}
  row={'id':id,'axes':['target_yaw_FLU_forward','target_yaw_FLU_left','target_yaw_FLU_up'],'phases':phases,'velocity_episodes':{str(k):episodes(t[m],(abs(ve[m,k])>1)) for k in range(3)},'position_episodes':{str(k):episodes(t[m],abs(pe[m,k])>.5) for k in range(3)},'action_clip_episodes':{str(k):episodes(t[m],abs(d['raw_reconstructed'][m,k])>1) for k in range(4)},'events':ev,'source_sync_sha256':sha(r['analysis']/'observation/synchronized.npz'),'interpretation':'logged pre-clip target-frame errors; correlated prior state/cache and treatment differences retained; not proof clipping is unique cause or additive neural-memory contribution'}
  write(out/id/'clipping.json',row);rows.append(row)
 write(out/'summary.json',{'rows':rows,'new_SITL':0,'additional_models':0,'repairs_are_old_actual_evidence_only':True})
if __name__=='__main__':main()
