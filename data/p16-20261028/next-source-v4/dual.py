"""Two independent model query histories; shared truth revealed only on own choice."""
import json
from pathlib import Path
from p16.common import B,sha,write
from p16.workflow import Flow,read

def flow(policy):
 assert policy in ['G','R'];return Flow(B/'policies'/policy,B/'attempts.jsonl',policy_id=policy,run_root=B/'runs')
def both_terminal():
 result={p:flow(p).verify_terminal()[1] for p in ['G','R']}
 for p in ['G','R']:assert flow(p).verify_terminal()[1]==result[p]
 return result

def prepare_fill(cell_id):
 terminal=both_terminal();assert (B/'replication-forecast.json').exists(),'fixed six forecasts must be sealed before fill';docs,files=flow('G').inputs();allseen=set().union(*(set(flow(p).verify_terminal()[0]['seen_ids']) for p in ['G','R']));assert cell_id not in allseen
 cell=next(c for c in docs['pool.json'] if c['id']==cell_id);row=docs['rows.json'][cell_id];path=B/'fill-tickets'/f'{cell_id}.json';write(path,dict(kind='truth_fill',terminal=terminal,cell=cell,row=row,pool_sha256=files['pool.json']));return path

def authorize(row,ticket):
 d=read(ticket)
 if d['kind']=='model_query':return flow(d['policy_id']).authorize(row,ticket)
 if d['kind']=='truth_fill':
  assert d['terminal']==both_terminal(),'both policies must stay sealed beforefill';docs,files=flow('G').inputs();assert d['pool_sha256']==files['pool.json'];assert d['row']==row==docs['rows.json'][d['cell']['id']];assert d['cell']==next(c for c in docs['pool.json'] if c['id']==d['cell']['id'])
  assert Path(ticket).resolve()==(B/'fill-tickets'/f"{d['cell']['id']}.json").resolve();assert not any(d['cell']['id'] in flow(p).verify_terminal()[0]['seen_ids'] for p in ['G','R'])
  from p16.workflow import digest
  return dict(kind='truth_fill',ticket_sha256=sha(ticket),row_digest=digest(row),adoption_digest=digest(read(flow('G').path('adoption.json'))),terminal=d['terminal'])
 if d['kind']=='replication':
  assert d['terminal']==both_terminal();plan=read(B/'frozen/replication-plan.json');assert sha(B/'frozen/replication-plan.json')==d['plan_sha256'];assert row in plan['rows'] and row==d['row'];assert sha(B/'replication-forecast.json')==d['forecast_sha256'];assert Path(ticket).resolve()==(B/'replication-tickets'/f"{row['id']}.json").resolve()
  from p16.workflow import digest
  return dict(kind='replication',ticket_sha256=sha(ticket),adoption_digest=digest(read(flow('G').path('adoption.json'))),terminal=d['terminal'])
 raise AssertionError('unknown ticketkind')

def prepare_replication():
 terminal=both_terminal();plan=read(B/'frozen/replication-plan.json');assert plan['fixed_before_any_main_result'] and not plan['model_update_allowed']
 assert not any(json.loads(l).get('stage')=='replication' and json.loads(l)['event']=='START_INTENT' for l in (B/'attempts.jsonl').read_text().splitlines())
 maps={p:read(flow(p).path('maps/q08.json')) for p in ['G','R']};prior=read(B/'frozen/initial-predictions.json');records=[]
 for row in plan['rows']:records.append(dict(row=row,initial=prior[row['cell_id']],G=maps['G']['prediction'][row['cell_id']],R=maps['R']['prediction'][row['cell_id']],newseed_outcomes_used=False))
 out=B/'replication-forecast.json';write(out,dict(terminal=terminal,rows=records,plan_sha256=sha(B/'frozen/replication-plan.json'),model_refit=False))
 for row in plan['rows']:write(B/'replication-tickets'/f"{row['id']}.json",dict(kind='replication',row=row,terminal=terminal,plan_sha256=sha(B/'frozen/replication-plan.json'),forecast_sha256=sha(out)))
 return out
