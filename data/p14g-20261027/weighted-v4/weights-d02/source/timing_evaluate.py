"""Actual words only at independent scoring side, never predictor/selection."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *
from p12c.features import load

def events(t,stale):
 return {'capture':t[np.flatnonzero(stale & np.r_[False,~stale[:-1]])].tolist(),'resume':t[np.flatnonzero(~stale & np.r_[False,stale[:-1]])].tolist()}
def main():
 out=Path(sys.argv[1]);register(out,'H1 actual membership/cache/native/commit clock evaluation, futureword score side only');rows=[]
 for name,c in cases().items():
  run=R/c['raw_run'];data=load(run,run.parent/'analysis-v1');hist=dict(np.load(run.parent/'analysis-v1/native/history.npz'));d=doc(name);live=data['t']>=d['initial']['profile_s'];actual=events(data['t'][live],data['stale'][live].astype(bool));fixed=[]
  for f in sorted((OLD/'registered-points-v1/predictions'/name).glob('*.npz')):
   if f.stem=='old-complement':continue
   z=np.load(f);fixed.append(events(z['trace'][:,0],z['trace'][:,34].astype(bool)))
  bracket=json.load(open(B/'A-v2/result.json'));brow=next(r for r in bracket['rows'] if r['id']==name);comparison=[]
  for event in brow['conditional_bracket_coverage']:
   for kind in ['capture','resume']:
    a,b=event['conditional_brackets']['planned_gap'];values=[t for word in fixed for t in word[kind] if (a if kind=='capture' else b)-.02<=t<=b+.08];truth=event[kind];envelope=[min(values),max(values)] if values else None;predinterval=event['conditional_brackets'][kind+'_profile_interval'];comparison.append({'kind':kind,'actual':truth,'fixed8_point_envelope':envelope,'fixed8_outside':sum(not(envelope and envelope[0]-.000001<=t<=envelope[1]+.000001) for t in truth),'causal_conditional_interval':predinterval,'conditional_outside':sum(not(predinterval[0]<=t<=predinterval[1]) for t in truth),'point_vs_interval_caveat':'broader conditional coverage is not point accuracy or full dynamics equivalence'})
  def dist(x):
   u,n=np.unique(x,return_counts=True,axis=0);return [{'value':v.tolist(),'count':int(c)} for v,c in zip(u,n)]
  idx=hist['call_before'];commit=idx%2==0;clock=np.c_[np.diff(data['sample_us'].astype(np.int64)),np.diff(data['native_us'].astype(np.int64))];age=np.c_[data['sample_us'].astype(np.int64)-data['att_sample'].astype(np.int64),data['sample_us'].astype(np.int64)-data['lp_sample'].astype(np.int64)];ca=data['sample_us'].astype(np.int64)[:,None]-data['exec_sample_us'].astype(np.int64)
  rows.append({'id':name,'events':comparison,'cache_age_joint_us':dist(age),'sample_native_increment_pairs_us':dist(clock),'source_commit_matches':bool(np.array_equal(commit,data['committed'])),'history_count_matches':bool(np.array_equal(hist['count_after'],np.where(commit,0,hist['count_before']+1))),'applied_command_age_range_us':[int(ca.min()),int(ca.max())],'latest_value_scope':'not every generated action must be consumed; source pendingcommand continuous. Per-motor timestamps sampledatcontrolRunwall, not proof allphysicscallbackordering.'})
 # Independently parse original fixed8 Bcapture miss, keep original failure.
 legacy=json.load(open(OLD/'A-clock-reach-v2/p13-F2-b1-AB-short.json'));oldwords=[json.load(open(f)) for f in (OLD/'A-clock-v1/predictions/p13-F2-b1-AB-short').glob('word*.json')];Bcaps=[r['capture'][1] for r in oldwords];actual=legacy['events'][1]['actual_capture_diagnostic'];oldmiss={'actual_B_capture':actual,'fixed8_B_capture_envelope':[min(Bcaps),max(Bcaps)],'early_outside_s':min(Bcaps)-actual[0],'conditional_interval':legacy['events'][1]['capture_profile_interval'],'old_validity_unchanged':True}
 write(out/'result.json',{'rows':rows,'old_counterexample':oldmiss,'source_graph_native70_example':{'sample_ms':[80336,80340,80344,80348],'native_ms':[80336,80344,80344,80348],'source':'THOR_P12_INTERFACE.md andoldrun70diagnostic; agesdifferent4ms butactualguardlabelsunchanged. Graphallowsnondecreasingnative,debtchanges4ms. No newrun/rewrite.'},'totals':{'actual_events':sum(len(e['actual']) for r in rows for e in r['events']),'fixed8_outside':sum(e['fixed8_outside'] for r in rows for e in r['events']),'conditional_outside':sum(e['conditional_outside'] for r in rows for e in r['events'])},'all_commit_history_checks':all(r['source_commit_matches'] and r['history_count_matches'] for r in rows)})
if __name__=='__main__':main()
