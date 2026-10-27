"""Eight frozen-model opposite-side point diagnostics, no new candidate/fit.
No actual opposite-side label is invented for any specific initial state.
"""
import sys,json,shutil,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from p14h.common import *

def main():
 out=register(sys.argv[1],'H2 finite opposite-cell response at each of eight actual new initial packets. Model fixed before independent flights; calculation post-exposure is diagnostic, not new prospective samples',maximum_workers=8,CPU_cap=240,actual_initials_preserved=True,no_outcome_refitting=True);tmp=Path(tempfile.mkdtemp(prefix='p14h-cf-'));inp=tmp/'inputs';inp.mkdir();plan=json.load(open(B/'independent-plan-v2/plan.json'));jobs=[]
 for n,row in enumerate(plan['rows']):
  if not any(m in row['methods'] for m in ['branch','continuous']):continue
  name=f'e{n+1:02d}';shutil.copyfile(B/f'evaluation-{name}-v1/past-packet/input.json',inp/(name+'.json'));jobs.append(dict(case=name,model='source-queue',side='AFTER' if row['side']=='BEFORE' else 'BEFORE',actual_side=row['side'],seed=row['seed']))
 for src,name in [(R/'data/p13-20261026-freeze/models/policy.npz','policy.npz'),(R/'data/p14r-20261027/offline-build-v2/libop.bin','libop.bin'),(B/'cadence-recovery-v2/cadence.bin','cadence.bin')]:shutil.copyfile(src,inp/name)
 write(out/'jobs.json',jobs);rows=[]
 for n,j in enumerate(jobs):
  jf=inp/f'job{n}.json';write(jf,j);dest=tmp/f'out{n}';dest.mkdir();cmd=[shutil.which('bwrap'),'--ro-bind','/','/','--tmpfs',str(R/'data'),'--tmpfs',str(R/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(dest),str(dest),'--chdir',str(R),'/usr/bin/time','-f','%U %S %M','-o',str(dest/'inner-cpu.txt'),str(PY),str(R/'tools/p14h/response_trials.py'),'child',str(inp),str(jf),str(dest/'result')];r=run(cmd,out/f'{n:03d}',cpu=30,wall=40,reserve_cpu=31,extra_cpu_report=dest/'inner-cpu.txt',scope='isolated retrospective opposite-cell conditional diagnostic, no actual label');assert r['rc']==0;shutil.copytree(dest/'result',out/f'{n:03d}/result');d=json.load(open(inp/(j['case']+'.json')));end=d['plan']['windows_profile_s'][0][1]
  def value(folder):
   z=np.load(folder/'trace.npz')['trace'];ix=np.flatnonzero((~z[:,34].astype(bool))&np.r_[False,z[:-1,34].astype(bool)]&(z[:,0]>=end));k=int(ix[0]);mask=(z[:,0]>=end)&(z[:,0]<=end+.5);return np.r_[z[k,8:12],max(z[mask,7]),max(z[mask,44]-d['initial']['LP_H0_NED_z'])]
  own=value(B/f'evaluation-{j["case"]}-v1/source-queue/result');opp=value(dest/'result');delta=opp-own if j['side']=='AFTER' else own-opp;rows.append(dict(**j,model_within_same_initial_after_minus_before=delta.tolist(),coordinates=['action4','tilt_peak_half_deg','LP_D_half_m'],conditional_only=True,no_real_same_initial_counterfactual=True))
 write(out/'result.json',dict(rows=rows,source_model_unchanged=True,role='post-exposure diagnostic; independent model scores unchanged',future_data_hidden=True));print('COUNTERFACTUAL_DIAGNOSTIC',len(rows))
if __name__=='__main__':main()
