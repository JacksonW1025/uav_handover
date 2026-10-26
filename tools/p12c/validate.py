#!/usr/bin/env python3
"""Read-only continuation audit into a new directory, with separate experiment/theory gates."""
import argparse,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write
from p12c.features import load

def validate(run,analysis,output):
 d=load(run,analysis);doc=json.loads((analysis/'packed/prediction-input.json').read_text());first=doc['plan']['common_first_gap_profile_s'];i=(d['t']>=first-.5)&(d['t']<first)
 ages={k:(d['sample_us'][i].astype(np.int64)-d[k][i].astype(np.int64)) for k in ['lp_sample','att_sample']}
 tests={k:json.loads((analysis/f).read_text())['status'] in ['PASS','MEASURED'] for k,f in [('observation','observation/observation.json'),('native','native/native-audit.json'),('execution','execution/execution.json'),('target','target/target-replay.json'),('measurement','measured/measurement.json')]}
 tests['cache_age']=all(np.min(a)>=0 and np.max(a)<=20000 for a in ages.values());tests['finite_prestate']=all(np.isfinite(d[k][i]).all() for k in ['position','velocity','attitude','omega','h_before','previous','mean','exec_filter_after','truth_pv'])
 cfg=json.loads((run/'config.json').read_text());events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
 anchor=[e for e in events if e['event']=='p12_confirmed_native_stream_anchor'];tests['bounded_native_start']=len(anchor)==1
 n=json.loads((analysis/'native/native-audit.json').read_text());m=json.loads((analysis/'measured/measurement.json').read_text())
 if cfg['p12'].get('repair_sample_window'):
  windows=[e for e in events if e['event']=='p12_planned_repair_window']
  tests['sample_window_readback']=len(windows)==1
  if len(windows)==1:
   gate=windows[0]['not_before_sample_ms']*1000
   from pyulog import ULog
   targets=next(x.data for x in ULog(str(run/'flight.ulg'),['research_target']).data_list if x.name=='research_target')
   caps=targets['kind']==1
   tests['no_pre_event_repair']=bool(not np.any((targets['mode'][caps]==2)&(targets['timestamp_sample'][caps]<gate)))
   tests['repair_matches_declared_window']=all(c['mode']==(2 if cfg['p12']['repair'] and not c['activation'] and c['external_seen'] and c['sample_us']>=gate else 0) for c in n['captures'])
   tests['no_startup_repair']=all(c['mode']==0 for c in n['captures'] if (c['capture_host_interval_ns'][0]-d['run_wall_ns'][0])/1e9<d['t'][0]*-1)

 # Identify actual treatment delivery on the common absolute task axis.
 epoch=d['run_wall_ns'][0]-d['t'][0]*1e9
 capture_t=[(float(np.mean(c['capture_host_interval_ns']))-epoch)/1e9 for c in n['captures'] if not c['activation']]
 planned=doc['plan']['windows_profile_s'];stream_end=doc['plan']['stream_end_profile_s']
 event_counts=[sum(a<=t<b+.1 for t in capture_t) for a,b in planned]
 tests['reached_complete_event_captures']=all(count==1 for (a,b),count in zip(planned,event_counts) if d['t'][-1]>=b+.1)
 tests['no_unplanned_task_capture']=not any(first<=t<stream_end-.05 and not any(a<=t<b+.1 for a,b in planned) for t in capture_t)
 result={'schema':'p12-cont-engineering-gate-1','engineering_status':'PASS' if all(tests.values()) else 'FAIL','tests':tests,'pre_event_rows':int(i.sum()),'cache_ages_us':{k:sorted(np.unique(a).tolist()) for k,a in ages.items()},'assigned_phase':cfg['p12']['phase'],'actual_captures':n['captures'],'whole':m['whole'],'task_outcome':m['task_outcome'],'censored':m['censored'],'theory_gate':{'status':'NOT_PROVEN_FULL_FEEDBACK','experimental_stop':False,'first_unclosed_connection':'finite solver impulse/residual domain then body/estimator cache feedback; observed residual is not a future bound'},'run':str(run),'strict_same_initial_state':False}
 write(output,result);print(json.dumps({'engineering':result['engineering_status'],'tests':tests,'cache_ages_us':result['cache_ages_us']}));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--analysis',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError(a.output)
 raise SystemExit(validate(a.run,a.analysis,a.output)['engineering_status']!='PASS')
