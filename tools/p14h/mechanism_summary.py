"""Scoring-only paired differences, preserving actual initial differences."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p12c.features import load
from p14h.score_response import angle

def main():
 out=register(sys.argv[1],'two seed-block differences and own-initial errors; all four used, no equal-state causal claim');scores=json.load(open(B/'response-score-v1/response-errors.json'))['rows'];jobs=json.load(open(B/'response-trials-v1/jobs.json'));records={};pairs=[]
 for n in range(1,5):
  target=next((B/'runs').glob(f'p14h-d{n:02d}-*'));info=json.load(open(target/('information-v2.json' if (target/'information-v2.json').exists() else 'information.json')));analysis=R/info['source_analysis'] if 'source_analysis' in info else target/'analysis-v1';obs=load(target/'run',analysis);doc=json.load(open(B/f'cadence-recovery-v2/d{n:02d}/input.json'));a,b=doc['plan']['windows_profile_s'][0];ix=np.flatnonzero((~obs['stale'].astype(bool))&np.r_[False,obs['stale'][:-1].astype(bool)]&(obs['t']>=b));j=int(ix[0]);m=(obs['t']>=b)&(obs['t']<=b+.5);records[n]={'action':obs['action'][j], 'tilt_half':float(max(obs['tilt'][m])) if 'tilt' in obs else float(max([__import__('p11.models',fromlist=['tilt']).tilt(q) for q in obs['attitude'][m]])),'LP_half_D':float(max(obs['position'][m,2]-doc['initial']['LP_H0_NED_z'])),'doc':doc,'side':json.load(open(target/'plan.json'))['side']}
  c=np.cos(obs['target_yaw']);s=np.sin(obs['target_yaw']);raw=[]
  for vals in [obs['position']-obs['target_p'],obs['velocity']-obs['target_v']]:raw.append(np.c_[c*vals[:,0]+s*vals[:,1],s*vals[:,0]-c*vals[:,1],-vals[:,2]])
  raw=np.c_[*raw];limits=np.array([.5]*3+[1.]*3);clip=np.abs(raw)>limits;reconstructed=np.clip(raw,-limits,limits);assert np.max(abs(reconstructed-np.c_[obs['input'][:,:3],obs['input'][:,12:15]]))<2e-5
  def intervals(mask):
   starts=np.flatnonzero(mask&np.r_[True,~mask[:-1]]);ends=np.flatnonzero(mask&np.r_[~mask[1:],True]);return [[float(obs['t'][i]),float(obs['t'][j]+.004)] for i,j in zip(starts,ends)]
  write(out/f'd{n:02d}-clip.json',{'supersedes':'paired-v1 clip arrays wrongly treated rotation rows as velocity; original kept, no forecast/score changed','axes':[dict(axis=k,policy_input_index=([0,1,2,12,13,14][k]),threshold=float(limits[k]),seconds=float(np.sum(clip[:,k])*.004),intervals=intervals(clip[:,k])) for k in range(6)],'scope':'raw target-yaw-frame p/v errors from recorded actual cache and target; diagnostic only, no isolated causal attribution'})
 for seed,be,af in [(142710201,1,3),(142710202,4,2)]:
  x,y=records[be],records[af];i,j=x['doc']['initial'],y['doc']['initial'];raw=np.r_[y['action']-x['action'],y['tilt_half']-x['tilt_half'],y['LP_half_D']-x['LP_half_D']];row={'seed':seed,'before':be,'after':af,'observed_delta_after_minus_before':raw.tolist(),'coordinates':['action0','action1','action2','action3','tilt_peak_0.5s_deg','LP_D_0.5s_m'],'initial_differences':{'p_L2':float(np.linalg.norm(np.array(j['position'])-i['position'])),'v_L2':float(np.linalg.norm(np.array(j['velocity'])-i['velocity'])),'h_L2':float(np.linalg.norm(np.array(j['h'])-i['h'])),'SO3_deg':float(angle([j['attitude']],[i['attitude']])[0]),'LP_age_before_us':i['sample_us']-i['LP_cache_sample_us'],'LP_age_after_us':j['sample_us']-j['LP_cache_sample_us']},'models':{}}
  for model in ['held','error-prototype','source-queue']:
   def value(case,side):
    rr=next(r for r in scores if r['case']==f'd{case:02d}' and r['model']==model and r['side']==side);z=next(z for z,k in enumerate(jobs) if k['case']==f'd{case:02d}' and k['model']==model and k['side']==side);tr=np.load(B/f'response-trials-v1/{z:03d}/result/trace.npz')['trace'];end=records[case]['doc']['plan']['windows_profile_s'][0][1];m=(tr[:,0]>=end)&(tr[:,0]<=end+.5);return np.r_[rr['predicted_first_action'],max(tr[m,7]),max(tr[m,44]-records[case]['doc']['initial']['LP_H0_NED_z'])]
   actual_initial_delta=value(af,'AFTER')-value(be,'BEFORE');within=[value(c,'AFTER')-value(c,'BEFORE') for c in [be,af]];row['models'][model]={'different_actual_initial_delta':actual_initial_delta.tolist(),'response_error':(actual_initial_delta-raw).tolist(),'within_initial_conditional_deltas':[v.tolist() for v in within],'response_isolation':'raw paired change includes initial differences; within-initial counterfactual is model-only'}
  pairs.append(row)
 write(out/'paired.json',{'pairs':pairs,'independent_seed_blocks':2,'mechanism_runs':4,'future_used_only_for_scoring':True,'same_seed_not_same_initial':True});print('PAIRED',[(r['seed'],r['observed_delta_after_minus_before']) for r in pairs])
if __name__=='__main__':main()
