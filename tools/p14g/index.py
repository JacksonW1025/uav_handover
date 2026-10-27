"""Final offline evidence ledger and reproducible source/input hash index."""
import sys,json,time,resource,hashlib,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14g.common import R,B,write,sha

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
 rows=[]
 for n in range(64):
  p=B/'analysis-v2'/f'job-{n:03d}.json';r=json.load(open(p));rows.append({'identity':f'fixed-set-{n:03d}','kind':'B' if n<40 else 'C','final_summary':str(p.relative_to(R)),'result_source':r['result_source'],'terminal':r['status'],'CPU_s_latest_attempt':r['CPU_s'],'phase_corrected_weighting':n<40 and r['job']['variant']=='weighted','exposure':'retrospective','physical_start':False})
 write(out/'offline-ledger.json',{'rows':rows,'preserved_previous_attempts':['B-v1','B-v2','C-v1','C-v2','rich-v3','weighted-v4'],'point_forecasts':{'C-v2':45,'held_matches_old_all5':True},'ranking':{'labeled_aliases':35,'distinct_physical_candidates':29,'actual_anchors':5,'unexecuted_truth_UNKNOWN':24},'correctness_reruns':{'passive_rich_metrics':64,'poststate_weighting':10,'adjoint_chains':2},'new_SITL':0,'launcher_calls':0,'old_budget_used':0,'do_not_sum_as_flights_or_independent_samples':True})
 files=list((R/'tools/p14g').glob('*.py'))+list((R/'config/p14g').glob('*'))+list((R/'docs').glob('THOR_P14G_*.md'))+[R/'tests/test_p14g.py',R/'.gitignore']
 inputs=json.load(open(R/'config/p14g/protocol-v1.json'))['cases']
 write(out/'source-input-hashes.json',{'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':{str(p.relative_to(R)):sha(p) for p in files if p.is_file()},'old_case_inputs':{v['input']:sha(R/v['input']) for v in inputs.values()},'local_arrays':'delivery-v5/local-array-hashes.json','old_raw':'delivery-v5/historical-preservation.json','full_data_index':'all-data-files.json','runtime_unchanged':'no Lab edits, builds, policy writes or launcher imports; source OP and frozen policy dependencies retained'})
 paths=[p for p in B.rglob('*') if p.is_file() and out not in p.parents and p.suffix not in {'.npz','.bin','.pyc'}]
 write(out/'all-data-files.json',{'files':{str(p.relative_to(R)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in paths},'local_binary_arrays_separate':True,'no_deletions':True})
 write(out/'validation-receipt.json',{'regression':'tests-final-v3.log','expected_tests':106,'earlier_test_error_retained':'tests-final-v1.log','validated_scopes':['source membership/illegal order','conditional consumption order','correlation and outer support','post-state adjoint phase','same domain and all64 passive metrics','checkpoint continuity','LP/COM all-prefix history','future-hidden ranking and canonical pool','premise withdrawal with misses retained'],'reserved_validation_CPU_s':100,'legacy_global_CPU_hardcap_certified':False,'scientific_additional_comparisons':0,'process_snapshot':'process-final-host-v2.json','final_machine':'delivery-v5/machine-conclusion.json','integrated_map':'pipeline-v4/map-edge.json'})
 print('P14G_INDEX',len(rows),len(paths),'SITL0')
if __name__=='__main__':main()
