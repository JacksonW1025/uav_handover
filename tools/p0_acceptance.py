#!/usr/bin/env python3
"""Audit selected P0 runs without modifying their raw logs or existing metrics."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from pyulog import ULog
from analyze import stats,clean
from p0_metrics import dispatch_metrics
KINDS={'classic_hover','raptor_hover','repeated_handover','state_reset','state_hold','state_restore','state_injection'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def audit(selection):
    root=Path(__file__).resolve().parents[1];spec=json.loads(selection.read_text())
    identity=json.loads((root/spec['source_identity']).read_text());out={'runs':{},'unresolved_issues':spec['unresolved_issues']}
    all_ok=set(spec['runs'])==KINDS
    for kind,relative in spec['runs'].items():
        folder=root/relative;raw=root/spec.get('raw_runs',{}).get(kind,relative);v=json.loads((folder/'validation.json').read_text());m=json.loads((folder/'metrics.json').read_text());meta=json.loads((folder/'metadata.json').read_text())
        version_ok=meta['experiment_type']==kind and meta['binary_sha256']==sha(Path(meta['binary'])) and meta['ulog_sha256']==sha(folder/'flight.ulg')
        if kind=='classic_hover':version_ok &= meta['binary_sha256']==identity['classic_binary_sha256'] and meta['source_diff_sha256']==identity['classic_diff_sha256'] and meta['source_commit']==identity['classic_head']
        if kind!='classic_hover':version_ok &= meta['binary_sha256']==identity['raptor_binary_sha256'] and meta['source_diff_sha256']==identity['raptor_diff_sha256'] and meta.get('source_untracked_sha256')==identity['raptor_untracked_sha256'] and meta['policy_sha256']==identity['policy_sha256']
        scope={};cross={};window_ok=True
        if kind!='classic_hover':
            topics={d.name:d.data for d in ULog(str(folder/'flight.ulg')).data_list if d.multi_id==0}
            timing=topics['research_timing'];owner=topics['research_actuator'];t=timing['timestamp'].astype(np.int64)
            idx=np.searchsorted(owner['timestamp'],t,side='right')-1
            owners=np.where(idx>=0,owner['owner'][np.maximum(idx,0)],0)
            called=timing['executor_called'].astype(bool);active=timing['active'].astype(bool)
            # Include the exact action-publication classification too, protecting
            # handover rows whose HRT publication tick advances during inference.
            neural=(owners==1)|timing['actuator_published'].astype(bool)
            mask=called&neural;warnings=int(sum(mask&~timing['executor_ok'].astype(bool)))
            scope={'logged_calls':int(sum(mask)),'warnings_logged':warnings,
                'duration_us_logged':stats(timing['inference_duration_us'][mask]),
                'definition':'backward as-of last actual actuator publisher, union exact neural action publications; HRT ties have tick resolution',
                'p99_budget_proven':bool(sum(mask) and m['executor_scopes']['whole_run']['duration_over_2500us_total']*100<int(sum(mask))),
                'coverage':'logged interval rows; whole-runtime warning total zero proves zero interval warnings despite omitted rows; whole exceedance count bounds missing duration tails'}
            scope.update(dispatch_metrics(timing,neural,stats))
            for name,mask in [('whole_run',np.ones(len(called),bool)),('active',active),('neural_actuator_authority',timing['actuator_published'].astype(bool))]:
                m['executor_scopes'][name].update(dispatch_metrics(timing,mask,stats))
            for is_active in [False,True]:
                for owner_id in [0,1,2]:
                    cm=called&(active==is_active)&(owners==owner_id)
                    cross[f'active={is_active},owner={owner_id}']={'logged_calls':int(sum(cm)),
                        'executor_warnings_logged':int(sum(cm&~timing['executor_ok'].astype(bool))),
                        'duration_us_logged':stats(timing['inference_duration_us'][cm])}
            window_ok=warnings==0 and scope['p99_budget_proven']
            if m['executor_warning_count'] and m['state_advancement']['log_omitted_accepted_rows_between_first_and_last']:
                window_ok=False;scope['uncertainty']='nonzero runtime warnings plus omitted rows prevent proving ownership-interval warning attribution'
        passed=v['status'] in ['PASS','PASS_WITH_WARNINGS'] and m['status']==v['status'] and version_ok and window_ok
        out['runs'][kind]={'directory':relative,'raw_directory':str(raw.relative_to(root)),'status':m['status'],'audit_pass':bool(passed),'version_hashes_match':bool(version_ok),
            'native_window_clock':m.get('hover_window_clock'),'request_boundary_status':m.get('request_boundary_status'),
            'joint_recovery_status_counts':m.get('joint_recovery_status_counts'),
            'executor_scopes':m.get('executor_scopes'),'neural_ownership_interval_logged':scope,'activity_authority_cross_table':cross,
            'audit_code_sha256':{n:sha(root/'tools'/n) for n in ['p0_acceptance.py','p0_metrics.py','recovery.py','analyze.py']},
            'metadata_sha256':sha(folder/'metadata.json'),'metrics_sha256':sha(folder/'metrics.json'),'ulog_sha256':sha(folder/'flight.ulg')}
        all_ok &= passed
    all_ok &= not any(x['status']=='OPEN' for x in out['unresolved_issues'])
    out['p0_complete']=bool(all_ok);out['status']='PASS' if all_ok else 'FAIL'
    target=selection.parent/'acceptance.json';target.write_text(json.dumps(clean(out),indent=2,ensure_ascii=False)+'\n')
    print(out['status'],target);return 0 if all_ok else 1
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('selection',type=Path)
    raise SystemExit(audit(p.parse_args().selection))
