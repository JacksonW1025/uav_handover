"""Analyze finished ledger IDs only, no simulation or external mutations."""
import json,sys,time,traceback
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(Path(__file__).parent));sys.path.insert(0,str(R/'tools'))
from record_review_v1 import review
from p9_model import write
P=R/'data/p13-20261026-preparation';out=R/'data/p13-20261026-formal-analysis-v1';out.mkdir(exist_ok=True)
while True:
 rows=[json.loads(s) for s in (P/'attempts.jsonl').read_text().splitlines()];starts={x['id']:x for x in rows if x['event']=='START_INTENT' and x['budget_class']=='formal'};done=[x['id'] for x in rows if x['event']=='FINISH' and x['budget_class']=='formal']
 for ident in done:
  dst=out/ident
  if (dst/'receipt.json').exists():continue
  if dst.exists():raise RuntimeError('partial analysis retained, version repair separately '+ident)
  try:review(R/starts[ident]['output'],dst);print('ANALYZED',ident,flush=True)
  except BaseException as e:
   traceback.print_exc();write(out/'analysis-error.json',{'id':ident,'reason':repr(e),'experiment_layer_affected':False,'no_new_start':True});raise
 write(out/'progress.json',{'formal_starts':len(starts),'formal_finished':len(done),'analyzed':len(list(out.glob('*/receipt.json'))),'planned':66,'no_new_starts_by_analysis':True})
 if len(done)==66:break
 if any(x['event']=='STOP_CRITICAL' and x.get('queue')=='formal' for x in rows):break
 time.sleep(10)
