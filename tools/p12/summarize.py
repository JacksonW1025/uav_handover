#!/usr/bin/env python3
"""No-flight P12 evidence consolidation into a NEW directory; never changes old runs."""
import argparse,csv,hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from p12.execution import DTYPE
from p11.models import speeds


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output;out.mkdir(parents=True,exist_ok=False);prep=ROOT/'data/p12-20261026-preparation';analysis=ROOT/'data/p12-20261026-analysis'
    ledger=[json.loads(s) for s in (prep/'attempts.jsonl').read_text().splitlines()];starts=[r for r in ledger if r['event']=='START_INTENT']
    names=[r['id'] for r in starts];cases={};raw=[];hash_cache={};ordering=[]
    for name in names:
        base=ROOT/'data/p12-20261026-development'/name;run=base/'run'
        meta=json.loads((run/'metadata.json').read_text());cfg=json.loads((run/'config.json').read_text());wrapper=json.loads((base/'wrapper-result.json').read_text())
        measured=json.loads((analysis/(name+'-measured/measurement.json')).read_text())
        observed=json.loads((analysis/(name+'-observation/observation.json')).read_text())
        d=dict(np.load(analysis/(name+'-observation/synchronized.npz')))
        cases[name]={'protocol':cfg['p12']['schema'],'wrapper_infrastructure_ok':wrapper['infrastructure_ok'],
            'candidate_unchanged':wrapper['candidate_unchanged'],'frozen_flight_outcome':measured['frozen_flight_outcome'],
            'task_outcome':measured['task_outcome'],'whole':measured['whole'],'censored':measured['censored'],
            'observation_status':observed['status'],'continuous_action_error':observed['continuous']['action_max'],
            'control_calls':observed['coverage']['observed_control_calls'],
            'native_plateaus':observed['clock']['dual_clock_edges']['plateaus'],
            'native_jumps_or_catchup':len(observed['clock']['dual_clock_edges']['exceptions']),
            'cycle_p99_us':observed['baseline']['whole_observation_cycle_us']['p99'],
            'binary_sha256':meta['binary_sha256'],'policy_sha256':meta['policy_sha256'],
            'world_height_held_min_m':float(np.nanmin(-d['truth_pv'][:,2])),
            'world_height_meaning':'Gazebo world ENU z via held NED groundtruth topic, 20ms samples/transport age retained; observed minimum does not bound unobserved between-sample minimum'}
        if cfg['p12']['observe']:
            native=json.loads((analysis/(name+'-native/native-audit.json')).read_text())
            execution_path=analysis/(name+'-execution/execution.json')
            if name=='dev02-on':execution_path=analysis/(name+'-execution-v2/execution.json')
            execution=json.loads(execution_path.read_text())
            cases[name].update(native_status=native['status'],execution_status=execution['status'],
                actual_phases=native['actual_capture_phases'],valid_reads=native['valid_reads'],
                read_commits=native['read_commit_count'],read_intermediate=native['read_intermediate_count'],
                capture_modes=[{'activation':c['activation'],'mode':c['mode'],'velocity_input_error_m_s':c['horizontal_velocity_input_error_m_s']} for c in native['captures']],
                physical_motor_rows=sum(m['rows'] for m in execution['motors'].values()),
                direct_filter_replay_max=max(m['continuous_max_rad_s'] for m in execution['motors'].values()),
                joint_filter_difference_max_rad_s=max(max(abs(m['joint_abs_minus_filter_before_rad_s']['min']),abs(m['joint_abs_minus_filter_before_rad_s']['max'])) for m in execution['motors'].values()),
                filter_vs_steady_command_max_rad_s=max(m['filter_vs_steady_command_rad_s']['max'] for m in execution['motors'].values()))
            packed=analysis/(name+'-packed/prediction-input.json')
            if packed.exists():
                initial=json.loads(packed.read_text())['initial']
                cases[name]['M2_steady_initial_filter_error_max_rad_s']=float(np.max(abs(speeds(initial['previous'])-initial['rotor_filter'])))
            for motor in range(4):
                e=np.fromfile(run/f'gz-motor/execution-p12-{motor}.bin',DTYPE)
                for capture in native['captures']:
                    if capture['activation']:continue
                    lo,hi=capture['capture_host_interval_ns'];hit=np.flatnonzero(e['sim_us']==capture['sample_us'])
                    same='NO_MATCHING_PHYSICAL_ROW'
                    if len(hit)==1:
                        wall=int(e['consume_ns'][hit[0]])
                        same='BEFORE_CAPTURE_BRACKET' if wall<lo else 'AFTER_CAPTURE_BRACKET' if wall>hi else 'OVERLAPS_UNKNOWN'
                    applied=np.flatnonzero(e['sample_us']==capture['sample_us'])
                    selected='NOT_CONSUMED_LATEST_VALUE' if not len(applied) else ('AFTER_CAPTURE_BRACKET' if int(e['consume_ns'][applied[0]])>hi else 'OVERLAPS_OR_PRIOR_REQUIRES_REVIEW')
                    ordering.append({'case':name,'motor':motor,'capture_sample':capture['sample_us'],
                        'same_physics_step_consumption':same,'command_from_capture_call_first_consumption':selected,
                        'capture_bracket_ns':[lo,hi]})
        score=analysis/(name+'-score/score.json')
        if score.exists():
            report=json.loads(score.read_text())
            cases[name]['predictions']={key:{k:v.get(k) for k in ['peak_abs_error_deg','position_norm_m','risk_comparison','task_risk_comparison','event_windows']} for key,v in report['models'].items()}
        paths=[run/'flight.ulg',run/'telemetry.jsonl',run/'resources.jsonl',run/'p11-sends.jsonl']
        paths+=list((run/'gz-motor').glob('*.bin'))+list((run/'rootfs/log').glob('**/*.ulg'))
        for file in paths:
            st=file.stat();key=(st.st_dev,st.st_ino)
            if key not in hash_cache:hash_cache[key]=sha(file)
            raw.append({'path':str(file.relative_to(ROOT)),'bytes':st.st_size,'allocated_bytes':st.st_blocks*512,
                'device':st.st_dev,'inode':st.st_ino,'sha256':hash_cache[key],
                'matches_metadata_ulog':hash_cache[key]==meta['ulog_sha256'] if file.suffix=='.ulg' else None})
    write(out/'cases.json',cases);write(out/'raw-data-manifest.json',{'files':raw,'unique_inodes':len(hash_cache),'policy':'all raw paths retained locally; hardlinks never double counted; no raw in Git'})
    write(out/'capture-consumption-order.json',{'rows':ordering,'meaning':'cross-thread host brackets; overlap is unknown, never ordered using equal sample labels alone'})
    off=cases['dev02-off-final'];on=cases['dev02-on']
    gates={'same_binary_off_on':off['binary_sha256']==on['binary_sha256'],
        'off_on_peak_difference':abs(off['whole']['max_tilt_deg']-on['whole']['max_tilt_deg'])<=2.5,
        'cycle_p99':all(c['cycle_p99_us']<2500 for c in cases.values()),
        'observation_replay':all(c['observation_status']=='PASS' for c in cases.values()),
        'enabled_native_and_execution':all(c.get('native_status','PASS')==c.get('execution_status','PASS')=='PASS' for c in cases.values()),
        'policy_unchanged':len({c['policy_sha256'] for c in cases.values()})==1,
        'raw_ulog_metadata':all(r['matches_metadata_ulog'] is not False for r in raw)}
    pair=json.loads((analysis/'pair-feasibility-3.json').read_text());stop=json.loads((prep/'formal-design-stop.json').read_text())
    conclusion={'schema':'p12-conclusion-1','execution_status':'STOPPED_AT_DEVELOPMENT_PAIR_GATE_NO_FORMAL_FREEZE',
        'budget':{'development_starts':len(starts),'development_cap':12,'formal_starts':0,'formal_cap':48,'total_cap':60},
        'engineering_observation_gates':gates,'engineering_observation_status':'PASS' if all(gates.values()) else 'FAIL',
        'actual_native_phase_classes_identified':True,'phase_effect_on_flight_causally_identified':False,
        'reliable_combination_failure_evidence':False,'combination_response':'NOT_ESTIMABLE_NORMAL_A_B_ARMS_NOT_STARTED',
        'prestate_feasible_pairs':sum(p['status']=='FEASIBLE_SUBSYSTEM_PAIR' for p in pair['pairs']),
        'pairs_tested':len(pair['pairs']),'formal_stop':stop,
        'primary_failures':sum(c['frozen_flight_outcome']['outcome']=='FAILURE' for c in cases.values()),
        'task_failures':sum(c['task_outcome']=='FAILURE' for c in cases.values()),'censored':sum(c['censored'] for c in cases.values()),
        'empirical_prediction_scope':'all development/previously seen sources; isolated autonomous simulations and known-input replay separated; no formal heldout validation',
        'theory_status':'SOURCE_SUBSYSTEM_INCREMENTAL_RELATIONS_PROVED; FULL_FEEDBACK_STORAGE_AND_ACTUAL_COVERAGE_NOT_ESTABLISHED',
        'A4_counterexample':'NOT_PROVEN_EXCLUDED','clock70':'new offline diagnostic only; old P11 validity/STOP/pending unchanged',
        'CI':'separately query after normal push; local tests are not CI'}
    write(out/'conclusion.json',conclusion)
    with (out/'startup-ledger.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['id','budget_class','ordinal','input_sha256','status']);writer.writeheader()
        for row in starts:writer.writerow({k:row[k] for k in ['id','budget_class','ordinal','input_sha256']}|{'status':'FINISHED_DEVELOPMENT'})
    write(out/'formal-unstarted-ledger.json',json.loads((ROOT/'config/p12.json').read_text())['formal_slots'])
    print(json.dumps({'starts':len(starts),'formal':0,'gates':gates,'pairs_feasible':conclusion['prestate_feasible_pairs'],'raw_files':len(raw)}))


if __name__=='__main__':main()
