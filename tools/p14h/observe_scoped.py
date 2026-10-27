"""P14H canonical state coverage from P11+same-call direct-read identities.
Legacy Timing topic is auxiliary when only its shutdown tail is missing. Never
bridge an interior state gap or invent the absent timing/overhead/counter row.
The original strict P12 analyzer and its FAIL are preserved in full-source-view.
"""
import sys,json,shutil,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from pyulog import ULog
from p12.observe import analyze
from p12b.read_trace import load
from p14.common import write,sha

def main():
 p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False);raw=analyze(a.run,out/'full-source-view');s=dict(np.load(out/'full-source-view/synchronized.npz'));ts=s['sample_us'];direct=load(a.run/'gz-motor/read-p12b.bin');di=direct['active'].astype(bool)&(direct['timestamp_sample']>=ts[0])&(direct['timestamp_sample']<=ts[-1]);expected=direct['timestamp_sample'][di];timing=next(x.data for x in ULog(str(a.run/'flight.ulg'),['research_timing']).data_list);sel=timing['active'].astype(bool)&timing['executor_called'].astype(bool)&timing['control_step'].astype(bool);aux=timing['timestamp_sample'][sel];extra=np.setdiff1d(ts,aux);missing=np.setdiff1d(aux,ts);gates={k:v for k,v in raw['gates'].items() if k!='all_control_calls'};gates['all_control_calls']=bool(np.array_equal(ts,expected) and not len(missing) and (not len(extra) or np.all(extra>aux[-1])))
 report=json.loads(json.dumps(raw));report.update(schema='P14H-critical-state-observation-1',status='PASS' if all(gates.values()) and not raw['problems'] else 'FAIL',gates=gates,legacy_full_run_status=raw['status'],legacy_timing_coverage=raw['coverage'],coverage={**raw['coverage'],'reference':'same-call P12b direct active rows inP11 state-covered interval','direct_control_calls':len(expected),'missing':len(np.setdiff1d(expected,ts)),'extra':len(np.setdiff1d(ts,expected))},unobserved_auxiliary_timing_tail_sample_us=extra.tolist(),auxiliary_timing_tail_fields='UNKNOWN: source_generation/lifetimecounter/cycleoverhead, never synthesized. Neural/capture/history/cache/native/sample identity is directly recorded independently. Full-run strictlegacyFAIL retained.',scope='all criticalP11/direct state-covered controlcalls, plus only actuallyobservedTimingoverhead; safeincomplete predictions UNKNOWN andscientific failurewitness kept')
 shutil.copyfile(out/'full-source-view/synchronized.npz',out/'synchronized.npz');manifest=json.load(open(out/'full-source-view/source-manifest.json'));manifest.update(analysis_scope='P14H criticalP11/direct canonical',original_analysis_status=raw['status'],original_report_sha256=sha(out/'full-source-view/observation.json'),auxiliary_tail_missing=extra.tolist());write(out/'source-manifest.json',manifest);write(out/'observation.json',report);print('P14H_OBSERVATION',report['status'],'criticalcalls',len(ts),'auxTimingtailunknown',extra.tolist())
 if report['status']!='PASS':raise RuntimeError('criticalstateinteriorlossorotherobservationfailure; no tailrepair')
if __name__=='__main__':main()
