from pathlib import Path
import json,numpy as np
import sequential as s
ROOT=Path(__file__).resolve().parent;d=json.loads((ROOT/'sequential_results.json').read_text());a=np.load(ROOT/'sequential_scores.npz')['scores'];examples=json.loads((ROOT/'sequential_examples.json').read_text());checks=[]
for e in examples:
 seq=e['sequence'];assert len(seq)==12 and len({r['case'] for r in seq})==12;assert not set(r['group'] for r in seq)&set(e['heldout']);checks.append(e['learner']+'|'+e['policy'])
order_delta=float(np.max(abs(a[:,:,:,:,-1,:]-a[:,:,:,:1,-1,:])));assert order_delta<1e-10,order_delta
# Compare online source residual updates with the batch posterior at an identical revealed set.
model=s.Learner('greybox_gp',s.kernel());fold=s.FOLDS[0];_,seq,pred=s.run('greybox_gp','map_variance',fold,0,s.kernel());q=[];y=[];hq=[];hy=[]
for r in seq:
 j=next(i for i,g in enumerate(s.GROUPS) if g['id']==r['group']);obs=next(o for o in s.GROUPS[j]['cases'] if o['id']==r['case']);q.append(j);y.append(obs['y']);
 if obs['height_known']:hq.append(j);hy.append(obs['height'])
K=s.kernel();batch=s.PRIORS['greybox']+K[:,q]@np.linalg.solve(K[np.ix_(q,q)]+.25*np.eye(len(q)),np.array(y)-s.PRIORS['greybox'][q]);hbatch=s.HPRIORS['greybox']+K[:,hq]@np.linalg.solve(K[np.ix_(hq,hq)]+.16*np.eye(len(hq)),np.array(hy)-s.HPRIORS['greybox'][hq]);assert np.max(abs(batch-pred[-1,:6]))<1e-10;assert np.max(abs(hbatch-pred[-1,6:]))<1e-10
_,seq,pr=s.run('cheap_ridge','map_variance',fold,0,s.kernel());q=[];y=[]
for r in seq:
 j=next(i for i,g in enumerate(s.GROUPS) if g['id']==r['group']);q.append(j);y.append(r['label'])
Z=np.r_[s.Z0,s.Z[q]];Y=np.r_[s.Y0,y];coef=np.linalg.solve(Z.T@Z+s.PEN,Z.T@Y);assert np.max(abs(s.Z@coef-pr[-1,:6]))<1e-8
out=dict(sequence_examples_checked=len(examples),each_query_reveals_one_unique_case=True,target_combinations_never_revealed=True,full_budget_order_invariance_max_delta=order_delta,source_sequential_matches_batch_posterior=True,cheap_online_ridge_matches_batch_refit=True,initial_history_count=len(s.TR),initial_history_contains_AB=any(r['branch'] in ['AB','REPAIR'] for r in s.TR));assert not out['initial_history_contains_AB'];(ROOT/'verification.json').write_text(json.dumps(out,indent=2));print(out)
