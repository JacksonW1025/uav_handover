import importlib.util,pathlib,sys
p=pathlib.Path(__file__).with_name('report.py');spec=importlib.util.spec_from_file_location('p16_analysis',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_persistent_not_first_transient():
 s=[dict(query=i,quality=dict(same_quality=x)) for i,x in enumerate([False,True,False,True,True])];assert m.persistent(s)==3
 assert m.persistent([dict(query=0,quality=dict(same_quality=False))]) is None

def test_scores_unknown_stays_denominator_and_unqueried():
 p=[dict(id=str(i),family='F2',prefix='AB',G=i,curve_id='F2/AB') for i in range(4)];t={str(i):dict(valid=True,tilt='SUCCESS',height='SUCCESS',task='SUCCESS') for i in range(4)};pr={str(i):dict(tilt='SUCCESS',height='SUCCESS',task='SUCCESS') for i in range(4)};pr['3']['task']='UNKNOWN';r=m.scores(p,t,[dict(query=1,seen_ids=['0'],prediction=pr)],{'0':dict(wall_s=100,CPU_measured_s=50)})
 assert r['final']['components']['task']['accuracy']==.75
 assert r['final']['components']['task']['prediction_unknown']==1
 assert r['series'][0]['unqueried_quality']['components']['task']['N_valid']==3
 assert r['first_persistent_joint_quality'] is None
 assert r['series'][0]['query_wall_s']==100

def test_development_cost_missing_not_zero_claim():
 x=m.cost('p16-d02-F4-AB');assert not x['CPU_complete'];assert x['unknown'];assert x['wall_s']>90

def test_end_to_end_synthetic_fullgrid_no_real_ledger(tmp_path,monkeypatch):
 # Synthetic test records only, isolated from real run identity and maps.
 import json,copy
 real=m.B;fake=tmp_path/'synthetic';fake.mkdir();monkeypatch.setattr(m,'B',fake);monkeypatch.setattr(m,'R',tmp_path)
 def w(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x))
 pool=m.read(real/'frozen/pool.json');rows=m.read(real/'frozen/rows.json');initial=m.read(real/'frozen/initial-predictions.json');rep=m.read(real/'frozen/replication-plan.json')
 for name,x in [('pool',pool),('rows',rows),('initial-predictions',initial),('replication-plan',rep)]:w(fake/f'frozen/{name}.json',x)
 w(fake/'freeze-receipt.json',dict(commit='SYNTHETIC_TEST_ONLY'))
 w(fake/'reuse-calibration-history-v2/summary.json',dict(CPU_s=1))
 w(fake/'material-acceptance-v1/full.json',dict(elapsed_seconds=1))
 ledger=[];truth={}
 def run(row,tr):
  rid=row['id'];w(fake/f'runs/{rid}/analysis-v1/result.json',tr);w(fake/f'runs/{rid}/execution.json',dict(wall_s=100,CPU_s=30));w(fake/f'runs/{rid}/review-cost.json',dict(wall_s=5,CPU_s=2));w(fake/f'runs/{rid}/manager-cost.json',dict(wall_s=106,CPU_s=1));ledger.append(dict(event='START_INTENT',id=rid,stage=row['stage'],role='synthetic'))
 for c in pool:
  pr=initial[c['id']];tr=dict(valid=True,complete=True,tilt=pr['tilt'],height=pr['height'],task=pr['task'],peak_tilt=pr['peak_tilt'],peak_loss=pr['peak_loss'],prefix_failed_before_B=bool(pr['prefix_failed_before_B']),B_plan_reached=True,capture_suffix=dict(pr['capture_suffix'],available=True,signature=pr['reuse_signature'],branch_compatible=True));truth[c['id']]=tr;run(rows[c['id']],tr)
 seedpred=[]
 for row in rep['rows']:run(row,truth[row['cell_id']]);seedpred.append(dict(row=row,initial=initial[row['cell_id']],G=initial[row['cell_id']],R=initial[row['cell_id']]))
 w(fake/'replication-forecast.json',dict(rows=seedpred))
 for i in range(2):run(dict(id=f'dev{i}',stage='development'),next(iter(truth.values())))
 (fake/'attempts.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in ledger))
 for policy in ['G','R']:
  h={}
  for q in range(9):
   pred,rr=m.model_map(pool,initial,h,policy);w(fake/f'policies/{policy}/maps/q{q:02d}.json',dict(query=q,prediction=pred,seen_ids=list(h)))
   if q<8:
    x=m.next_query(pool,initial,h,policy)['selected'];tr=truth[x['id']];w(fake/f'policies/{policy}/queries/q{q+1:02d}/decision.json',dict(cell=x));w(fake/f'policies/{policy}/queries/q{q+1:02d}/return.json',dict(cell_id=x['id'],record=tr));h[x['id']]=tr
 m.main(fake/'SYNTHETIC_OUTPUT_NOT_EXPERIMENT')
 d=m.read(fake/'SYNTHETIC_OUTPUT_NOT_EXPERIMENT/delivery.json');assert d['truth']['valid']==24;assert d['costs']['actual_unique_START']==32;assert d['methods']['A_grid']['final']['same_quality']
 assert not (real/'SYNTHETIC_OUTPUT_NOT_EXPERIMENT').exists()
