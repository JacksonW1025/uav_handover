"""Immutable own-query maps, bound run tickets, terminal seal, and fill gate.
No full-truth table is accepted by this module.
"""
import json,hashlib
from pathlib import Path
from p16.common import write,sha,now
from p16.sequential import calibrated,next_query,WIDTH,SHRINK

CAP=8
RETURN_FIELDS=['valid','complete','peak_tilt','peak_loss','tilt','height','task','prefix_failed_before_B']
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def read(path):return json.load(open(path))

class Flow:
 def __init__(self,root,ledger):self.root=Path(root);self.ledger=Path(ledger)
 def path(self,name):return self.root/name
 def initialize(self,pool,initial,rows,rules,adoption):
  assert not self.root.exists(),'never overwrite a workflow'
  assert rules.get('query_cap',CAP)==CAP and rules.get('width_G_s',WIDTH)==WIDTH and rules.get('shrink',SHRINK)==SHRINK and rules.get('exploration_query_numbers',[4,7])==[4,7],'rules disagree with implemented recipe'
  assert set(initial)=={x['id'] for x in pool} and len(initial)==len(pool)
  assert set(rows)==set(initial)
  for cell in pool:
   row=rows[cell['id']];assert row['stage']=='main' and row['cell_id']==cell['id'] and row['family']==cell['family'] and row['G']==cell['G']
  assert len({r['id'] for r in rows.values()})==len(rows)
  assert adoption.get('adopted') is True and adoption.get('files'),'real adoption identity required before initialize'
  for p,h in adoption['files'].items():assert sha(p)==h,'model adoption source hash mismatch'
  self.root.mkdir(parents=True);docs={'pool.json':pool,'initial.json':initial,'rows.json':rows,'rules.json':rules,'adoption.json':adoption}
  for name,value in docs.items():write(self.path(name),value)
  manifest={name:sha(self.path(name)) for name in docs};write(self.path('inputs-seal.json'),dict(schema='P16-flow-inputs-1',files=manifest,query_cap=CAP,time=now()))
  write(self.path('maps/q00.json'),dict(query=0,seen_ids=[],history_digest=digest({}),prediction=calibrated(pool,initial,{}),input_files=manifest,zero_query_model=True))
 def inputs(self):
  seal=read(self.path('inputs-seal.json'));assert seal['query_cap']==CAP
  for name,h in seal['files'].items():assert sha(self.path(name))==h,'workflow input drift '+name
  for path,h in read(self.path('adoption.json'))['files'].items():assert sha(path)==h,'adopted model source drift'
  return {name:read(self.path(name)) for name in ['pool.json','initial.json','rows.json','rules.json']},seal['files']
 def history(self):
  history={};sources={};missing=False
  for i in range(1,CAP+1):
   p=self.path(f'queries/q{i:02d}/return.json')
   if not p.exists():missing=True;continue
   assert not missing,'return sequence has a hole'
   q=read(p);d=self.path(f'queries/q{i:02d}/decision.json');assert sha(d)==q['decision_sha256'],'decision modified after returned result'
   source=Path(q['source_result']);assert sha(source)==q['source_sha256'],'queried raw analysis modified'
   actual=read(source);assert {k:actual.get(k) for k in RETURN_FIELDS}==q['record'],'return must equal whitelisted actual query result'
   assert q['cell_id'] not in history;history[q['cell_id']]=q['record'];sources[f'q{i:02d}']=sha(p)
  return history,sources
 def prepare_next(self):
  assert not self.path('terminal-seal.json').exists(),'B terminal: query loop closed'
  docs,files=self.inputs();history,sources=self.history();n=len(history);assert n<CAP
  path=self.path(f'queries/q{n+1:02d}/decision.json');assert not path.exists(),'pending decision: inspect, never replace'
  query=next_query(docs['pool.json'],docs['initial.json'],history);m=self.path(f'maps/q{n:02d}.json');mp=read(m);assert mp['history_digest']==digest(history) and mp['prediction']==query['prediction'],'current map differs from own returned history'
  cell=query['selected'];row=docs['rows.json'][cell['id']]
  decision=dict(kind='model_query',query=n+1,row=row,row_digest=digest(row),cell=cell,cell_digest=digest(cell),input_files=files,history_digest=digest(history),history_sources=sources,map_path=str(m.resolve()),map_sha256=sha(m),reason=query['reason'],selected_prediction=query['prediction'][cell['id']],created_at=now(),future_labels_used=False)
  write(path,decision);return path
 def record_result(self,decision_path,result_path):
  assert not self.path('terminal-seal.json').exists(),'B terminal: no result/update after seal'
  decision_path=Path(decision_path);d=read(decision_path);assert d['kind']=='model_query';q=d['query'];assert 1<=q<=CAP;assert decision_path.resolve()==self.path(f'queries/q{q:02d}/decision.json').resolve()
  docs,files=self.inputs();history,sources=self.history();assert len(history)==q-1 and digest(history)==d['history_digest'] and sources==d['history_sources'];assert files==d['input_files']
  row=d['row'];assert docs['rows.json'][d['cell']['id']]==row
  result_path=Path(result_path).resolve();run=(self.root.parent/'runs'/row['id']).resolve();assert result_path.is_relative_to(run) and result_path.name=='result.json' and result_path.parent.name.startswith('analysis-'),'must return this actual run analysis'
  assert digest(read(run/'row.json'))==d['row_digest']
  ledger=[json.loads(l) for l in self.ledger.read_text().splitlines()];ss=[x for x in ledger if x.get('id')==row['id'] and x['event']=='START_INTENT'];assert len(ss)==1 and ss[0]['stage']=='main'
  assert any(x.get('id')==row['id'] and x['event'] in ['FINISH','SCOPED_REVIEW_RESOLVED'] for x in ledger),'physical review must return before update'
  result=read(result_path);assert result['id']==row['id'];record={k:result.get(k) for k in RETURN_FIELDS}
  assert all(record[k] in ['SUCCESS','FAIL','UNKNOWN'] for k in ['tilt','height','task'])
  if record['prefix_failed_before_B'] is True:assert record['task']=='FAIL','prefix failure irreversible'
  p=self.path(f'queries/q{q:02d}/return.json');write(p,dict(query=q,cell_id=d['cell']['id'],run_id=row['id'],record=record,source_result=str(result_path),source_sha256=sha(result_path),decision_sha256=sha(decision_path),time=now()))
  history,sources=self.history();write(self.path(f'maps/q{q:02d}.json'),dict(query=q,seen_ids=list(history),history_digest=digest(history),history_sources=sources,prediction=calibrated(docs['pool.json'],docs['initial.json'],history),input_files=files,zero_query_model=False))
  return p
 def terminal(self):
  docs,files=self.inputs();history,sources=self.history();assert len(history)==CAP,'all8 query returns required before truth fill'
  assert {p.name for p in self.path('queries').iterdir()}=={f'q{i:02d}' for i in range(1,CAP+1)},'unexpected query directory'
  assert {p.name for p in self.path('maps').iterdir()}=={f'q{i:02d}.json' for i in range(CAP+1)},'unexpected map'
  artifact_files={name:h for name,h in files.items()};artifact_files['inputs-seal.json']=sha(self.path('inputs-seal.json'))
  for p in sorted(self.root.glob('maps/q*.json')):artifact_files[str(p.relative_to(self.root))]=sha(p)
  for p in sorted(self.root.glob('queries/q*/*.json')):artifact_files[str(p.relative_to(self.root))]=sha(p)
  result=dict(schema='P16-B-terminal-1',query_count=CAP,seen_ids=list(history),history_digest=digest(history),history_sources=sources,files=artifact_files,final_map='maps/q08.json',time=now(),truth_fill_labels_seen=False,no_more_updates=True)
  p=self.path('terminal-seal.json');write(p,result);return p
 def verify_terminal(self):
  p=self.path('terminal-seal.json');t=read(p);assert t['query_count']==CAP and t['no_more_updates']
  for name,h in t['files'].items():assert sha(self.path(name))==h,'terminal artifact drift '+name
  history,sources=self.history();assert len(history)==CAP and digest(history)==t['history_digest'] and sources==t['history_sources']
  return t,sha(p)
 def prepare_fill(self,cell_id):
  t,sealhash=self.verify_terminal();docs,files=self.inputs();assert cell_id not in t['seen_ids'],'queried cell cannot be replacement fill'
  cell=next(c for c in docs['pool.json'] if c['id']==cell_id);row=docs['rows.json'][cell_id]
  p=self.path(f'fill/{cell_id}.json');write(p,dict(kind='truth_fill',cell=cell,cell_digest=digest(cell),row=row,row_digest=digest(row),input_files=files,terminal_sha256=sealhash,source_B_map_sha256=sha(self.path(t['final_map'])),fill_must_not_update_B=True,time=now()));return p
 def authorize(self,row,ticket_path):
  path=Path(ticket_path).resolve();assert path.is_relative_to(self.root.resolve()),'ticket outside workflow'
  ticket=read(path);docs,files=self.inputs();cell=ticket['cell'];assert ticket['input_files']==files and digest(row)==ticket['row_digest'] and row==ticket['row'],'row changed or another run used'
  assert row==docs['rows.json'][cell['id']] and cell==next(c for c in docs['pool.json'] if c['id']==cell['id']) and digest(cell)==ticket['cell_digest'],'pool/case mismatch'
  if ticket['kind']=='model_query':
   assert not self.path('terminal-seal.json').exists(),'model closed after terminal'
   history,sources=self.history();assert ticket['query']==len(history)+1<=CAP and ticket['history_digest']==digest(history) and ticket['history_sources']==sources
   assert path==self.path(f"queries/q{ticket['query']:02d}/decision.json").resolve()
   m=Path(ticket['map_path']);assert m.resolve()==self.path(f'maps/q{len(history):02d}.json').resolve() and sha(m)==ticket['map_sha256'],'map binding failure'
   expected=next_query(docs['pool.json'],docs['initial.json'],history);assert cell==expected['selected'] and expected['prediction']==read(m)['prediction'],'choice not from own query map'
   assert ticket['selected_prediction']==expected['prediction'][cell['id']] and ticket['reason']==expected['reason'],'selection prediction/reason changed'
  elif ticket['kind']=='truth_fill':
   terminal,sealhash=self.verify_terminal();assert ticket['terminal_sha256']==sealhash and ticket['source_B_map_sha256']==sha(self.path(terminal['final_map']));assert cell['id'] not in terminal['seen_ids'];assert path==self.path(f"fill/{cell['id']}.json").resolve()
  else:raise AssertionError('unrecognized main operation')
  return dict(kind=ticket['kind'],ticket_sha256=sha(path),adoption_digest=digest(read(self.path('adoption.json'))),pool_sha256=files['pool.json'],row_digest=digest(row),history_or_terminal_digest=ticket.get('history_digest',ticket.get('terminal_sha256')),prefix_failed_before_B_prediction=ticket.get('selected_prediction',{}).get('prefix_failed_before_B'))
