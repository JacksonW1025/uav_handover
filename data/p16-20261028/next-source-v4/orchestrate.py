"""G/R first, both terminal seals, fixed seed2 forecasts, then blind truth fill.
All policies choose from only their own returned histories. No repeated START.
"""
import json,subprocess,time,resource
from pathlib import Path
from p16.common import *
from p16.dual import flow,both_terminal,prepare_fill,prepare_replication
from p16.workflow import read

def ledger():return [json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()] if (B/'attempts.jsonl').exists() else []
def progress(last):
 ss=[x for x in ledger() if x['event']=='START_INTENT'];x=dict(time=now(),starts={k:sum(r['stage']==k for r in ss) for k in ['development','main','replication']},total_START=len(ss),policy_queries={p:len(flow(p).history()[0]) for p in ['G','R']},last=last);(B/'progress.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def execute(row,ticket):
 old=[x for x in ledger() if x.get('id')==row['id']]
 if any(x['event']=='START_INTENT' for x in old):
  assert any(x['event'] in ['FINISH','SCOPED_REVIEW_RESOLVED'] for x in old),'uncertain/pending run inspect owned processes; no retry'
  assert read(B/'runs'/row['id']/'row.json')==row
  return False
 plan=B/'frozen/physical-plan.json';cmd=[str(PY),'-m','p16.campaign',str(plan),row['id'],str(B/'preflight-formal/gate.json'),str(ticket)]
 subprocess.run(cmd,check=True);return True

def main():
 start=time.process_time();enforce=read(B/'freeze-receipt.json');assert enforce['remote_verified'];assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==enforce['commit']
 from p9_run import host_gate
 host_gate()
 for step in range(1,9):
  for policy in ['G','R']:
   f=flow(policy);history,_=f.history()
   if len(history)>=step:continue
   assert len(history)==step-1
   ticket=f.path(f'queries/q{step:02d}/decision.json')
   if not ticket.exists():ticket=f.prepare_next()
   row=read(ticket)['row'];auth=f.authorize(row,ticket);new=execute(row,ticket);result=B/'runs'/row['id']/'analysis-v1/result.json';f.record_result(ticket,result)
   write(f.path(f'queries/q{step:02d}/reveal-cost.json'),dict(policy=policy,row=row['id'],new_physical_START=new,physical_record=str(result),counterfactual_query_cost=read(B/'runs'/row['id']/'execution.json'),information_revealed_only_after_own_choice=True,actual_project_saved_repeat=not new))
   progress(dict(policy=policy,query=step,id=row['id'],new_START=new,result=read(result)['task']));print('P16_QUERY_DONE',policy,step,row['cell_id'],read(result)['task'],flush=True)
 for p in ['G','R']:
  if not flow(p).path('terminal-seal.json').exists():flow(p).terminal()
 both_terminal()
 if not (B/'replication-forecast.json').exists():prepare_replication()
 pool=read(B/'frozen/pool.json');order=read(B/'frozen/execution-order.json')
 for cell in order:
  row=read(B/'frozen/rows.json')[cell]
  if any(x.get('id')==row['id'] and x['event']=='START_INTENT' for x in ledger()):continue
  ticket=B/'fill-tickets'/f'{cell}.json'
  if not ticket.exists():ticket=prepare_fill(cell)
  execute(row,ticket);progress(dict(role='truth_fill',id=row['id']));print('P16_FILL_DONE',cell,flush=True)
 for row in read(B/'frozen/replication-plan.json')['rows']:
  ticket=B/'replication-tickets'/f"{row['id']}.json";execute(row,ticket);progress(dict(role='seed2',id=row['id']));print('P16_SEED2_DONE',row['id'],flush=True)
 write(B/'execution-complete.json',dict(time=now(),manager_CPU_s=time.process_time()-start,scope='orchestrator CPU; childcampaign/physical/review/model costs separately measured',both_policies_sealed=both_terminal(),all_starts=len([x for x in ledger() if x['event']=='START_INTENT'])));print('P16_PHYSICAL_COMPLETE',flush=True)
if __name__=='__main__':main()
