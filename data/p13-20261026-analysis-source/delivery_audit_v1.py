"""Read-only end-of-P13 identity/budget/history/runtime/raw evidence audit."""
import sys,json,os,stat,time
from pathlib import Path
from collections import Counter
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p9_model import write,sha

def audit(out):
 out.mkdir(parents=True,exist_ok=False);P=R/'data/p13-20261026-preparation';Z=R/'data/p13-20261026-freeze';ledger=[json.loads(s) for s in (P/'attempts.jsonl').read_text().splitlines()];starts=[x for x in ledger if x['event']=='START_INTENT'];fin={x['id']:x for x in ledger if x['event']=='FINISH'};formal=[x for x in starts if x['budget_class']=='formal'];dev=[x for x in starts if x['budget_class']=='development'];design=json.load(open(R/'config/p13-formal.json'));issues=[]
 if len(starts)!=len({x['id'] for x in starts}):issues.append('duplicate START ID')
 if len(dev)>12 or len(formal)>72 or len(starts)>84:issues.append('budget exceeded')
 if [x['id'] for x in formal]!=[x['id'] for x in design['rows']][:len(formal)]:issues.append('formal order not frozen order')
 freeze=json.load(open(Z/'manifest.json'));drift={f:{'expected':h,'actual':sha(R/f)} for f,h in freeze['files'].items() if sha(R/f)!=h};old=json.load(open(P/'old-history-check-v1.json'));oldcheck={f:{'expected':v['expected'],'actual':sha(R/f),'unchanged':sha(R/f)==v['expected']} for f,v in old['files'].items()};snap=json.load(open(P/'runtime-snapshot-v1.json'));runtime=[]
 for v in snap['files']:
  p=R/v['snapshot'];runtime.append(dict(v,current_source_sha256=sha(Path(v['source'])),snapshot_sha256=sha(p),still_ordinary=p.is_file() and not p.is_symlink(),unchanged=sha(p)==v['sha256']==sha(Path(v['source']))))
 cases=[]
 for x in starts:
  tar=R/x['output'];a=tar/'analysis-v1';r={'id':x['id'],'budget_class':x['budget_class'],'ordinal':x['ordinal'],'start_consumed':True,'finish':x['id'] in fin}
  if x['id'] not in fin:cases.append(r);issues.append('pending terminal '+x['id']);continue
  eng=json.load(open(a/'engineering.json'));ph=json.load(open(tar/'physics-v3/physics.json' if x['id']=='dev01-F2-NORMAL' else a/'physics/physics.json'));md=json.load(open(tar/'run/metadata.json'));wrapper=json.load(open(tar/'wrapper-result.json'));candidate=json.load(open(tar/'candidate.json'));ulog=sha(tar/'run/flight.ulg');r.update(engineering=eng['status'],physical=ph['status'],task=fin[x['id']]['task_outcome'],censored=fin[x['id']]['censored'],original_rigid_ideal=ph['ideal_rigid_geometry_preserved']['status'],binary_sha256=md['binary_sha256'],plugin_sha256=md['gz_research_plugin_sha256'],policy_sha256=md['policy_sha256'],raw_ulog_sha256=ulog,metadata_ulog_sha256=md.get('ulog_sha256'),px4_exit=wrapper['checks']['px4_exit'],candidate_project_head=candidate['project_head'],case_config_sha256=x['config_sha256'])
  if r['engineering']!='PASS' or r['physical']!='PASS' or not r['px4_exit'] or md.get('ulog_sha256')!=ulog:issues.append('evidence/runtime mismatch '+x['id'])
  if x['budget_class']=='formal':
   plan=next(v for v in design['rows'] if v['id']==x['id']);r['config_still_frozen']=sha(R/plan['config'])==plan['config_sha256']==x['config_sha256'];r['candidate_equal_frozen']={k:v for k,v in candidate.items() if k!='project_head'}=={k:v for k,v in json.load(open(Z/'candidate.json')).items() if k!='project_head'};r['future_hidden']=json.load(open(a/'prediction/isolation.json'))['future_data_hidden']
   if not all(r[k] for k in ['config_still_frozen','candidate_equal_frozen','future_hidden']):issues.append('formal identity/blind contract '+x['id'])
  cases.append(r)
 if drift:issues.append('freeze file drift')
 if not all(v['unchanged'] for v in oldcheck.values()):issues.append('old history changed')
 if not all(v['unchanged'] and v['still_ordinary'] for v in runtime):issues.append('actual runtime/source snapshot mismatch')
 raw=[];inodes=set();allocated=0
 for base in sorted((R/'data').glob('p13*')):
  if not base.is_dir():continue
  for p in sorted(base.rglob('*')):
   if not p.is_file() or p.is_symlink():continue
   rel=p.relative_to(R);parts=rel.parts
   selected=('gz-motor' in parts or p.name in ['flight.ulg','telemetry.jsonl','resources.jsonl','p11-sends.jsonl'] or p.suffix=='.npz' or 'runtime-local' in base.name)
   if not selected or 'rootfs' in parts or 'cli' in parts:continue
   st=p.stat();key=(st.st_dev,st.st_ino);new=key not in inodes
   if new:allocated+=st.st_blocks*512;inodes.add(key)
   raw.append({'path':str(rel),'bytes':st.st_size,'sha256':sha(p),'allocation_counted_once':new})
 write(out/'raw-derived-runtime-manifest.json',{'schema':'p13-complete-local-manifest-1','files':raw,'files_n':len(raw),'unique_inode_allocated_bytes':allocated,'ordinary_runtime_copy_and_all_full_arrays_retained':True,'not_in_Git':'ULog/gz-motor/telemetry/resources/fullNPZ/runtime copies use existing uniform ignore rules; manifest delivered, no deletion/downsampling','historical_raw_unchanged_scope':'no old raw writes/deletes performed; selected old small evidence hash checks independently below'})
 st=os.statvfs(R);report={'schema':'p13-delivery-audit-1','status':'PASS' if not issues else 'FAIL','issues':issues,'counts':{'development_starts':len(dev),'formal_starts':len(formal),'finished':len(fin),'P13_total_starts':len(starts),'formal_assigned_not_started':len(design['rows'])-len(formal),'unused_optional6':6,'P13_cap84':84,'old_P12_series_actual_starts':66,'cumulative_P12_series_plus_P13':66+len(starts)},'formal_science_outcomes':dict(Counter(r['task'] for r in cases if r['budget_class']=='formal' and r['finish'])),'formal_censored':sum(r['censored'] for r in cases if r['budget_class']=='formal' and r['finish']),'ledger_sha256':sha(P/'attempts.jsonl'),'frozen_manifest_sha256':sha(Z/'manifest.json'),'frozen_file_drift':drift,'old_history':oldcheck,'runtime':runtime,'cases':cases,'available_bytes':st.f_bavail*st.f_frsize,'raw_manifest_sha256':sha(out/'raw-derived-runtime-manifest.json'),'write_error_detection_limit':'frozen destructor final header/fclose return not completely checked; independent fullread/length/valid/phase/continuity/hash establishes current evidence, not fsync/powerloss guarantee','theory':'NOT_PROVEN_FULL_FEEDBACK, engineering PASS is separate','new_SITL_by_audit':0}
 write(out/'audit.json',report);print('DELIVERY_AUDIT',report['status'],report['counts'],issues);return report
if __name__=='__main__':audit(Path(sys.argv[1]))
