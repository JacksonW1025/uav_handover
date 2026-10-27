import sys,json,time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write
from p12c.features import load
from p14_motion.core import Ctl,physical
from p14r.delivery import Delivery,Word
from p13.physics import read,BODY,ROTOR,rot
from p13.physical_model import S,B
from p12.execution import step as motor
from p14_motion.analyze import angles
from p14.evaluate import stats,crossing
out=Path(sys.argv[1]);out.mkdir();P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));rows=[]
write(out/'before-compute.json',{'cases':['d02','d03','d04','d05','d06'],'contrasts':'actual cache vs held-fusion OP cache; nominal persistent delivery vs actual future read word, carried NN/history throughout; command-open source physics initialized once atA-pre','future_data':'all controlled diagnostics, not autonomous scoring or additive causal attribution','metrics':'protocol-v1 errors and.5s/2s/A-resume/B-pre absolute windows unchanged','SITL':0})
for n in ['d02','d03','d04','d05','d06']:
 base=R/'data/p14r-20261027';run=next((base/'runs').glob('p14r-'+n+'-*'));v='source-inputs-v4' if n in ['d05','d06'] else 'source-inputs-v3';doc=json.load(open(base/v/n/'input.json'));i=doc['initial'];d=load(run/'run',run/'analysis-v1');ii=np.flatnonzero(d['sample_us']>i['sample_us']);approx=np.load(base/'A-input-contrasts-v3'/n/'imu0-fusion0-cache0.npz');amap={float(t):r for t,r in zip(approx['t'],approx['values'])};variants=[]
 for actual_cache in [False,True]:
  for actual_delivery in [False,True]:
   ctl=Ctl(i,doc['plan']);delivery=Delivery(doc,Word());a=[];h=[];times=[]
   for k,j in enumerate(ii,1):
    if float(d['t'][j]) not in amap:continue
    value=np.r_[d['position'][j],d['velocity'][j],d['attitude'][j],d['omega'][j]] if actual_cache else amap[float(d['t'][j])];lp,lv,q,w=value[:3],value[3:6],value[6:10],value[10:13]
    if actual_delivery:message=(d['external_p'][j],d['external_v'][j],float(d['external_yaw'][j])) if d['read_valid'][j] else None;native=int(d['native_us'][j]);sample=int(d['sample_us'][j])
    else:message=delivery.step(i['profile_s']+k*.004);native=i['native_us']+4000*k;sample=i['sample_us']+4000*k
    action,info=ctl.step(native,sample,lp,lv,q,w,message,P);a.append(np.linalg.norm(action-d['action'][j]));h.append(np.linalg.norm(ctl.h-d['h_after'][j]));times.append(float(d['t'][j]))
   a,h,times=map(np.array,[a,h,times]);variants.append({'actual_future_cache':actual_cache,'actual_future_read_native_word':actual_delivery,'action_error':stats(a),'h_error':stats(h),'action_first_over_.1':crossing(times,a,.1),'h_first_over_.5':crossing(times,h,.5),'first2s_action':stats(a[times<=i['profile_s']+2]),'body_role':'actual future physical/cache supplied when requested; actions do not drive actual body. No autonomous interpretation.'})
 body,_=read(run/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');body=body[(body['phase']==1)&(body['valid']==63)];body=body[(body['sim_ns']//1000>i['physical_sample_us'])];rotors=[read(run/f'run/gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1')[0] for k in range(4)];commands=[]
 for r in rotors:
  ix=np.searchsorted(r['step'],body['step']);assert np.array_equal(r['step'][ix],body['step']);commands.append(r['command'][ix])
 commands=np.array(commands).T;p,v,q,w,phi,f=[np.array(i[k]) for k in ['physical_COM_p','physical_COM_v','physical_q','physical_omega','rotor_phase','rotor_filter']];errors=[];T=[];stop=None
 for k,z in enumerate(body):
  fn=motor(f,commands[k],.004);p,v,q,w=physical(p,v,q,w,f,fn,phi);f=fn;Q=S@rot(z['base_q'][None,:])[0]@B;realq=Rotation.from_matrix(Q).as_quat()[[3,0,1,2]];t=i['profile_s']+(int(z['sim_ns']//1000)-i['sample_us'])*1e-6;T.append(t);err=np.r_[np.linalg.norm(p-S@z['com_p']),np.linalg.norm(v-S@z['com_v']),angles(q[None,:],realq[None,:])[0],np.linalg.norm(w-Q.T@S@z['base_omega'])];errors.append(err)
  if not np.isfinite(err).all() or np.linalg.norm(v)>8 or max(abs(w))>8:stop={'profile_s':t,'reason':'physical working domain'};break
 E=np.array(errors);T=np.array(T);measurement=json.load(open(run/'analysis-v1/measured/measurement.json'));scored_end=min(doc['plan'].get('nominal_horizon_profile_s',doc['plan']['horizon_profile_s']),measurement['observed_profile_end_s']);scoremask=T<=scored_end;open_result={'rows':len(T),'stop':stop,'first':{key:crossing(T,E[:,j],L) for j,(key,L) in enumerate([('p',.1),('v',.15),('SO3',2.5),('w',.1)])},'whole_shared_task_prefix':{key:stats(E[scoremask,j]) for j,key in enumerate(['p','v','SO3','w'])},'scored_end_profile_s':scored_end,'complete_observed_task':not measurement['censored'],'first2s':{key:stats(E[T<=i['profile_s']+2,j]) for j,key in enumerate(['p','v','SO3','w'])},'future_input':'actual consumed command only; physical/filter/rotor state initialized once, never reset','timing':'known future physical step identity for scoring only; dynamics uses4ms'};row={'id':n,'controller_contrasts':variants,'known_command_from_Apre':open_result};write(out/n/'result.json',row);rows.append(row);print('DIAG',n,flush=True)
write(out/'summary.json',rows)
