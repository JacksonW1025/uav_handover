import json,copy
from pathlib import Path
import numpy as np,pytest
from p16.common import R,B,write,sha,append
from p16.workflow import Flow,read
from p16.quality import evaluate
from p16.baseline import predict

def test_curves_never_connect_sameG_different_prefix():
 pool=[dict(id=f'{p}{i}',family='F2',prefix=p,curve_id=f'F2/{p}',G=float(i)) for p in ['B','AB'] for i in range(3)]
 truth={c['id']:dict(valid=True,tilt='FAIL' if c['prefix']=='AB' else 'SUCCESS',height='SUCCESS',task='FAIL' if c['prefix']=='AB' else 'SUCCESS') for c in pool};pred={k:{c:v[c] for c in ['tilt','height','task']} for k,v in truth.items()};score=evaluate(pool,truth,pred)
 assert len(score['components']['task']['edges'])==2 and all(e['status']=='NO_TRANSITION' for e in score['components']['task']['edges'])
 p=predict(pool,{'B0':truth['B0']});assert p['AB0']['task']=='UNKNOWN'

def test_material_pass_and_strict_model_not_old_default():
 d=read(B/'material-acceptance-v1/full.json');assert d['status']=='PASS' and d['training_trajectories']==18 and d['sequential_queries_reproduced']==12
 from p16.greybox import parameters,core
 assert parameters()['thrust']!=core.reference.M['thrust']
 assert read(B/'material-acceptance-v1/adapter-fixtures-importfix.json')['status']=='PASS'

def signature():
 states=dict(v=[0,0,0],q=[1,0,0,0],omega=[0,0,0],filter=[700]*4,pending=[[700]*4,[701]*4],h=[0]*16,previous=[0]*4,mean=[0]*4,future_resume_error=[0,0,0],last_read_age_us=204000)
 return dict(operation='same',family='F2',G=2.,duration=.36,phase=1,future_plan_hash='sameknownsuffix',sample_phase_us=0,commit_phase=0,count=1,LP_phase_us=0,native_minus_sample_us=0,states=states)

def test_reuse_has_state_timing_gate_and_ledger_counterexample():
 from p16.reuse import gate,apply
 a=signature();b=copy.deepcopy(a);b['sample_phase_us']=4000;assert not gate(a,b)[0] and gate(a,b,True)[0]
 pool=[dict(id='d',family='F2',prefix='B',G=2),dict(id='r',family='F2',prefix='AB',G=2)];initial={c['id']:dict(reuse_signature=signature(),capture_suffix=dict(delta_loss=.1,peak_tilt=25),capture_ledger=dict(L=.9,D=1.1,prefix_tilt=25)) for c in pool};history={'d':dict(valid=True,complete=True,capture_suffix=dict(available=True,branch_compatible=True,signature=signature(),delta_loss=.1,peak_tilt=25))};base={c['id']:dict(tilt='SUCCESS',height='SUCCESS',task='SUCCESS') for c in pool}
 full,tr=apply(pool,initial,history,base);bad,_=apply(pool,initial,history,base,drop_ledger=True)
 assert full['r']['height']=='FAIL' and bad['r']['height']=='SUCCESS';assert any(t['accepted'] for t in tr)
 history['d']['capture_suffix']['signature']['states']['h'][0]=5.;full,tr=apply(pool,initial,history,base);assert not any(t['accepted'] for t in tr)

@pytest.fixture
def dual_fixture(tmp_path,monkeypatch):
 import p16.dual as dual
 monkeypatch.setattr(dual,'B',tmp_path);pool=[dict(id=f'{f}-{i}',family=f,prefix='B' if i%2==0 else 'AB',G=.55+i*.2,curve_id=f'{f}/{i%2}') for f in ['F2','F4'] for i in range(6)];initial={c['id']:dict(peak_tilt=30.,peak_loss=.2,model_complete=True) for c in pool};rows={c['id']:dict(id='run-'+c['id'],cell_id=c['id'],family=c['family'],prefix=c['prefix'],G=c['G'],stage='main',seed=123,config='fixture') for c in pool};source=tmp_path/'source.py';source.write_text('# synthetic unit only\n');adoption=dict(adopted=True,files={str(source):sha(source)})
 for p in ['G','R']:dual.flow(p).initialize(pool,initial,rows,dict(query_cap=8),adoption)
 write(tmp_path/'frozen/initial-predictions.json',initial);write(tmp_path/'frozen/replication-plan.json',dict(fixed_before_any_main_result=True,model_update_allowed=False,rows=[dict(rows[c['id']],id='rep-'+c['id'],stage='replication',seed=456) for c in pool[:6]]))
 return dual

def reveal(dual,policy):
 f=dual.flow(policy);ticket=f.prepare_next();row=read(ticket)['row'];dual.authorize(row,ticket);t=dual.B/'runs'/row['id'];result=t/'analysis-v1/result.json'
 if not result.exists():
  write(t/'row.json',row);write(result,dict(id=row['id'],valid=True,complete=True,peak_tilt=30.,peak_loss=.2,tilt='SUCCESS',height='SUCCESS',task='SUCCESS',prefix_failed_before_B=False));append(f.ledger,dict(event='START_INTENT',id=row['id'],stage='main'));append(f.ledger,dict(event='FINISH',id=row['id']))
 f.record_result(ticket,result);return ticket

def test_dual_history_isolated_and_shared_reveal_not_an_extra_START(dual_fixture):
 d=dual_fixture;g=reveal(d,'G');assert len(d.flow('G').history()[0])==1 and len(d.flow('R').history()[0])==0
 r=reveal(d,'R');assert read(g)['cell']==read(r)['cell'];starts=[json.loads(x) for x in (d.B/'attempts.jsonl').read_text().splitlines() if json.loads(x)['event']=='START_INTENT'];assert len(starts)==1
 for _ in range(7):reveal(d,'G')
 d.flow('G').terminal()
 with pytest.raises(FileNotFoundError):d.prepare_fill('F4-5')
 for _ in range(7):reveal(d,'R')
 d.flow('R').terminal();d.prepare_replication();assert (d.B/'replication-forecast.json').exists()
 seen=set(d.flow('G').history()[0])|set(d.flow('R').history()[0]);docs,_=d.flow('G').inputs();cell=next(c['id'] for c in docs['pool.json'] if c['id'] not in seen);ticket=d.prepare_fill(cell);assert d.authorize(read(ticket)['row'],ticket)['kind']=='truth_fill'
 old=d.flow('R').path('maps/q08.json');old.write_text(old.read_text()+' ')
 with pytest.raises(AssertionError):d.authorize(read(ticket)['row'],ticket)

def test_fixed_secondary_six_and_pool_before_new_main():
 p=read(B/'freeze-inputs-v4/replication-with-seam-hash.json');assert len(p['rows'])==6 and p['fixed_before_any_main_result'] and not p['model_update_allowed'];assert len({r['id'] for r in p['rows']})==6
 assert len({r['seed'] for r in p['rows']})==1 and p['rows'][0]['seed']!=162810101
 pool=read(B/'freeze-inputs-v4/pool.json');assert len(pool)==24 and len({c['curve_id'] for c in pool})==4

def test_moving_target_initialization_is_preserved():
 from p16.greybox import OUT,controller
 rows=read(OUT/'offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json')['rows'];i=copy.deepcopy(rows[0]['initial']);i['target_v']=[1.2,.4,0.];c=controller(i,1)
 assert np.array_equal(c.target.s,i['target_v']) and np.array_equal(c.h,i['h']) and c.count==i['history_count'] and c.index==i['call_index']

def test_forecast_adapter_all24_keeps_fullcapture_accounting():
 p=read(B/'freeze-inputs-v4/initial-predictions.json')
 for row in p.values():
  assert row['future_actual_inputs'] is False and row['capture_ledger'] is not None
  before=row['capture_ledger'];after=row['capture_suffix'];assert abs(max(before['D'],before['L']+after['delta_loss'])-row['peak_loss'])<1e-8

def test_frozen_counterfactual_and_shared_project_costs_are_separate():
 c=read(B/'frozen/cost-contract.json');assert 'cannot sum as actualproject' in c['counterfactual'] and c['registered_before_first_main'];assert 'UNKNOWN' in c['historical']
