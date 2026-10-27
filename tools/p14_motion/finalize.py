"""Independent preservation and evidence ledger, read-only historical inputs."""
import sys,json,subprocess,datetime,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import sha,write

def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);base=ROOT/'data/p14-motion-20261027';old=ROOT/'data/p14-20261027'
 bound=json.load(open(old/'audit-v1/input-hashes.json'));changed=[p for p,h in bound.items() if sha(ROOT/p)!=h]
 freeze=json.load(open(ROOT/'data/p13-20261026-freeze/manifest.json'))['files'];drift=[p for p,h in freeze.items() if sha(ROOT/p)!=h]
 histories=json.load(open(old/'delivery-v1/preservation.json'))['current_historic_ledger_hashes'];historydrift=[p for p,h in histories.items() if sha(ROOT/p)!=h]
 selected=json.load(open(base/'inputs-v3/old-input-hashes.json'));rawdrift=[p for p,h in selected.items() if sha(ROOT/p)!=h]
 paths=['tools/p14','config/p14-offline.json','tests/test_p14.py','data/p14-20261027','docs/THOR_P14_REPORT.md','docs/THOR_P14_PLAN.md','docs/THOR_P14_STATE.md','docs/THOR_P14_REPRODUCE.md','.gitignore']
 diff=subprocess.check_output(['git','diff','--name-only','eed2f84daca23f7a36fce8c4ab0ea8b1fba1512c','--',*paths],cwd=ROOT,text=True).splitlines()
 seal=json.load(open(base/'tubes-final-v1/before-compute.json'));core=['tools/p14_motion/'+p for p in ['core.py','algebra.py','tube.py']];modeldrift=[p for p in core if sha(ROOT/p)!=seal['source_hashes'][p]]
 protocol=json.load(open(base/'protocol-seal.json'));protocoldrift=[p for p,h in protocol['files'].items() if sha(ROOT/p)!=h]
 preserve={'old_P14_bound_inputs':len(bound),'changed':changed,'P13_frozen_files':len(freeze),'frozen_drift':drift,'old_ledger_drift':historydrift,'selected_raw_drift':rawdrift,'old_canonical_or_gitignore_diff':diff,'final_tube_model_drift':modeldrift,'original_protocol_drift':protocoldrift,'new_SITL':0,'status':'PASS' if not any([changed,drift,historydrift,rawdrift,diff,modeldrift,protocoldrift]) else 'FAIL'}
 write(out/'preservation.json',preserve);assert preserve['status']=='PASS'
 arrays={str(p.relative_to(ROOT)):{'sha256':sha(p),'bytes':p.stat().st_size,'git_ignored':subprocess.run(['git','check-ignore','-q',str(p.relative_to(ROOT))],cwd=ROOT).returncode==0} for p in base.rglob('*.npz')}
 assert all(x['git_ignored'] for x in arrays.values());write(out/'derived-local-manifest.json',arrays)
 scores=json.load(open(base/'analysis-v2/summary.json'));den={}
 for name in scores[0]['models']:
  vals=[r['models'][name]['score'] for r in scores if name in r['models']];entry={}
  for comp,key in [('tilt','risk_comparison'),('height','height_risk_comparison'),('task','task_risk_comparison')]:
   entry[comp]={'records':len(vals),'actual_failure_n':sum(v['risk']['observed'][comp]=='FAILURE' for v in vals),'predicted_unknown_n':sum(v['risk']['predicted'][comp]=='UNKNOWN' for v in vals),'observed_unknown_n':sum(v['risk']['observed'][comp]=='UNKNOWN' for v in vals),'classifiable_n':sum(v['risk']['classification_eligible'][comp] for v in vals),'comparisons':dict(collections.Counter(v[key] for v in vals)),'full_trajectory_n':sum(v['risk']['full_trajectory_eligible'][comp] for v in vals)}
  entry['windows']={str(w):{key:dict(collections.Counter(e[key] for v in vals for e in v['event_windows'] if e['window_s']==w)) for key in ['risk_comparison','height_risk_comparison','task_risk_comparison']} for w in [.5,2]};den[name]=entry
 write(out/'score-denominators.json',{'case_count':4,'new_independent_flights':0,'all_retrospective':True,'fixed_diagnostic_selection_not_population_sample':True,'models':den})
 sources=['tools/p14/model.py','tools/p14/extension.py','tools/p14/affine.py','tools/p12/state.py','tools/p11/observe.py','tools/p13/physical_model.py','tools/apply_research.py','research/state/MemoryInit.hpp','research/state/ActuatorGate.hpp','research/state/TargetProfile.hpp']
 sources += ['uav_lab/.local/checkouts/px4-raptor/'+p for p in ['src/modules/mc_raptor/mc_raptor.cpp','src/modules/simulation/gz_bridge/GZBridge.cpp','src/modules/ekf2/EKF/output_predictor/output_predictor.cpp','src/modules/sensors/vehicle_angular_velocity/VehicleAngularVelocity.cpp','src/lib/mathlib/math/filter/LowPassFilter2p.hpp','src/lib/rl_tools/rl_tools/include/rl_tools/inference/executor/operations_generic.h']]
 write(out/'source-evidence-hashes.json',{p:sha(ROOT/p) for p in sources})
 write(out/'attempt-ledger.json',{'new_SITL':0,'stage':'alloffline','original_seal':str(base/'protocol-seal.json'),'final_tube_cases':11,'final_first_two_reused_from':'tubes-final-v1, originalmodel hashverified','preserved':['inputs-v1,v2','point-v1 (attitude/nav frame hypothesis)','tubes-v1 error, tubes-v2,v3','structure-v1,directions-v1','tubes-final-v1 summary-file error after2completed','cache-diagnostics-v1/v2 task0 initial-info sensitivity','assemble-v2 missing directory, v3 relative-path failure','delivery-v4 before explicit physical/cache margin labels','reproduction-v1 NETLINK_ROUTE denied by ordinary sandbox; identical offline bwrap succeeds on authorized host as v2'],'corrected_semantics':['rotorPre/Post phase','Nav axes independent of initial attitude difference','task0 H0 and D0 preserved','knownbinary32 attitude norm preserved; physicalunitgroup separatelyused','sampleID-based futurecache diagnostic; A-preconditional vs task0explicit','physicalCOM/physicaltilt vs cachedatt/LP task criterion separate'],'no_old_result_rewritten':True})
 tests=(base/'tests-v3.log').read_text();assert '38 passed' in tests
 repro=json.load(open(base/'reproduction-v2/reproduction.json'));assert all(repro['point_arrays_exact_equal'].values()) and repro['tube_first16_rows_exact_equal']
 files=list((ROOT/'tools/p14_motion').glob('*.py'))+list((ROOT/'docs').glob('THOR_P14_MOTION*.md'))+list((ROOT/'docs/figures/p14-motion').glob('*.png'))+[ROOT/'config/p14-motion-offline.json',ROOT/'tests/test_p14_motion.py']
 write(out/'deliverable-hashes.json',{str(p.relative_to(ROOT)):sha(p) for p in files})
 machine=json.load(open(base/'delivery-v5/machine-conclusion.json'));machine.update(preservation=preserve,local_tests={'passed':38,'scope':'targeted P14_motion/P14/P13/P12score','CI':'NOT_EQUIVALENT_TO_LOCAL_TESTS'},independent_reproduction=repro,denominators_path=str(out/'score-denominators.json'),publication='normal commit/push and remote/CI read to follow, stored in local publication receipt',blocked_actions=[])
 write(out/'machine-conclusion.json',machine);print('FINAL_PRESERVATION_PASS',len(bound),len(freeze),'arrays',len(arrays),'tests38')

if __name__=='__main__':main()
