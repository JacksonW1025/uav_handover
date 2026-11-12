import json,hashlib
from pathlib import Path
A=Path(__file__).parent;B=A.parent/'handover-f1-sync-20261112'
rows=[]
for p in sorted(B.glob('00*-a1/result.json')):
 r=json.loads(p.read_text());a=json.loads((A/p.parent.name/'audit.json').read_text());s=json.loads((A/p.parent.name/'score.json').read_text());rows.append(dict(case=r['case'],cost=r['execution_cost'],execution=r['execution_status'],reason=r['reason'],cleanup_error=r['cleanup_error'],candidate_unchanged=r['candidate_unchanged'],physical=s['physical_task'],peak_tilt_deg=s['physical']['peak_tilt_deg'],first_landed_us=a['completion']['first_landed_native_us'],first_disarmed_us=a['completion']['first_disarmed_native_us'],process_exits=a['completion']['process_stops']))
assert len(rows)==6
out={'attempts':6,'retries':0,'repeats_each_arm':2,'seed':20261110,'completed':rows,'wall_s':sum(r['cost']['wall_s'] for r in rows),'cpu_s':sum(r['cost']['cpu_s'] for r in rows),'note':'Costs include failed safety-stop attempts; classic no-switch is Offboard, not Mission. Simulator process cleanup is not physical landing. No extra launches.'}
(A/'execution-summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(out['wall_s'],out['cpu_s'])
