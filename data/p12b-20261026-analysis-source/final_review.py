#!/usr/bin/env python3
"""Read-only synthesis of stopped P12b preparation; never launches SITL."""
import sys,json,hashlib,os
from pathlib import Path
from collections import Counter
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from preparation_acceptance import feat
from p11.models import tilt
P=R/'data/p12b-20261026-delivery';O=P/'reviewed';O.mkdir(exist_ok=False)
def write(n,d): (O/n).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
rows=json.load(open(R/'data/p12b-20261026-preparation/protocol.json'))['rows'][:2]+json.load(open(R/'data/p12b-20261026-preparation-v2/protocol.json'))['rows'];starts=[];scores=[];features={};tables={}
for row in rows:
 parent=R/('data/p12b-20261026-development-v2' if row['ordinal']>=3 else 'data/p12b-20261026-development')/row['id'];a=parent/'analysis';t=json.load(open(P/'event-tables'/row['id']/'event-states.json'));tables[row['ordinal']]=t
 m=json.load(open(a/'measured/measurement.json')) if (a/'measured/measurement.json').exists() else None
 starts.append({**{k:row[k] for k in ['id','ordinal','family','phase','branch','sim_seed','observe']},'run':str((parent/'run').relative_to(R)),'status':'STOP_CRITICAL_READ_CONTRACT' if row['ordinal']==2 else 'PREPARATION_COMPLETE','frozen_flight':t['frozen_outcome'],'task_outcome':t['task_outcome'],'whole':t['full_task_measurement'],'censored':t['censored'],'events':t['events'],'nominal_end_status':t['rows'][-1]['status'],'formal':False,'m':None})
 if row['ordinal']>=3:features[row['ordinal']]=feat(parent)
 if (a/'score/score.json').exists():
  sc=json.load(open(a/'score/score.json'))
  for model,s in sc['models'].items():
   scores.append({'id':row['id'],'ordinal':row['ordinal'],'native_contract_valid':row['ordinal'] in [3,5,6,7,8],'split':'preparation_not_formal_holdout','model':model,**{k:s.get(k) for k in ['window_rows','scored_rows','prediction_window_coverage','observed_censored','prediction_stop','risk','tilt_peak_deg','observed_tilt_peak_deg','peak_abs_error_deg','tilt_error_deg','altitude_loss_m','first_crossing','event_windows','prefix_errors']}})
write('startup-ledger.json',{'counts':{'old_P12':48,'P12b_preparation':8,'P12b_formal':0,'cumulative':56},'starts':starts,'not_started_formal':json.load(open(R/'data/p12b-20261026-preparation-v2/formal-stop.json'))['pending'],'replacement_runs':0,'experiment_release':'NOT_PASSED','theory':'CONDITIONAL_RELATIONS_ONLY_NOT_FULL_FEEDBACK'})
write('prediction-scores.json',{'unit_of_analysis':'five valid canonical preparation flights; seven models per flight are correlated outputs, not independent flights; v1 invalid stream and off baseline not promoted','scores':scores})
# Respect each measured safety stop; original scope review and primary labels untouched.
a,b=features[4],features[5];lo=tables[4]['events'][0]['planned_window_profile_s'][0];hi=min(tables[k]['valid_experiment_end_profile_s'] for k in [4,5]);prefix={}
for ordinal,d in [(4,a),(5,b)]:
 sel=(d['t']>=lo)&(d['t']<=hi);ref=int(np.searchsorted(d['t'],lo));q=np.array([tilt(x) for x in d['attitude'][sel]])
 prefix[str(ordinal)]={'rows':int(sel.sum()),'controller_cache_tilt_peak_deg':float(q.max()),'LP_loss_common_first_A_m':max(0,float(d['position'][sel,2].max()-d['position'][ref,2])),'scope':'controller-cache rows through actual safety stop, not whole ULog attitude topic; no frozen outcome rewrite'}
write('common-prefix-review-v2.json',{'old_acceptance_FAIL_unchanged':True,'old_scope_review_retained':True,'interval_profile_s':[lo,hi],'common_prefix':prefix,'whole_task_effect':'UNKNOWN_CENSORED_VS_COMPLETE','release':'NOT_PASSED; unequal safety abort remains unexplained and preparation budget exhausted','reason':'prefix similarity, equal binaries and stripped source do not establish behavioral noninterference'})
# Paired summaries are descriptive; no strict common state and no randomized assignment.
comparisons=[]
for abi,ri in [(5,7),(6,8)]:
 x,y=features[abi],features[ri];ta,tb=tables[abi],tables[ri];end=min(ta['valid_experiment_end_profile_s'],tb['valid_experiment_end_profile_s']);vals={}
 for oi,d in [(abi,x),(ri,y)]:
  sel=(d['t']>=lo)&(d['t']<=end);ts=d['t'][sel];dt=np.diff(ts);ep=np.linalg.norm(d['position'][sel,:2]-d['target_p'][sel,:2],axis=1);power=np.sum(np.square(d['exec_command'][sel]),axis=1)
  vals[str(oi)]={'common_window_s':[lo,end],'active_target_horizontal_error_integral_m_s':float(np.sum((ep[1:]+ep[:-1])*dt/2)),'command_square_integral_rad2_s':float(np.sum((power[1:]+power[:-1])*dt/2)),'full_task_metrics':tables[oi]['full_task_measurement'],'B_before':next(z['state'] for z in tables[oi]['rows'] if z['label']=='B_before'),'entire_holds':tables[oi]['events']}
 comparisons.append({'preparation_AB_ordinal':abi,'preparation_repair_ordinal':ri,'phase':1 if abi==5 else 2,'same_seed':True,'strict_pair':False,'independent_randomized_blocks':0,'scope':'descriptive preparation comparison, same plan and full window; initial/cache differences retained','records':vals})
write('repair-comparisons.json',comparisons)
# Separate event/window and whole-trajectory denominators under scorev2.
agg={}
for model in sorted({s['model'] for s in scores}):
 ss=[s for s in scores if s['model']==model and s['native_contract_valid']];out={}
 for axis in ['tilt','height','task']:
  c=Counter(s['risk']['comparisons'][axis] for s in ss);eligible=sum(s['risk']['classification_eligible'][axis] for s in ss);full=sum(s['risk']['full_trajectory_eligible'][axis] for s in ss);out[axis]={'valid_flights':len(ss),'classification_eligible':eligible,'full_trajectory_eligible':full,'comparison_counts':dict(c)}
 out['event_windows']=[{'id':s['id'],'index':w['index'],'rows':w['rows'],'observed_complete':w['observation_complete'],'predicted_complete':w['prediction_complete'],'risk':w.get('risk')} for s in ss for w in (s['event_windows'] or [])];agg[model]=out
write('prediction-denominators.json',agg)
# Revalidate immutable historical evidence and real saved files (not symlinks).
base=json.load(open(R/'data/p12b-20261026-preparation/baseline.json'));old={n:sha(R/n)==v for n,v in base['files'].items()};runtime=[]
for version in ['preparation','preparation-v2']:
 doc=json.load(open(R/f'data/p12b-20261026-{version}/runtime-snapshot.json'))
 for r in doc['files']:
  p=R/r['snapshot'];runtime.append({'path':r['snapshot'],'sha256':r['sha256'],'match':sha(p)==r['sha256'],'regular_not_symlink':p.is_file() and not p.is_symlink()})
write('preservation.json',{'old_13_immutable_files':old,'runtime_regular_snapshots':runtime,'old_statuses_not_rewritten':True,'all_pass':all(old.values()) and all(r['match'] and r['regular_not_symlink'] for r in runtime)})
# Raw/derived local manifest includes hardlink identity, never double counts allocated bytes.
manifest=[];inodes=set();allocated=0
roots=[R/f'data/p12b-20261026-{n}' for n in ['development','development-v2','preparation','preparation-v2','delivery','reproduction','runtime-local','source-local']]
for root in roots:
 for p in sorted(root.rglob('*')):
  if not p.is_file() or p.is_symlink():continue
  raw=p.suffix in ['.ulg','.bin','.npz'] or p.name in ['telemetry.jsonl','resources.jsonl','p11-sends.jsonl'] or 'runtime-local' in str(p)
  if not raw:continue
  s=p.stat();key=(s.st_dev,s.st_ino);same=key in inodes
  if not same:allocated+=s.st_blocks*512;inodes.add(key)
  manifest.append({'path':str(p.relative_to(R)),'bytes':s.st_size,'sha256':sha(p),'device':s.st_dev,'inode':s.st_ino,'nlink':s.st_nlink,'allocated_bytes':s.st_blocks*512,'hardlink_already_counted':same})
write('raw-and-derived-local-manifest.json',{'files':manifest,'unique_allocated_bytes':allocated,'deletion':False,'raw_data_policy':'local only, no downsampling; rootfs flight logs hardlink same inode; full predictions and solver matrices kept in NPZ/bin','scope':'P12b raw streams, all full arrays including diagnostic drafts/rechecks/reproduction, ordinary runtime copies'})
# Static scientific figure, five on/off preparation F4 records including the censored record.
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
fig,axs=plt.subplots(3,1,figsize=(9,9),sharex=True)
for ordinal in [4,5,6,7,8]:
 d=features[ordinal];end=tables[ordinal]['valid_experiment_end_profile_s'];sel=(d['t']>=lo-.3)&(d['t']<=min(end,lo+4));t=d['t'][sel];h=-d['truth_pv'][:,2];i0=max(0,int(np.searchsorted(d['t'],0,side='right')-1));loss=h[i0]-h[sel]
 label=f'prep{ordinal} '+('AB off (censored)' if ordinal==4 else ('AB' if ordinal<7 else 'REPAIR'))+(' PH1' if ordinal in [4,5,7] else ' PH2')
 axs[0].plot(t,np.array([tilt(q) for q in d['attitude'][sel]]),label=label);axs[1].plot(t,loss);axs[2].plot(t,d['velocity'][sel,2])
axs[0].axhline(45,color='k',ls='--',lw=.8);axs[1].axhline(1,color='k',ls='--',lw=.8)
for ax in axs:
 for a0,b0 in [e['planned_window_profile_s'] for e in tables[5]['events']]:ax.axvspan(a0,b0,color='gray',alpha=.15)
 ax.grid(alpha=.25)
axs[0].set_ylabel('Controller tilt (deg)');axs[1].set_ylabel('World model-origin loss (m)');axs[2].set_ylabel('LP down velocity (m/s)');axs[2].set_xlabel('Absolute profile time (s)');axs[0].legend(fontsize=8,ncol=2);fig.suptitle('Preparation only: same seed, no strict state pairing; shaded planned A/B interruptions');fig.tight_layout();F=R/'docs/figures/p12b';F.mkdir(parents=True,exist_ok=True);fig.savefig(F/'preparation.png',dpi=160);plt.close(fig)
write('review-summary.json',{'counts':{'preparation':8,'formal':0,'cumulative':56},'engineering':'NOT_PASSED','theory':'CONDITIONAL_NOT_PROVEN_FULL_FEEDBACK','replication':'NO_NEW_FORMAL_CROSS_BLOCK_EVIDENCE','models_unchanged':True,'valid_native_prediction_flights':5,'new_SITL_starts_by_review':0,'history_and_runtime_preservation':all(old.values()) and all(r['match'] for r in runtime)})
print('REVIEW_COMPLETE',len(manifest),'raw/array/runtime files; formal0; engineering NOT_PASSED')
