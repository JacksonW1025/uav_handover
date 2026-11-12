#!/usr/bin/env python3
"""Independently audit a finished preparation batch from raw run evidence; never modifies runs."""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[1]
CRASH=re.compile(r'assertion failed|Assertion|Fatal glibc error|Segmentation fault|SIGSEGV|SIGABRT|Aborted|terminate called|AddressSanitizer|fatal signal',re.I)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def topics(run,names):
    return {d.name:d.data for d in ULog(str(run/'flight.ulg'),names).data_list if d.multi_id==0}
def common(run):
    meta=json.loads((run/'metadata.json').read_text())
    stops=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()]
    stops=[e for e in stops if e['event']=='process_stopped']
    log=(run/'logs/px4.log').read_text(errors='replace')
    return meta,{'directory':str(run.relative_to(ROOT)),'px4_exit_codes':[e['exit_code'] for e in stops if e['name']=='px4'],
        'crash_markers':sorted({x.lower() for x in CRASH.findall(log)}),'ulog_sha256_matches':sha(run/'flight.ulg')==meta.get('ulog_sha256'),
        'GZ_IP':meta['environment'].get('GZ_IP'),'capture_raw_sensors':meta['capture_raw_sensors'],
        'process_names':sorted({p['name'] for p in meta['processes']})}
def startup(run):
    meta,row=common(run)
    t=topics(run,['vehicle_status','sensor_baro','vehicle_air_data'])
    row['armed_seen']=bool(np.any(t['vehicle_status']['arming_state']==2)) if 'vehicle_status' in t else None
    row['raw_sensor_observers_started']=meta['capture_raw_sensors'] or any(n.startswith('gz-topic') or 'raw' in n for n in row['process_names'])
    commands=[json.loads(s) for s in (run/'logs/commands.log').read_text().splitlines()]
    row['callbacks']=[{k:int(v) for k,v in re.findall(r'(imu|baro|mag)=(\d+)',c['output'])} for c in commands if 'Research callbacks' in c['output']]
    info=(run/'logs/gazebo-imu_sensor-info.txt').read_text()
    addresses=re.findall(r'tcp://([\d.]+):\d+',info)
    row['loopback_imu_endpoints']=bool(addresses) and all(a=='127.0.0.1' for a in addresses)
    row['imu_subscribers']=len(re.findall(r'tcp://[\d.:]+, gz.msgs.IMU',info.split('Subscribers')[-1])) if 'Subscribers' in info else 0
    row['sensor_baro_rows']=len(t.get('sensor_baro',{}).get('timestamp',[]));row['vehicle_air_data_rows']=len(t.get('vehicle_air_data',{}).get('timestamp',[]))
    row['passed']=(row['px4_exit_codes']==[0] and not row['crash_markers'] and row['ulog_sha256_matches'] and row['armed_seen'] is False
        and not row['raw_sensor_observers_started'] and row['GZ_IP']=='127.0.0.1' and row['loopback_imu_endpoints'] and row['imu_subscribers']==1
        and bool(row['callbacks']) and all(c.get(k,0)>0 for c in row['callbacks'] for k in ['imu','baro','mag'])
        and row['sensor_baro_rows']>0 and row['vehicle_air_data_rows']>0)
    return row
def flight(run,kind):
    meta,row=common(run)
    if not (run/'metrics.json').exists():
        row.update({'validation':json.loads((run/'validation.json').read_text())['status'] if (run/'validation.json').exists() else None,'metrics_missing':True,'passed':False});return row
    v=json.loads((run/'validation.json').read_text());m=json.loads((run/'metrics.json').read_text())
    row.update({'validation':v['status'],'analysis':v.get('analysis_status'),'recovery_status':m.get('recovery_status'),
        'joint_recovery_status_counts':m.get('joint_recovery_status_counts'),'executor_acceptance':m.get('executor_acceptance'),
        'executor_warnings_whole_run':m.get('executor_warning_count'),
        'first_recovery_uncertain_stages':sum(bool(s.get('joint_recovery',{}).get('true_first_recovery_uncertain')) for s in m.get('recovery_stages',[]))})
    if kind!='classic_hover':
        trace=json.loads((run/'preparation-trace.json').read_text())
        neural=trace['observations'].get('neural_publication',{});b=trace['bridge']
        row['trace']={'status':trace['status'],'publish_sim_age_max_us':(neural.get('publish_sim_age_us') or {}).get('max'),
            'run_sim_age_max_us':(neural.get('run_sim_age_us') or {}).get('max'),
            'bridge_age_bins':b.get('age_bins_all_runtime'),'bridge_repeated':b.get('repeated_selected_sample_total'),
            'bridge_regressed':b.get('regressed_selected_sample_total'),'bridge_negative_age':b.get('negative_age_total'),
            'neural_owner_bridge_age_max_us':(b.get('neural_owner_interval_age_us_logged') or {}).get('max')}
    if (run/'output-chain.json').exists():
        c=json.loads((run/'output-chain.json').read_text());m0=c['motors'].get('0',{}).get('neural',{})
        row['output_chain']={'status':c['status'],'neural_steps':m0.get('steps'),'neural_hold_steps':m0.get('hold_steps'),
            'neural_gazebo_overwritten':m0.get('commands_overwritten_in_gazebo'),'neural_over_target_steps':m0.get('over_target_steps'),
            'neural_applied_age_max_us':(m0.get('applied_age_us') or {}).get('max'),'neural_longest_over_target_steps':m0.get('longest_over_target_steps'),
            'px4_overwritten_neural':c.get('px4_overwritten_publications',{}).get('neural_bracketed'),'motors_disagree_steps':c.get('motors_disagree_steps'),
            'neural_published_not_applied_logged':c.get('neural_published_actions_logged',{}).get('not_applied')}
    row['passed']=(row['px4_exit_codes']==[0] and not row['crash_markers'] and row['ulog_sha256_matches'] and row['validation'] in ['PASS','PASS_WITH_WARNINGS']
        and row['recovery_status']=='PASS' and (row['executor_acceptance'] in ['PASS','PASS_WITH_WARNINGS'] or (kind=='classic_hover' and row['executor_acceptance'] is None))
        and row['GZ_IP']=='127.0.0.1' and not row['capture_raw_sensors'] and (kind=='classic_hover' or row['trace']['status']=='MEASURED'))
    return row
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);p.add_argument('--output',type=Path,help='default: <batch>/batch-audit.json');args=p.parse_args()
    batch=args.batch.resolve();results=json.loads((batch/'results.json').read_text())
    starts=[];flights=[]
    for r in results['runs']:
        run=ROOT/r['directory']
        if r['status']=='NOT_RUN' or not run.exists():continue
        (starts if r['startup_only'] else flights).append({'id':r['id'],'kind':r['kind'],**(startup(run) if r['startup_only'] else flight(run,r['kind']))})
    chains=[f['output_chain'] for f in flights if 'output_chain' in f]
    chain_total={k:sum(c[k] or 0 for c in chains) for k in ['neural_steps','neural_hold_steps','neural_gazebo_overwritten','neural_over_target_steps','px4_overwritten_neural','motors_disagree_steps','neural_published_not_applied_logged']} if chains else None
    if chains:
        chain_total.update({'runs':len(chains),'all_measured':all(c['status']=='MEASURED' for c in chains),
            'neural_applied_age_max_us':max(c['neural_applied_age_max_us'] or 0 for c in chains),
            'neural_longest_over_target_steps':max(c['neural_longest_over_target_steps'] or 0 for c in chains)})
    bins={}
    for f in flights:
        for k,v in (f.get('trace') or {}).get('bridge_age_bins',{}).items():bins[k]=bins.get(k,0)+v
    out={'batch':str(batch.relative_to(ROOT)),'audit_code_sha256':sha(Path(__file__)),'runner_results':{k:results[k] for k in results if k!='runs'},
        'startups':{'passed':bool(starts) and all(s['passed'] for s in starts),'count':len(starts),'runs':starts},
        'flights':{'passed':bool(flights) and all(f['passed'] for f in flights),'count':len(flights),
            'joint_recovery_totals':{k:sum((f.get('joint_recovery_status_counts') or {}).get(k,0) for f in flights) for k in ['SETTLED','NOT_SETTLED','INSUFFICIENT_OBSERVATION']},
            'first_recovery_uncertain_stages':sum(f.get('first_recovery_uncertain_stages',0) for f in flights),
            'neural_publish_sim_age_max_us':max([f['trace']['publish_sim_age_max_us'] or 0 for f in flights if 'trace' in f],default=None),
            'bridge_age_bins_sum':bins,'output_chain_totals':chain_total,'runs':flights},
        'scope':'Engineering screen of one frozen candidate. Does not close historical P0 issues, prove root cause, or prove Gazebo motor physics consumption.'}
    (args.output or batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print('startups',out['startups']['passed'],'flights',out['flights']['passed'],out['flights']['joint_recovery_totals'])
    return 0 if out['startups']['passed'] and out['flights']['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
