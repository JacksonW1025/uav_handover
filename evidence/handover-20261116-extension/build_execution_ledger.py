import json,hashlib,time
from pathlib import Path
OUT=Path(__file__).resolve().parent
repo=Path('/home/car/uav_handover')
sets=[('T4',OUT/'t4-raw',['001_deadline60-a1','002_active_release60-a1']),('T3',OUT/'t3-raw',['001_zero_capture-a1','002_continuous_capture-a1']),('T1-retime',OUT/'t1-retime',['PRE']),('T2',OUT/'t2-live',['N4','N2']),('T1-feedforward',OUT/'t1-feedforward',['FF','NOFF'])]
rows=[];ledgerrows=[]
for category,base,arms in sets:
 ledger=[json.loads(x) for x in (base/'attempts.jsonl').read_text().splitlines()]
 ledgerrows.extend(dict(category=category,**x) for x in ledger)
 for arm in arms:
  d=base/arm;r=json.loads((d/'result.json').read_text());f=d/'flight';m=json.loads((f/'metadata.json').read_text());ev=[json.loads(x) for x in (f/'events.jsonl').read_text().splitlines()]
  ready=[x.get('condition') for x in ev if x['event']=='ready'];exits=[{k:x[k] for k in ['name','pid','exit_code']} for x in ev if x['event']=='process_stopped']
  assert 'landing' in ready and 'disarmed' in ready
  assert all(next(x for x in exits if x['name']==name)['exit_code']==0 for name in ['px4','gazebo'])
  failures=[x for x in ev if x['event']=='failure']
  sha=hashlib.sha256((f/'flight.ulg').read_bytes()).hexdigest();assert sha==m['ulog_sha256']
  rows.append(dict(category=category,arm=arm,source_dir=str(d),result=r,landed=True,disarmed=True,failures=failures,process_exits=exits,source_identity={k:m.get(k) for k in ['source_commit','project_commit','binary','binary_sha256','policy_sha256','gz_research_plugin_sha256','source_diff_sha256','ulog_sha256']}))
starts=[x for x in ledgerrows if x['event']=='START_INTENT'];assert len(starts)==9
result=dict(batch='20261116-extension-only',physical_starts=len(starts),completed_flights=len(rows),prearm_failures=0,simulator='Thor-only PX4 RAPTOR Gazebo civilian x500 SITL; original protections unchanged',new_flights=rows,total_workflow_wall_s=sum(r['result'].get('wall_s',r['result'].get('execution_cost',{}).get('wall_s',0)) for r in rows),ledger_events=ledgerrows,notes=['Excludes the prior five-flight batch.','T1-feedforward arms remain classical throughout; neural handover times do not apply.','Source commit denotes shared source base; exact executed private binary identity is separately retained.','No automatic reruns, source/controller/protection changes, or old evidence overwrites.'])
(OUT/'execution-ledger.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['physical_starts','completed_flights','total_workflow_wall_s']}))
