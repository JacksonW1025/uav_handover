"""Posthoc sampled checks of hypothetical A_body2 condition, not future bounds."""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p13.physics import read,BODY,ROTOR
from p9_model import write,sha
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);plan=json.load(open(R/'config/p13-formal.json'));rows=[]
for row in plan['rows']:
 if row['branch']!='REPAIR':continue
 tar=R/'data/p13-20261026-formal'/row['id'];event=json.load(open(R/'data/p13-20261026-formal-analysis-v3'/row['id']/'events/event-states.json'));b,_=read(tar/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');post=b[b['phase']==1];pre=b[b['phase']==0];sends=[json.loads(s) for s in (tar/'run/p11-sends.jsonl').read_text().splitlines()];epoch=round(next(v['stream_t0_monotonic_s'] for v in sends if v['stream_t0_monotonic_s'] is not None)*1e9);pt=(post['wall_ns'].astype(np.int64)-epoch)/1e9;originv=post['base_v']+np.cross(post['base_omega'],post['origin_p']-post['base_p']);inc=np.linalg.norm(np.diff(originv,axis=0)/(np.diff(post['sim_ns'])/1e9)[:,None],axis=1);force=np.zeros((len(pre),3));counts=np.zeros(len(pre),dtype=int)
 for k in range(4):
  z,_=read(tar/f'run/gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1');j=np.searchsorted(pre['step'],z['step']);force[j]+=z['thrust'][:,None]*z['axis']+z['drag'];counts[j]+=1
 ac=np.full_like(force,np.nan);good=(pre['valid']==63)&(pre['mass']>0)&(counts==4);ac[good]=force[good]/pre['mass'][good,None]+np.array([0,0,-9.8]);at=(pre['wall_ns'].astype(np.int64)-epoch)/1e9
 for e in event['events']:
  if e['status']!='CAPTURE_REACHED':continue
  lo=e['capture_profile_s'];hi=e.get('resume_profile_s',event['valid_end_s']);use=(pt[1:]>=lo)&(pt[1:]<hi);u=(at>=lo)&(at<hi);maximum=float(max(inc[use])) if use.any() else None;force_max=float(max(np.linalg.norm(ac[u],axis=1))) if u.any() else None;assert np.all(good[u]),'missing force or mass in hold';rows.append({'id':row['id'],'event':e['label'],'status':e.get('resume_status'),'hold_profile_s':[lo,hi],'direct_origin_velocity_increment_rate_max_m_s2':maximum,'source_reconstructed_COM_force_acceleration_norm_max_m_s2':force_max,'sampled_increment_projection_A2':'OUTSIDE' if maximum is not None and maximum>2 else 'NOT_REJECTED_AT_RECORDED_STEPS','A2_whole_actual_continuous_certified':False})
write(out/'projection.json',{'schema':'p13-hypothetical-repair-antecedent-projection-1','rows':rows,'source':'physical origin velocity from direct getter+geometry, difference over real simdt is a sampled increment diagnostic, NEVER called direct acceleration. COM force acceleration independently reconstructed from actual force-phase thrust/drag and sourcegravity/mass. No future input goes into forecasts.','scope':'checks an already explicitly hypothetical A_body2 example, not parameter fitting or exclusion. >2 sampled velocity increment rates reject using that simple discreteA2 box without extra jump/integration budgets; not a standalone continuous causal acceleration theorem.','new_SITL':0,'formal_case_model_changes':False,'source_sha256':sha(Path(__file__))});print('A2_PROJECTION',len(rows),sum(r['sampled_increment_projection_A2']=='OUTSIDE' for r in rows))
