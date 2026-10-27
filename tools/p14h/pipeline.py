"""Recoverable independent queue: one physical item, information review, then score.
No run is replaced. Existing START_INTENT always prevents a second launch.
"""
import sys,json,subprocess,resource
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14h.common import *

def main():
 plan=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False);write(out/'before.json',dict(plan=str(plan.relative_to(R)),sha256=sha(plan),rule='no repeat of any START_INTENT; each prior physical end inspected through campaign and review; scientific failure retained'))
 for n,row in enumerate(json.load(open(plan))['rows']):
  ident=row['id'];attempts=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];started=any(x['event']=='START_INTENT' and x['id']==ident for x in attempts);ended=any(x['event'] in ['FINISH','OUTCOME_RESOLVED'] and x['id']==ident for x in attempts)
  if started and not ended:raise RuntimeError('existing identity outcome unresolved, inspect owned processes; never relaunch '+ident)
  if not started:
   print('INDEPENDENT_NEXT',n+1,ident,flush=True)
   with (out/f'{n+1:02d}-campaign.log').open('w') as f:rc=subprocess.run([PY,R/'tools/p14h/campaign.py',ident,plan],stdout=f,stderr=subprocess.STDOUT).returncode
   if rc!=0:raise RuntimeError('physical/analysis result requires scoped review; no duplicate '+ident)
  target=B/'runs'/ident;review=B/f'review-e{n+1:02d}-v1';evaluation=B/f'evaluation-e{n+1:02d}-v1'
  for command,artifact,label in [([PY,R/'tools/p14h/review.py',target,review],review/'result.json','review'),([PY,R/'tools/p14h/evaluate.py',target,review,evaluation],evaluation/'summary.json','evaluation')]:
   if artifact.exists():continue
   if artifact.parent.exists():raise RuntimeError('partial analysis directory retained; versioned repair required '+str(artifact.parent))
   with (out/f'{n+1:02d}-{label}.log').open('w') as f:rc=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT).returncode
   if rc!=0:raise RuntimeError('scoped analysis error '+label+' '+ident)
  info=json.load(open(target/'information.json'));rev=json.load(open(review/'result.json'));append(out/'progress.jsonl',dict(id=ident,ordinal=n+1,task_outcome=info['task_outcome'],censored=info['censored'],actual_branches=rev['actual_read_branches'],review=str(review.relative_to(R)),evaluation=str(evaluation.relative_to(R)),next_independent_allowed=True));print('INDEPENDENT_REVIEWED',n+1,ident,info['task_outcome'],flush=True)
 used=resource.getrusage(resource.RUSAGE_SELF);append(B/'resource-ledger-v2.jsonl',dict(event='MANAGER_FINAL',id='independent-pipeline-manager',CPU_s_manager=used.ru_utime+used.ru_stime,scope='pipeline self only; all children counted separately'));write(out/'complete.json',dict(status='FINISHED',items=len(json.load(open(plan))['rows']),no_extra_starts=True))
if __name__=='__main__':main()
