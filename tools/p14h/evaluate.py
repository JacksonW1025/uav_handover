"""Frozen-record forecasts with future hidden, then independent three-valued scoring."""
import sys,json,shutil,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p14h.record_packet import packet
from p12.score import score
from p12c.features import load
from p14h.score_response import angle,first

def main():
 target=Path(sys.argv[1]).resolve();review=Path(sys.argv[2]).resolve();out=register(sys.argv[3],'frozen H0/H1 actualpastinitial evaluation; no future inforecast, scoring side separate, initial reconstructed postflight');d,analysis=packet(target,review,out/'past-packet');row=json.load(open(target/'plan.json'));side=row['side'];tmp=Path(tempfile.mkdtemp(prefix='p14h-eval-'));inp=tmp/'input';inp.mkdir();shutil.copyfile(out/'past-packet/input.json',inp/'record.json')
 for src,name in [(R/'data/p13-20261026-freeze/models/policy.npz','policy.npz'),(R/'data/p14r-20261027/offline-build-v2/libop.bin','libop.bin'),(B/'cadence-recovery-v2/cadence.bin','cadence.bin')]:shutil.copyfile(src,inp/name)
 meta={'models':{}};pred=out/'score-input';pred.mkdir();obs=load(target/'run',analysis);rows=[];i=d['initial']
 for model in ['held','source-queue']:
  job=inp/(model+'.json');write(job,dict(case='record',model=model,side=side));dest=tmp/model;dest.mkdir();cmd=[shutil.which('bwrap'),'--ro-bind','/','/','--tmpfs',str(R/'data'),'--tmpfs',str(R/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(dest),str(dest),'--chdir',str(R),'/usr/bin/time','-f','%U %S %M','-o',str(dest/'inner-cpu.txt'),str(PY),str(R/'tools/p14h/response_trials.py'),'child',str(inp),str(job),str(dest/'result')];rr=run(cmd,out/model,cpu=30,wall=40,reserve_cpu=31,scope='isolated own-past-initial frozen prediction',extra_cpu_report=dest/'inner-cpu.txt');assert rr['rc']==0;shutil.copytree(dest/'result',out/model/'result');r=json.load(open(dest/'result/result.json'));z=np.load(dest/'result/trace.npz');tr=z['trace'];known=np.ones(len(tr),bool)
  if r['stop']:known &= tr[:,0]<r['stop']['profile_s']
  v=tr[known].copy();v[:,1:7]=v[:,42:48];np.savez_compressed(pred/(model+'.npz'),trace=v);meta['models'][model]={'stop':r['stop'],'height_modelled':True,'compute_s':rr['CPU_s']}
  ix=np.flatnonzero((obs['sample_us']>i['sample_us'])&(obs['sample_us']<=i['sample_us']+(len(tr)-1)*4000));k=((obs['sample_us'][ix]-i['sample_us'])//4000).astype(int);ix=ix[known[k]];k=k[known[k]];t=obs['t'][ix];errors={'LP':np.linalg.norm(tr[k,42:45]-obs['position'][ix],axis=1),'velocity':np.linalg.norm(tr[k,45:48]-obs['velocity'][ix],axis=1),'estimated_SO3_deg':angle(tr[k,48:52],obs['attitude'][ix]),'omega':np.linalg.norm(tr[k,39:42]-obs['omega'][ix],axis=1),'h':np.linalg.norm(tr[k,12:28]-obs['h_after'][ix],axis=1),'action':np.linalg.norm(tr[k,8:12]-obs['action'][ix],axis=1),'input':np.linalg.norm(z['inputs'][k]-obs['input'][ix],axis=1)};thresholds=dict(LP=.1,velocity=.15,estimated_SO3_deg=2.5,omega=.1,h=.1,action=.02,input=.05);windows=[]
  for gi,(a,b) in enumerate(d['plan']['windows_profile_s']):
   for width in [.064,.5,2.]:
    mask=(t>=b)&(t<=b+width);windows.append(dict(event=gi,window_s=width,observation_complete=bool(obs['t'][-1]>=b+width-.004),prediction_complete=bool(tr[known,0][-1]>=b+width-.004),RMSE={key:float(np.sqrt(np.mean(e[mask]**2))) if np.any(mask) else None for key,e in errors.items()}))
  rows.append(dict(model=model,first_errors={key:first(t,e,thresholds[key]) for key,e in errors.items()},full_common_prefix_RMSE={key:float(np.sqrt(np.mean(e**2))) for key,e in errors.items()},windows=windows,stop=r['stop']))
 write(pred/'prediction.json',meta);s=score(pred,analysis/'packed',analysis/'measured/measurement.json',out/'score');write(out/'summary.json',dict(id=target.name,models={m:v['risk'] for m,v in s['models'].items()},errors=rows,initial_packet_sha256=sha(out/'past-packet/input.json'),isolated_future_data=True,initial_role='postflight reconstruction of strictly pre-A information under pre-frozen recipe',not_full_EKF_restore=True));print('RECORD_EVALUATED',target.name)
if __name__=='__main__':main()
