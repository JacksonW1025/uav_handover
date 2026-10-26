#!/usr/bin/env python3
"""Independent gates from completed records, no outcome selection or new launch."""
import json,sys,os
from pathlib import Path
import numpy as np
from pyulog import ULog
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import write,sha
from p11.observe import matrix
from p12c.features import compare
from p12.execution import DTYPE
P=R/'data/p12b-20261026-preparation-v2';D=R/'data/p12b-20261026-development-v2'
def feat(p):
 d=dict(np.load(p/'analysis/observation/synchronized.npz'));h=next(t.data for t in ULog(str(p/'run/flight.ulg'),['research_p12']).data_list if t.name=='research_p12');sel=h['active'].astype(bool)
 assert np.array_equal(h['timestamp_sample'][sel],d['sample_us']);d['mean']=matrix(h,'history_before',4)[sel];d['count']=h['history_count_before'][sel];d['call_index']=h['call_index_before'][sel]
 send=[json.loads(s) for s in (p/'run/p11-sends.jsonl').read_text().splitlines()];epoch=next(x['stream_t0_monotonic_s'] for x in send if x['stream_t0_monotonic_s'] is not None)*1e9;d['t']=(d['run_wall_ns'].astype(np.int64)-epoch)/1e9
 for key in ['filter_after','scaled_joint','command','sample_us','end_ns']:
  a=[]
  for motor in range(4):
   e=np.fromfile(p/f'run/gz-motor/execution-p12-{motor}.bin',DTYPE);j=np.searchsorted(e['end_ns'],d['run_wall_ns'],side='right')-1;assert (j>=0).all();a.append(e[key][j])
  d['exec_'+key]=np.array(a).T
 return d

def main():
 out=P/'acceptance.json'
 if out.exists():raise FileExistsError(out)
 protocol=json.load(open(P/'protocol.json'));rows=protocol['rows'];accepted={};prestates={};engineering={};tests={}
 for r in rows:
  p=D/r['id'];a=p/'analysis';result=json.load(open(p/'result.json'));accepted[r['id']]=result;tests[r['id']+'_wrapper_identity']=result['evidence_ok']
  if r['observe']:
   g=json.load(open(a/'engineering.json'));native=json.load(open(a/'native/native-audit.json'));solver=json.load(open(P/'solver-recheck'/r['id']/'solver-audit.json'));seed=json.load(open(a/'actual-seed.json'));engineering[r['id']]={'engineering':g['engineering_status'],'pre_read':native['status'],'solver':solver['status'],'seed':seed['metadata_seed'],'canonical_rows':native['pre_read_contract']['same_call_rows'],'ULog_redundancy_status':native['pre_read_contract']['ULog_redundancy_status'],'whole':result['task_outcome']};tests[r['id']+'_engineering']=g['engineering_status']=='PASS' and native['status']=='PASS' and solver['status']=='PASS' and seed['metadata_seed'] in [x['seed'] for x in seed['setter_calls']]
 # Same final binary and same runtime/control-source identity off/on F4.
 off=next(r for r in rows if r['ordinal']==4);on=next(r for r in rows if r['ordinal']==5);a=D/off['id'];b=D/on['id'];ca=json.load(open(a/'candidate.json'));cb=json.load(open(b/'candidate.json'));tests['off_on_same_compiled_candidate']=ca==cb
 ma=json.load(open(a/'analysis/measured/measurement.json'));mb=json.load(open(b/'analysis/measured/measurement.json'));dif={k:abs(ma['whole'][k]-mb['whole'][k]) for k in ['max_tilt_deg','max_altitude_loss_m']};tests['off_on_effect_scale']=dif['max_tilt_deg']<=5 and dif['max_altitude_loss_m']<=.2
 da=feat(a);db=feat(b);from p11.pack import source_plan
 cfg=json.load(open(a/'run/config.json'));events=[json.loads(s) for s in (a/'run/events.jsonl').read_text().splitlines()];origin=next(e for e in events if e['event']=='p1_reference_origin');plan=source_plan(cfg,origin['origin_ned_m'],origin['yaw_rad']);first=plan['common_first_gap_profile_s'];prestates['off4_on5']=compare(da,db,[first-.5,first])
 overhead={}
 for r in rows:
  o=json.load(open(D/r['id']/'analysis/observation/observation.json'));base=o['baseline'];overhead[r['id']]={k:base.get(k) for k in ['whole_observation_cycle_us','control_sample_dt_us','sample_missed_total','duplicate_total','regressed_total']};tests[r['id']+'_cycle_p99']=base['whole_observation_cycle_us']['p99']<=2500
 led=[json.loads(s) for f in [R/'data/p12b-20261026-preparation/attempts.jsonl',P/'attempts.jsonl'] for s in f.read_text().splitlines()];starts=[r for r in led if r['event']=='START_INTENT'];tests['count8_not_reset']=len(starts)==8 and len({r['id'] for r in starts})==8 and all(r['budget_class']=='preparation' for r in starts)
 tests['v1_stop_preserved']=any(r['event']=='STOP_CRITICAL' and r['id']=='prep02-F2-ph2-NORMAL0-on' for r in led)
 baseline=json.load(open(R/'data/p12b-20261026-preparation/baseline.json'));tests['old_history_preserved']=all(sha(R/n)==h for n,h in baseline['files'].items())
 st=os.statvfs(R);available=st.f_bavail*st.f_frsize;required=45*600_000_000+22_000_000_000;tests['capacity']=available>=required
 status='PASS' if all(tests.values()) else 'FAIL'
 result={'schema':'p12b-preparation-acceptance-direct-v2-1','experimental_engineering_status':status,'tests':tests,'new_preparation_starts':8,'formal_starts':0,'old_P12_starts':48,'cumulative_starts':56,'engineering_v2_only':engineering,'v1_status':'prep1 baseline closed; prep2 STOP/NOT_PASSED; not replaced or promoted','independent_versions':'v1 ULog nonunique NOT_PASSED retained; direct-v2 canonical native records, no old field backfill; frozen formal uses only v2 accepted runtime','off_on_same_version_effect_difference':dif,'off_on_prestate_diagnostic':prestates,'overhead':overhead,'budget':{'preparation':8,'formal':45,'total':53,'old_P12':48,'cumulative':101},'capacity':{'available_bytes':available,'required45_plus_analysis_reserve_bytes':required,'per_start_bytes':600000000,'analysis_and_reserve_bytes':22000000000},'strict_pairs':0,'comparability':'pre-frozen assigned random blocks with recorded initial/cache differences, no post-treatment matching','theory_gate':{'status':'NOT_PROVEN_FULL_FEEDBACK','experimental_stop':False,'progress':'real installed JointConstraint full matrix and post velocity relation numerically verified, plus conditional event-height map','first_gap':'future admissible joint/solver residual and impulse domain; force limits infinite; body/estimator/cache feedback and integration defect domain unclosed','A4':'NOT_PROVEN_EXCLUDED'},'models':'unchanged sealed M3/M4, no new candidate/refit','score':'p12-scoring-2; LP primary/task and independent H=-z diagnosis separate','formal_release':'requires freeze commit/push/remote readback; user already authorizes automatic execution'}
 write(out,result);print(json.dumps({'status':status,'tests':tests,'off_on_difference':dif,'overhead':overhead,'capacity':result['capacity']},indent=2));return result
if __name__=='__main__':raise SystemExit(main()['experimental_engineering_status']!='PASS')
