"""Frozen finite branch-sensitive event search. Forecast workers see past packets only.
The continuous baseline uses valid same-branch finite derivatives, while the
branch method keeps the two legal release cells and their finite jump.
Neither method receives a future flight label or future word.
"""
import sys,json,copy,shutil,tempfile,random,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p14h.predict_past import planned_cell

def apply_parameters(doc,D,G,side):
 d=copy.deepcopy(doc);a=d['plan']['full_source_windows_profile_s'][0][0];w=[[a,a+D],[a+D+G,a+D+G+.36]];d['plan']['windows_profile_s']=copy.deepcopy(w);d['plan']['full_source_windows_profile_s']=copy.deepcopy(w)
 return planned_cell(d,side)

def candidate_id(D,G,side):return f'D{D:.3f}-G{G:.3f}-{side}'

def worker(inp,job,out):
 from p14h.model import forecast
 from p14h.delivery import Word
 inp=Path(inp);out=Path(out);out.mkdir();d=apply_parameters(json.load(open(inp/(job['case']+'.json'))),job['D'],job['G'],job['side']);r=forecast(d,{},dict(np.load(inp/'policy.npz')),word=Word(),observer_library=inp/'libop.bin');tr=r['trace'];s=r['states'];a,b=d['plan']['windows_profile_s'][0];bs,be=d['plan']['windows_profile_s'][1];m=(tr[:,0]>=a)&(tr[:,0]<=be+2.);i=d['initial'];z=np.flatnonzero(m);L=tr[z,44]-i['LP_H0_NED_z'];C=s[z,2]-i['physical_H0_NED_z'];peak=float(max(tr[z,7]));ld=float(max(L));cd=float(max(C));resume=[k+1 for k,x in enumerate(r['branches']) if x['resume'] and b<=tr[k+1,0]<=b+.1];j=resume[0] if resume else z[0];pre=np.flatnonzero(tr[:,0]<bs);k=int(pre[-1]);complete=tr[-1,0]>=d['plan']['horizon_profile_s']-.004 and r['stop'] is None
 # A fixed nominal objective, separately published physical outputs. It is
 # search guidance, never an outer-set safety or inevitable-danger verdict.
 score=max(peak/45.,ld,cd);write(out/'result.json',dict(job=job,objective=score,peak_tilt_deg=peak,LP_D_m=ld,COM_D_m=cd,Bpre_L=float(s[k,2]-i['physical_H0_NED_z']),Bpre_W=float(s[k,5]),first_action=tr[j,8:12].tolist(),first_resume_profile_s=float(tr[j,0]),stop=r['stop'],complete=bool(complete),classification='CONDITIONAL_NOMINAL_ONLY',model_inputs='past initial, predeclared task/parameters and nominal source schedule; no actual future data',predicted_cell=d['plan']['p14h_cells'],prefix_branch_signature=[(x['read'],x['refresh'],x['commit'],x['capture'],x['resume']) for x in r['branches']],future_observer_coverage='UNKNOWN auxiliary EKF states/aiding corrections and producer scheduling'))

def prepare(out):
 out=register(out,'H3 finite equal-domain three-rule comparison, registered before ranking. All diagnostic cases exposed, future independent tests not run',CPU_cap=2400,per_worker_CPU=30,per_worker_wall=40,memory_GiB=24)
 pool=[dict(id=candidate_id(D,G,side),D=D,G=G,side=side) for D in [.34,.36,.38] for G in [.65,.85,1.05] for side in ['BEFORE','AFTER']]
 rules={'pool':pool,'seeds':[142710301,142710302,142710303,142710304],'methods':['random','continuous','branch'],'execution_budget_per_method':4,'shared_candidate_same_seed':'one physical start, all method credits explicitly dependent; unspent starts not replaced','initial_ensemble':['d01','d02','d03','d04'],'initial_coverage':'four observed development points, no convex-hull or full initial-set guarantee','origin':{'D':.36,'G':.85},'derivative_steps':{'D':.0005,'G':.0005},'trust_radii':{'D':.02,'G':.2},'derivative_guard':'both perturbations must have identical complete source branch signature, else derivative unavailable and axis fixed','validation_steps':{'D':.01,'G':.1},'linearization_error_rule':'report relative prediction error at fixed forward holdout, never tune/rerank after physical validation','objective':'max(peak tilt/45, all-prefix LP D/1m, all-prefix COM D/1m) over A through B-resume+2s; publish components, conditional center only','ensemble_aggregation':'arithmetic mean of four source-initial conditional objectives, every initial retained','random':'Random(seed) uniform pool candidate; seed is block identity','continuous':'choose anchor side using Random(seed+1); one same-branch gradient step to registered pool corner maximizing linear objective within trust rectangle; invalid derivative axis fixed at origin','branch':'same finite gradient construction separately in both release cells; maximize piecewise objective including cell intercept jump','ties':'objective rounded 1e-10, lexicographic candidate id','order':'Random(seed+2) shuffle method order within seed; merge duplicate candidate/seed at first occurrence','all_prior_exposed':True,'independent_model_parameters_frozen_after_development':True,'safety':'original task/safety thresholds and policy unchanged; scientific failure retained','failure_categories':'physical/identity/time/critical observation fault pauses dependents; pure analysis fixes versioned; resource loss preserves prefix; no replacements','all_costs':'all forecasts, gradients, validation pool, theory, development, errors, shared anchors, SITL and review separately charged; 2400 search CPU cap includes all jobs'}
 write(out/'rules.json',rules);inp=out/'inputs';inp.mkdir()
 for n in range(1,5):shutil.copyfile(B/f'cadence-recovery-v2/d{n:02d}/input.json',inp/f'd{n:02d}.json')
 for src,name in [(R/'data/p13-20261026-freeze/models/policy.npz','policy.npz'),(R/'data/p14r-20261027/offline-build-v2/libop.bin','libop.bin'),(B/'cadence-recovery-v2/cadence.bin','cadence.bin')]:shutil.copyfile(src,inp/name)
 jobs=[]
 def add(D,G,side,role):
  for n in range(1,5):
   if not any(j['D']==D and j['G']==G and j['side']==side and j['case']==f'd{n:02d}' for j in jobs):jobs.append(dict(case=f'd{n:02d}',D=D,G=G,side=side,role=role))
 for p in pool:add(p['D'],p['G'],p['side'],'fixed candidate-pool forward validation; not used to refit gradient or rerank')
 for side in ['BEFORE','AFTER']:
  for axis,step in [('D',.0005),('G',.0005),('D',.01),('G',.1)]:
   for sign in [-1,1]:add(.36+sign*step if axis=='D' else .36,.85+sign*step if axis=='G' else .85,side,'same-branch derivative' if step==.0005 else 'held-out finite forward-step check')
 write(out/'jobs.json',jobs);write(out/'input-hashes.json',{p.name:sha(p) for p in inp.iterdir()});return out

def calculate(out):
 out=Path(out).resolve();jobs=json.load(open(out/'jobs.json'));tmp=Path(tempfile.mkdtemp(prefix='p14h-select-'));inp=tmp/'inputs';shutil.copytree(out/'inputs',inp);rows=[];used=json.load(open(out/'reuse.json'))['CPU_allowance'] if (out/'reuse.json').exists() else 0
 for n,job in enumerate(jobs):
  if (out/f'{n:03d}/result/result.json').exists():continue
  if used+30>2400:write(out/'unstarted.json',{'jobs':jobs[n:],'reason':'search CPU cap'});break
  jf=inp/f'job-{n:03d}.json';write(jf,job);dest=tmp/f'output-{n:03d}';dest.mkdir();cmd=[shutil.which('bwrap'),'--ro-bind','/','/','--tmpfs',str(R/'data'),'--tmpfs',str(R/'export'),'--unshare-net','--unshare-pid','--proc','/proc','--bind',str(dest),str(dest),'--chdir',str(R),'/usr/bin/time','-f','%U %S %M','-o',str(dest/'inner-cpu.txt'),str(PY),str(Path(__file__).resolve()),'worker',str(inp),str(jf),str(dest/'result')];rr=run(cmd,out/f'{n:03d}',cpu=30,wall=40,reserve_cpu=31,scope='H3 isolated frozen-pool forecast, inner namespace CPU separately waited',extra_cpu_report=dest/'inner-cpu.txt');used+=rr['CPU_s'];rows.append(rr)
  if rr['rc']==0:shutil.copytree(dest/'result',out/f'{n:03d}/result')
  print('SELECT_FORECAST',n,rr['rc'],round(used,2),flush=True)
  if rr['rc']!=0:
   write(out/'unstarted.json',{'jobs':jobs[n+1:],'reason':'worker implementation/infrastructure failure; isolate and version repair, no silent substitute'});break
 write(out/'isolation.json',{'tmp':str(tmp),'data_and_export_hidden':True,'input_hashes':json.load(open(out/'input-hashes.json')),'no_future_labels_in_selector':True});write(out/'execution.json',{'rows':rows,'CPU_s':used,'jobs':len(jobs),'computed':len(rows)})

def select(out):
 out=Path(out).resolve();rules=json.load(open(out/'rules.json'));jobs=json.load(open(out/'jobs.json'));allrows=[]
 for n,j in enumerate(jobs):
  p=out/f'{n:03d}/result/result.json';assert p.exists(),'missing forecast isolate no invented score';allrows.append(json.load(open(p)))
 def get(D,G,side,case):return next(r for r in allrows if abs(r['job']['D']-D)<1e-10 and abs(r['job']['G']-G)<1e-10 and r['job']['side']==side and r['job']['case']==case)
 gradients={};validation=[]
 for side in ['BEFORE','AFTER']:
  gs=[]
  for case in rules['initial_ensemble']:
   base=get(.36,.85,side,case);g={};valid={}
   for axis in ['D','G']:
    def at(delta):return get(.36+delta if axis=='D' else .36,.85+delta if axis=='G' else .85,side,case)
    m,p=at(-.0005),at(.0005);ok=m['prefix_branch_signature']==base['prefix_branch_signature']==p['prefix_branch_signature'];g[axis]=(p['objective']-m['objective'])/.001 if ok else 0.;valid[axis]=ok
    step=rules['validation_steps'][axis];target=at(step);estimate=base['objective']+g[axis]*step;validation.append(dict(side=side,case=case,axis=axis,valid_same_branch=ok,step=step,linear_estimate=estimate,forward_objective=target['objective'],absolute_error=abs(estimate-target['objective']),branches_at_validation_equal=target['prefix_branch_signature']==base['prefix_branch_signature']))
   gs.append(dict(case=case,base=base['objective'],gradient=g,valid=valid))
  gradients[side]=gs
 def rank(sides):
  scored=[]
  for p in rules['pool']:
   if p['side'] not in sides:continue
   gs=gradients[p['side']]
   # Axis frozen if any source-initial member has an invalid local cell.
   if any(not z['valid'][a] and abs(p[a]-rules['origin'][a])>1e-10 for a in ['D','G'] for z in gs):continue
   score=float(np.mean([z['base']+z['gradient']['D']*(p['D']-.36)+z['gradient']['G']*(p['G']-.85) for z in gs]));scored.append(dict(candidate=p,predicted_piecewise_objective=score))
  assert scored;return sorted(scored,key=lambda x:(-round(x['predicted_piecewise_objective'],10),x['candidate']['id']))
 rows=[]
 for seed in rules['seeds']:
  random_candidate=random.Random(seed).choice(rules['pool']);side=random.Random(seed+1).choice(['BEFORE','AFTER']);chosen={'random':random_candidate,'continuous':rank([side])[0]['candidate'],'branch':rank(['BEFORE','AFTER'])[0]['candidate']};methods=rules['methods'].copy();random.Random(seed+2).shuffle(methods)
  for method in methods:
   c=chosen[method];found=next((r for r in rows if r['seed']==seed and r['candidate']['id']==c['id']),None)
   if found:found['methods'].append(method);continue
   ensemble=[get(c['D'],c['G'],c['side'],case) for case in rules['initial_ensemble']];rows.append(dict(seed=seed,candidate=c,methods=[method],selection_input='frozen past four diagnostic initial packets + planned parameters only',nominal_predictions=[{k:v for k,v in x.items() if k not in ['prefix_branch_signature']} for x in ensemble],no_future_data_in_selection=True))
 write(out/'selection.json',{'rules_sha256':sha(out/'rules.json'),'gradients':gradients,'validation':validation,'rankings':{s:rank([s]) for s in ['BEFORE','AFTER']},'branch_ranking':rank(['BEFORE','AFTER']),'rows':rows,'unique_physical_starts':len(rows),'per_method_credit':4,'shared_execution_dependence_explicit':True,'new_results_not_seen':True});print('SELECTION_FROZEN',len(rows),[(r['seed'],r['candidate']['id'],r['methods']) for r in rows])

if __name__=='__main__':
 if sys.argv[1]=='worker':worker(sys.argv[2],json.load(open(sys.argv[3])),sys.argv[4])
 elif sys.argv[1]=='prepare':prepare(sys.argv[2])
 elif sys.argv[1]=='calculate':calculate(sys.argv[2])
 elif sys.argv[1]=='select':select(sys.argv[2])
