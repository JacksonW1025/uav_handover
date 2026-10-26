#!/usr/bin/env python3
"""P13 experimental layer freeze after counted development, separate theory state."""
import sys,json,shutil,os,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import write,sha
import p2_batch
P=R/'data/p13-20261026-preparation';Z=R/'data/p13-20261026-freeze'
def main():
 ledger=[json.loads(x) for x in (P/'attempts.jsonl').read_text().splitlines()];starts=[x for x in ledger if x['event']=='START_INTENT'];finished={x['id'] for x in ledger if x['event']=='FINISH'}
 if len(starts)!=12 or any(x['budget_class']!='development' for x in starts) or any(x['id'] not in finished for x in starts):raise RuntimeError('preparation not12 unique terminal starts')
 cases=[]
 for row in starts:
  t=R/row['output'];eng=json.load(open(t/'analysis-v1/engineering.json'));path=t/'physics-v3/physics.json' if row['id']=='dev01-F2-NORMAL' else t/'analysis-v1/physics/physics.json';ph=json.load(open(path));r=json.load(open(t/'wrapper-result.json'));md=json.load(open(t/'run/metadata.json'))
  if eng['status']!='PASS' or ph['status']!='PASS' or not all(r['checks'][k] for k in ['px4_exit','no_crash_markers','trace','output_chain']):raise RuntimeError('hard development failure '+row['id'])
  cases.append({'id':row['id'],'engineering':'PASS','physical':'PASS','ideal_rigid_geometry':ph['ideal_rigid_geometry_preserved']['status'],'binary_sha256':md['binary_sha256'],'plugin_sha256':md['gz_research_plugin_sha256'],'policy_sha256':md['policy_sha256'],'task_outcome':eng['task_outcome'],'censored':eng['censored'],'engineering_sha256':sha(t/'analysis-v1/engineering.json'),'physical_sha256':sha(path)})
 if any(len({x[k] for x in cases})!=1 for k in ['binary_sha256','plugin_sha256','policy_sha256']):raise RuntimeError('runtime not constant')
 continuity=json.load(open(R/'data/p13-20261026-diagnostics/physical-continuity-all12-v1/continuity.json'));events=json.load(open(R/'data/p13-20261026-events/preparation-event-audit.json'));closure=json.load(open(P/'source-closure-v1/closure.json'))
 if len(continuity['records'])!=12 or any(x['status']!='PASS' for x in continuity['records']) or not events['complete_all'] or closure['status']!='PASS':raise RuntimeError('offline interface/source/event prerequisites')
 st=os.statvfs(R);avail=st.f_bavail*st.f_frsize;required=72*600000000+30000000000
 if avail<required:raise RuntimeError('capacity gate')
 acceptance={'schema':'p13-engineering-design-release-1','new_starts':12,'formal_starts':0,'engineering_hard_gate':'PASS','experimental_design_gate':'PASS','fixed_platform_scope':'same light-on physical-buffered source and runtime; no off-equivalence claim, old P12c FAIL preserved','actual_geometry_scope':'full measured geometry with observed joint residual, old ideal rigid FAIL remains; algebraic consistency not future bound','records':cases,'independent_continuity_sha256':sha(R/'data/p13-20261026-diagnostics/physical-continuity-all12-v1/continuity.json'),'event_audit_sha256':sha(R/'data/p13-20261026-events/preparation-event-audit.json'),'writer_detection_limits':continuity['writer_error_detection_scope'],'available_bytes':avail,'required_bytes':required,'theory_gate':{'status':'NOT_PROVEN_FULL_FEEDBACK','experimental_stop':False,'known_physical_initial':'direct COM p/v/H/W/q/omega and physical time now recorded, controller initial age retained','unknown':'future solver/joint residual domain and estimator/cache/history feedback invariance; observed errors are not future hard bounds'},'forecast_gate':'blind input/runtime contract PASS; predictive misses retained and not engineering veto','development_budget_exhausted':True}
 write(P/'acceptance.json',acceptance)
 draft=R/'data/p13-20261026-formal-draft-v1';design=json.load(open(draft/'design.json'));dest=R/'config/p13-formal-cases';shutil.copytree(draft/'cases',dest)
 for row in design['rows']:
  if sha(R/row['config'])!=row['config_sha256']:raise RuntimeError('formal case copy changed')
 write(R/'config/p13-formal.json',dict(design,status='FROZEN_BEFORE_FORMAL',acceptance_sha256=sha(P/'acceptance.json')))
 Z.mkdir(exist_ok=False);shutil.copytree(P/'models',Z/'models');write(Z/'candidate.json',p2_batch.identity());files={}
 for base in ['tools','research','config']:
  for f in sorted((R/base).rglob('*')):
   if f.is_file() and '__pycache__' not in f.parts:files[str(f.relative_to(R))]=sha(f)
 for f in [P/'acceptance.json',P/'engineering-spec.json',P/'engineering-spec-v2.json',P/'runtime-snapshot-v1.json',P/'development-v1.json',P/'development-v2.json',P/'development-v3.json',P/'source-closure-v1/closure.json',R/'docs/THOR_P13_PLAN.md',R/'docs/THOR_P13_INTERFACE.md',R/'docs/THOR_P13_PREPARATION.md',R/'docs/THOR_P13_THEORY.md']+list((Z/'models').glob('*')):
  if f.is_file():files[str(f.relative_to(R))]=sha(f)
 write(Z/'manifest.json',{'schema':'p13-experiment-layer-freeze-1','files':files,'source_baseline':'73d467beb70acf2c7413468f74be76e3b73c723a','preparation_ledger_sha256':sha(P/'attempts.jsonl'),'formal_count':66,'formal_cap':72,'extra6':'UNUSED never replacements','total_cap':84,'development_starts':12,'old_series_starts':66,'analysis_layer':'data/p13 analysis-source/report/plot/path/serialization independently versionable, preserve originals and recheck affected data; no parameter/threshold/order changes','models':['M3','M4','M5'],'new_candidates':1,'runtime':'ordinary actual copies and12 metadata hashes, no old symlink snapshot claim','receipt':'normal commit+push+remote readback then autonomous formal, no general approval required'})
 print('P13 FREEZE CREATED66;12 development; formal0; commit/push/readback required')
if __name__=='__main__':main()
