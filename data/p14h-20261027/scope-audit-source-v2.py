"""Independent P14H model-window audit; original full-run FAIL is retained.
No miss is erased: pre-initial latest-value skips become observed initial data,
while every active source sample and counter delta must still be exact.
"""
import json,numpy as np
from pathlib import Path
from pyulog import ULog
from p12b.read_trace import load as read_direct
from p14h.snapshot import read
from p14h.common import write,sha

def audit(run,analysis,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);old=json.load(open(analysis/'engineering.json'));u=ULog(str(run/'flight.ulg'),['research_timing']);t=next(x.data for x in u.data_list if x.name=='research_timing');active=t['active'].astype(bool);ix=np.flatnonzero(active);assert len(ix)>1;lo,hi=int(ix[0]),int(ix[-1]);span=np.arange(max(0,lo-1),hi+1);sel=t['executor_called'][ix].astype(bool);j=ix[sel];names=['source_missed_total','duplicate_total','regressed_total'];jumps=[]
 for name in names:
  a=t[name].astype(np.int64);k=np.flatnonzero(np.diff(a,prepend=a[0])!=0)
  jumps.extend({'counter':name,'row':int(k0),'timestamp':int(t['timestamp'][k0]),'sample_us':int(t['timestamp_sample'][k0]),'active':bool(active[k0]),'increment':int(a[k0]-a[k0-1])} for k0 in k)
 counter_delta={k:int(t[k][hi])-int(t[k][max(0,lo-1)]) for k in names};direct=read_direct(run/'gz-motor/read-p12b.bin');di=direct['active'].astype(bool);ds=direct['timestamp_sample'][di].astype(np.int64);tests={'all_other_original_gates':all(v for k,v in old['tests'].items() if k!='sample_no_loss'),'active_contiguous':bool(np.all(active[lo:hi+1])),'active_counters_no_increment':all(x==0 for x in counter_delta.values()),'active_source_samples4ms':bool(np.all(np.diff(t['timestamp_sample'][j].astype(np.int64))==4000)),'direct_sequence_complete':bool(np.array_equal(direct['sequence'],np.arange(len(direct['sequence'])))),'direct_active_samples4ms':bool(np.all(np.diff(ds)==4000)),'direct_matches_active_ULog':bool(np.array_equal(ds,t['timestamp_sample'][j]))}
 a,h=read(run/'gz-motor/ekf-p14h.bin');begin=int(min(direct['pre_read_wall_ns'][di]));end=int(max(direct['pre_read_wall_ns'][di]));tests.update(fullP_no_overflow=h['dropped']==h['errors']==0,fullP_active_coverage=bool(a['wall_ns'][0]<=begin and a['wall_ns'][-1]+16000000>=end),fullP_state_dimensions=bool(np.all(a['ndof']==24) and np.all(a['nstate']==25)),fullP_finite=bool(np.isfinite(a['covariance'][:,:24,:24]).all()))
 result={'schema':'P14H-neural-initial-value-scope-2','status':'PASS_FOR_NEURAL_SCOPE' if all(tests.values()) else 'NOT_PASSED','original_full_run_status':old['status'],'original_full_run_counter_failure_retained':not old['tests']['sample_no_loss'],'tests':tests,'counter_jumps_all_log':jumps,'active_counter_increment':counter_delta,'active_native_interval':[int(t['timestamp'][lo]),int(t['timestamp'][hi])],'old_fullrun_count':{k:int(t[k][-1]) for k in names},'source_definition':'_sample_missed adds uORB generation gap at mc_raptor callback, includinginactive shadow; a latestvalue skip is not evidence ofmissingloggedactive samples','initial_semantics':'classicwarmup/shadow skip canchangeactualinitialP/h/history/body; allareobservedatpreA, not normalized/reset/assumedequal. Fullclassic-from-reset replay remainsunresolved.','new_scope_exposure':'defined after d02fullrun counterfailure, retrospective d02; frozen before independent selection validation. No oldFAIL or count rewritten.','measurement':json.load(open(analysis/'measured/measurement.json')),'raw_ulog_sha256':sha(run/'flight.ulg')}
 write(out/'result.json',result)
 if not all(tests.values()):raise RuntimeError('P14H scopeddata invalid '+str([k for k,v in tests.items() if not v]))
 return result
