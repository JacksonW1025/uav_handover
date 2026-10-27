"""A: source-order/publisher/first-read audit. Actual future is diagnostic only."""
import sys,json,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import records,write,sha
from p12c.features import load

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[];start=time.perf_counter()
 for r in records():
  run=r['target']/'run';d=load(run,r['analysis']);events=[json.loads(l) for l in (run/'events.jsonl').read_text().splitlines()];sends=[json.loads(l) for l in (run/'p11-sends.jsonl').read_text().splitlines()];sendtime=np.array([s['before_ns'] for s in sends]);positions=np.array([s['position'] for s in sends],dtype=np.float32);velocities=np.array([s['velocity'] for s in sends],dtype=np.float32);res=np.flatnonzero(~d['stale'].astype(bool)&np.r_[False,d['stale'][:-1].astype(bool)])
  for e in events:
   if e['event']!='p5_gap_ended':continue
   a,b=e['planned_profile_s'];idx=[j for j in res if b-.02<=d['t'][j]<=b+.1]
   if not idx:rows.append({'id':r['id'],'gap_index':e['index'],'status':'NO_RESUME_WITNESS','planned':[a,b]});continue
   j=idx[0];matches=(np.max(abs(positions-d['target_p'][j]),axis=1)<3e-6)&(np.max(abs(velocities-d['target_v'][j]),axis=1)<3e-6)&(sendtime<=d['read_wall_ns'][j]);mm=np.flatnonzero(matches);m=mm[-1] if len(mm) else None
   prev=np.flatnonzero(d['committed'][:j]);before=int(prev[-1]) if len(prev) else max(0,j-2)
   row={'id':r['id'],'gap_index':e['index'],'status':'MATCHED_PUBLISH_PAYLOAD' if m is not None else 'UNKNOWN_PUBLISH_ID','planned':[a,b],'actual_emit_profile_s':e['first_emit_profile_s'],'actual_resume_profile_s':float(d['t'][j]),'resume_sample_us':int(d['sample_us'][j]),'resume_native_us':int(d['native_us'][j]),'read_host_ns':int(d['read_wall_ns'][j]),'publish_before_ns':None if m is None else int(sendtime[m]),'publish_to_read_ms':None if m is None else (int(d['read_wall_ns'][j])-int(sendtime[m]))/1e6,'emit_after_plan_ms':(e['first_emit_profile_s']-b)*1000,'resume_after_emit_ms':(float(d['t'][j])-e['first_emit_profile_s'])*1000,'previous_commit_read_host_ns':int(d['read_wall_ns'][before]),'publish_after_previous_commit_ms':None if m is None else (int(sendtime[m])-int(d['read_wall_ns'][before]))/1e6,'LP_age_us':int(d['sample_us'][j]-d['lp_sample'][j]),'att_age_us':int(d['sample_us'][j]-d['att_sample'][j]),'index':int(d['call_index'][j]),'committed':bool(d['committed'][j]),'publisher_semantics':'first gap-exit emit immediate, timer restarts there; subsequent now-last>=period; ROSlatest delivery then PH1commit gate','read_source':sha(run/'gz-motor/read-p12b.bin'),'send_source':sha(run/'p11-sends.jsonl'),'role':'future actual only for diagnosis; never a model clock word'}
   rows.append(row)
  print('TIMING_AUDITED',r['id'],flush=True)
 good=[r for r in rows if r['status']=='MATCHED_PUBLISH_PAYLOAD'];summary={'records':rows,'elapsed_s':time.perf_counter()-start,'actual_fields_are_diagnostic':True,'new_starts':0}
 for k in ['publish_to_read_ms','emit_after_plan_ms','resume_after_emit_ms','publish_after_previous_commit_ms']:
  v=np.array([r[k] for r in good]);summary[k]={'n':len(v),'min':float(min(v)),'median':float(np.median(v)),'max':float(max(v)),'percentiles':np.percentile(v,[5,95]).tolist()}
 write(out/'timing.json',summary)

if __name__=='__main__':main()
