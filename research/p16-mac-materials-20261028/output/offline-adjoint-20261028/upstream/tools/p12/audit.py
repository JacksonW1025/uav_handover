#!/usr/bin/env python3
"""Native achieved phase/history/capture audit, on complete active observations."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from p11.observe import matrix,stats


def audit(run,out):
    out.mkdir(parents=True,exist_ok=False)
    T={x.name:x.data for x in ULog(str(run/'flight.ulg'),['research_p12','research_p11','research_target','research_timing']).data_list if x.multi_id==0}
    d=T['research_p12'];old=T['research_p11'];target=T['research_target'];timing=T['research_timing']
    active=d['active'].astype(bool);d={k:v[active] for k,v in d.items()}
    sample=d['timestamp_sample'].astype(np.int64);os=old['timestamp_sample'][old['active'].astype(bool)].astype(np.int64)
    old={k:v[old['active'].astype(bool)] for k,v in old.items()}
    if not np.array_equal(sample,os):raise RuntimeError('P12/P11 active calls missing or order mismatch')
    index={int(t):i for i,t in enumerate(sample)}
    mean=matrix(d,'history_before',4);after=matrix(d,'history_after',4);prev=matrix(old,'previous_action_before',4)
    n=d['history_count_before'].astype(float)
    expected=(mean*n[:,None]+prev)/(n+1)[:,None]
    x=matrix(old,'policy_input',22)[:,18:]
    count_expected=np.where(d['actual_commit'],0,n+1)
    captures=[]
    for k in np.flatnonzero(target['kind']==1):
        s=int(target['timestamp_sample'][k]);j=index.get(s)
        if j is None:continue
        tp=matrix(target,'position',3)[k];tv=matrix(target,'velocity',3)[k]
        p=matrix(old,'position',3)[j];v=matrix(old,'velocity',3)[j]
        timing_j=np.flatnonzero(timing['timestamp_sample']==s)
        if len(timing_j)!=1:raise RuntimeError('timing sample not unique')
        tj=int(timing_j[0]);lo=int(old['read_wall_ns'][j]);hi=int(timing['control_start_wall_ns'][tj])
        native_age=int(d['timestamp'][j])-int(old['last_valid_read_us'][j]) if old['last_valid_read_us'][j] else None
        activation=bool(target['activation'][k]);mode=int(target['mode'][k])
        actual_phase='CAPTURE_THEN_GRU_COMMIT' if d['actual_commit'][j] else 'CAPTURE_ON_INTERMEDIATE_AFTER_PRIOR_COMMIT'
        captures.append({'sample_us':s,'native_us':int(d['timestamp'][j]),'activation':activation,'mode':mode,
            'phase':actual_phase,'requested_phase':int(d['requested_phase'][j]),'guard_age_us':native_age,
            'last_gru_sample_before':int(d['last_gru_sample_before'][j]),'call_index':int(d['call_index_before'][j]),
            'lp_age_us':s-int(old['local_position_sample'][j]),'attitude_age_us':s-int(old['attitude_sample'][j]),
            'capture_host_interval_ns':[lo,hi],'copy_position_max_m':float(np.max(abs(tp-p))),
            'horizontal_velocity_input_error_m_s':float(np.linalg.norm(v[:2]-tv[:2])),
            'history_count':int(n[j]),'external_seen':bool(d['external_seen'][j]),
            'cross_thread_consumption_order':'use capture bracket with per-motor consume_ns; overlap UNKNOWN'})
    commit=d['actual_commit'].astype(bool);reads=old['external_valid'].astype(bool);phase=d['requested_phase']
    gates={'complete_active':len(sample)>0 and len(np.unique(sample))==len(sample),
        'predicted_actual_commit':bool(np.array_equal(d['predicted_commit'],commit)),
        'history_input':float(np.max(abs(expected-x)))<1e-6,
        'history_after':float(np.max(abs(expected-after)))<1e-6,
        'history_count':bool(np.array_equal(count_expected,d['history_count_after'])),
        'call_index':bool(np.all(d['call_index_after']==d['call_index_before']+1)),
        'read_phase':bool(np.all(commit[reads&(phase==1)]) and not np.any(commit[reads&(phase==2)])),
        'activation_T0':all(c['mode']==0 for c in captures if c['activation']),
        'strict_timeout':all(c['guard_age_us'] is None or c['guard_age_us']>200000 for c in captures if not c['activation']),
        'correlated_position':all(c['copy_position_max_m']<1e-6 for c in captures),
        'repair_only_after_external':all(c['external_seen'] and not c['activation'] for c in captures if c['mode']==2)}
    report={'schema':'p12-native-audit-1','status':'PASS' if all(gates.values()) else 'FAIL',
        'run':str(run),'ulog_sha256':sha(run/'flight.ulg'),'rows':len(sample),'gates':gates,
        'max_history_input_error':float(np.max(abs(expected-x))),'max_history_after_error':float(np.max(abs(expected-after))),
        'valid_reads':int(reads.sum()),'read_commit_count':int(commit[reads].sum()),'read_intermediate_count':int((~commit[reads]).sum()),
        'gate_delays_pending_calls':int(np.sum(d['gate_pending']&~d['gate_permit'])),
        'captures':captures,'actual_capture_phases':sorted({c['phase'] for c in captures if not c['activation']}),
        'native_phase_scope':'achieved calls/captures, not host-send intent; late terminal capture retained',
        'history_state_directly_observed':True}
    np.savez_compressed(out/'history.npz',sample_us=sample,history_before=mean,history_after=after,
        count_before=n,count_after=d['history_count_after'],call_before=d['call_index_before'])
    write(out/'native-audit.json',report);print(json.dumps({'status':report['status'],'gates':gates,'phases':report['actual_capture_phases'],'captures':len(captures)}));return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=audit(a.run,a.output);raise SystemExit(r['status']!='PASS')
