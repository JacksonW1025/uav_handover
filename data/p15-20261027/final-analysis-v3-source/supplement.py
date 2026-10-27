"""Final immutable aggregation. Never launch physical work or fit parameters."""
import sys,json,collections,math
from pathlib import Path
import numpy as np
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p15.common import B,write,sha

def crossing(t,v,limit):
 ix=np.flatnonzero(np.asarray(v)>limit)
 if not len(ix):return None
 i=int(ix[0]);return [float(t[max(0,i-1)]),float(t[i])]

def candidate_prediction(selection,candidate):
 return next(r['prediction'] for r in selection['rows'] if r['candidate']['id']==candidate['id'])

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
 rows=json.load(open(B/'delivery-v2/physical-component-v1/all-starts.json'))
 search=[r for r in rows if r['budget_class']=='search'];events=[];maps=[];panels=[]
 for r in rows:
  if r['budget_class']=='development':continue
  rid=r['id'];p=B/'runs'/rid/'run';s=json.load(open(p/'p15-selection.json'));inp=json.load(open(p/'p15-selection-input.json'));ctx=inp['context'];c=s['executed_candidate'];Btime=ctx['A_start']+ctx['A_duration']+c['G'];br=Btime+c['D']
  evpath=B/'evaluation'/rid/'summary.json'
  if not evpath.exists():evpath=B/'evaluation-LP-only-v2'/rid/'summary.json'
  ev=json.load(open(evpath));fz=evpath.parent/'forecast.npz';z=np.load(fz)['trace']
  aev=ev['actual_events'];captures=[e for e in aev if e['kind']=='capture' and Btime<=e['profile_s']<=br+.25];resumes=[e for e in aev if e['kind']=='resume' and Btime<=e['profile_s']<=br+.25];res=r['result'];failuretimes=[x[1] for x in res['first_crossing'].values() if x is not None]
  events.append(dict(id=rid,stage=r['budget_class'],method=r['method'],block=r['block'],family=r['family'],information=r['information'],candidate=c,planned_B=Btime,planned_B_end=br,B_plan_reached=res['B_plan_reached'],B_capture='OBSERVED' if captures else 'NOT_REACHED_OR_NOT_CAPTURED',B_capture_witnesses=captures,B_resume_witnesses=resumes,prefix_failed_before_B=res['prefix_failed_before_B'],first_failure_s=min(failuretimes) if failuretimes else None,actual_first_crossing_brackets=res['first_crossing'],prediction_first_crossing_brackets=dict(tilt=crossing(z[:,0],z[:,4],45),height=crossing(z[:,0],z[:,2],1)),actual_risks=res['risks'],censored=res['censored'],peak_tilt=res['peak_tilt_deg'],LP_D=res['LP_D_m'],full_time_errors=ev['full_time_errors'],windows=ev['windows']))
  if r['budget_class']=='map':
   act=res['Bpre'];up=candidate_prediction(s,c);base=candidate_prediction(s['no_update_ablation'],c);a=up.get('Bpre');bb=base.get('Bpre');comp={}
   for name,key in [('L','LP_L_m'),('W','LP_W_m_s')]:
    comp[name]=dict(actual=act[key],updated=a[name],no_update=bb[name],updated_abs_error=abs(a[name]-act[key]),no_update_abs_error=abs(bb[name]-act[key]))
   maps.append(dict(id=rid,selection_changed=s['update_changed_choice'],candidate=c,matched_executed_candidate=True,Bpre_comparison=comp,updated_score=up['score'],no_update_score=base['score'],scope='same executed candidate, old first-at/after-B model field vs strict-before actual field; grid mismatch explicitly retained, extra-metrics has strict both-side before-B. No causal error attribution.',role='same-record adaptation' if (p/'p15-local-update.json').exists() else 'independent newseed with prior finished update'))
  extra=json.load(open(B/'extra-metrics'/rid/'result.json'))
  panels.append(dict(id=rid,strict_Bpre=extra['Bpre'],clip=extra['actual_clip']))
 pairs=[]
 for block in [1,2]:
  for trial in [1,2,3,4]:
   a=next(r for r in search if r['method']=='M2' and r['block']==block and f'-t{trial}-' in r['id']);b=next(r for r in search if r['method']=='M3' and r['block']==block and f'-t{trial}-' in r['id']);ar=a['result'];br=b['result'];pairs.append(dict(block=block,trial=trial,family=a['family'],information=a['information'],M2_id=a['id'],M3_id=b['id'],M2_candidate=a['selection_summary']['selected'],M3_candidate=b['selection_summary']['selected'],candidate_changed=a['selection_summary']['selected']!=b['selection_summary']['selected'],M2_risk=ar['risks'],M3_risk=br['risks'],tilt_M3_minus_M2=br['peak_tilt_deg']-ar['peak_tilt_deg'],LP_D_M3_minus_M2=br['LP_D_m']-ar['LP_D_m'],strict_sameinitial=False,scope='policy-pair descriptive contrasts, actual initial differences retained in immutable input and all-prefix states; 2 seedblocks only'))
 # Measured direct costs until first confirmed failure: chronology by actual method starts.
 # setup is declared separately, not charge later map to early discovery.
 direct=[]
 for m in ['M0','M1','M2','M3']:
  rr=[r for r in search if r['method']==m];cpu=wall=0
  for i,r in enumerate(rr):
   p=B/'runs'/r['id'];ex=r['execution'];cpu+=ex['CPU_s'];wall+=ex['wall_s']
   for q in [p/'manager-cost.json',p/'analysis-process/cost.json',p/'qualified-task-prefix-process-v2/cost.json']:
    if q.exists():d=json.load(open(q));cpu+=d['CPU_s'];wall+=d.get('wall_s',0)
   if r['result']['risks']['task']=='FAIL':
    direct.append(dict(method=m,start=i+1,id=r['id'],measured_direct_confirmation_CPU_s=cpu,physical_and_analysis_wall_lower_s=wall,scope='through failure confirmation only; excludes later evaluation/maps/setup, therefore not full-method cost. Full allocated cost in delivery-v2. Missing manager wall/tails UNKNOWN.'))
    break
 write(out/'event-reach-crossings.json',events);write(out/'strict-Bpre-and-clips.json',panels);write(out/'matched-policy-contrasts.json',pairs);write(out/'map-update-effects.json',maps);write(out/'first-failure-direct-cost.json',direct)
 all32=[x for x in events if x['stage']=='search'];matrix={}
 for m in ['M0','M1','M2','M3']:
  rr=[x for x in all32 if x['method']==m];matrix[m]=dict(B_capture_observed=sum(x['B_capture']=='OBSERVED' for x in rr),B_resume_observed=sum(bool(x['B_resume_witnesses']) for x in rr),tilt_failure=sum(x['actual_risks']['tilt']=='FAIL' for x in rr),height_failure=sum(x['actual_risks']['height']=='FAIL' for x in rr),height_unknown=sum(x['actual_risks']['height']=='UNKNOWN' for x in rr),censored=sum(x['censored'] for x in rr),prefix_failure=sum(x['prefix_failed_before_B'] for x in rr))
 write(out/'mechanism-coverage.json',matrix)
 # Only descriptive reorders of executed fixed labels; no claims about unseen pool or prospective sequences.
 rng=np.random.default_rng(152710999);perm={}
 for m in ['M0','M1','M2','M3']:
  labels=np.array([r['result']['risks']['task']=='FAIL' for r in search if r['method']==m]);first=[int(np.flatnonzero(rng.permutation(labels))[0])+1 for _ in range(1000)];perm[m]=dict(first_failure_start_quantiles=np.quantile(first,[.05,.5,.95]).tolist(),N=1000,seed=152710999,exposure='post-execution diagnostic seed registered in v3 source, NOT presealed independent random validation',scope='executed labels only, no unexecuted candidate labels')
 write(out/'executed-reordering-diagnostic.json',perm)
 machine=json.load(open(B/'delivery-v2/machine.json'));machine.update(schema='P15-final-v3',strict_comparison='M1/M2/M3 same conditional pool, M0 vs others bundled prior/support contrast only',mechanism=matrix,map_selection_changes=sum(x['selection_changed'] for x in maps),theory_search_gain='NOT_ESTABLISHED under same-pool M2/M3; costs/height misses limit use',map_choice_benefit='NOT_ESTABLISHED 0/4 changed',model_point_reuse='6/6 same-clock composition, CPU1.4075 vs .5681, no physical-snapshot saving',safety='NO_SAFE_SKIP, A4 NOT_PROVEN_EXCLUDED',new_SITL=42,remaining_not_used=dict(development=2,search=0,map=4),old_failures_preserved=True)
 write(out/'machine.json',machine)
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 fig,ax=plt.subplots(1,2,figsize=(10,4))
 for k,(key,title) in enumerate([('L','B-pre LP loss error [m]'),('W','B-pre LP down-speed error [m/s]')]):
  xx=np.arange(4);ax[k].bar(xx-.18,[x['Bpre_comparison'][key]['no_update_abs_error'] for x in maps],.36,label='no update');ax[k].bar(xx+.18,[x['Bpre_comparison'][key]['updated_abs_error'] for x in maps],.36,label='update');ax[k].set(xticks=xx,xticklabels=[x['id'].split('-')[1] for x in maps],ylabel=title);ax[k].legend()
 fig.tight_layout();fig.savefig(out/'map-update-errors.png',dpi=160);plt.close(fig)
 write(out/'source-inputs.json',dict(source_sha256=sha(__file__),v2_machine=sha(B/'delivery-v2/machine.json'),N_search=32,N_map=4,all_inputs_saved_during_decision=True,actual_future='scoring only',parameters_refit=False))
 print('SUPPLEMENT COMPLETE',matrix,'changed',sum(x['candidate_changed'] for x in pairs));print('MAP',maps)
if __name__=='__main__':main()
