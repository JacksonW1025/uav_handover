#!/usr/bin/env python3
"""Independently re-check a finished P1 batch from raw run evidence and summarize it; never modifies runs.

Per run: P0 audit checks (PX4 exit, crash markers, ULog hash, analyzer verdict, all recovery stages, executor,
trace), per-motor output-chain gate, and a fresh recomputation of p1-metrics compared with the stored file.
Batch: output-chain overwrite fraction, per (subject, condition) summaries, and repeatability of repeats.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from preparation_audit import flight
from p0_closure import GATE
from p1_batch import chain_gate
import p1_metrics
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def summary(values):
    a=np.array([v for v in values if v is not None],float)
    if not len(a):return None
    return {'n':int(len(a)),'mean':float(a.mean()),'min':float(a.min()),'max':float(a.max()),'spread':float(a.max()-a.min())}

def row_of(m):
    pr=m['primary'];au=m['auxiliary'];jr=pr['joint_recovery'];ref=m['reference_at_takeover']
    return {'speed_at_change_m_s':m['state_at_change']['horizontal_speed_m_s'],'max_altitude_loss_m':pr['max_altitude_loss_m'],
        'recovery_status':jr['status'],'recovery_from_change_s':jr['from_change_s'],'recovery_from_trigger_s':jr['from_trigger_s'],
        'constraints_satisfied':pr['window_constraints_all_satisfied'],
        'violated':[k for k,v in pr['window_constraints'].items() if not v['satisfied']],
        'max_tilt_deg':pr['window_constraints']['tilt_hover_deg']['max'],
        'max_error_to_active_target_m':au['max_position_error_to_active_target_m'],
        'max_deviation_from_final_target_m':au['max_deviation_from_final_target_m'],
        'overshoot_along_axis_m':au['overshoot_past_final_target_along_axis_m'],
        'motor_step_at_change':au['motor']['step_at_change'],'motor_max_step_window':au['motor']['max_step_in_window'],
        'saturation_any_s':au['motor']['saturation_any_s'],'saturation_upper_s':au['motor']['saturation_upper_s'],'saturation_lower_s':au['motor']['saturation_lower_s'],
        'trigger_to_change_ms':m['delays_ms']['trigger_to_change'],'trigger_to_nav_state_ms':m['delays_ms']['trigger_to_nav_state'],
        'reference_classification':ref.get('classification'),'reference_position_ned_m':ref.get('position_ned_m'),
        'reference_velocity_ned_m_s':ref.get('velocity_ned_m_s'),'fingerprint':m['fingerprint_sha256']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);args=p.parse_args()
    batch=args.batch.resolve();results=json.loads((batch/'results.json').read_text());runs=[]
    for r in results['runs']:
        run=ROOT/r['directory']
        if r['status']=='NOT_RUN' or not run.exists():continue
        a={'id':r['id'],'kind':r['kind'],'condition':r['condition'],**flight(run,r['kind'])}
        oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
        a['output_chain_gate_errors']=chain_gate(oc) if oc else ['missing']
        a['output_chain_counts']={'steps':sum(v['neural']['steps'] for v in oc.get('motors',{}).values()),
            'overwritten':sum(v['neural']['commands_overwritten_in_gazebo'] for v in oc.get('motors',{}).values())+4*(oc.get('px4_overwritten_publications',{}).get('neural_bracketed') or 0)} if oc else None
        stored=json.loads((run/'p1-metrics.json').read_text()) if (run/'p1-metrics.json').exists() else None
        fresh=json.loads(json.dumps(p1_metrics.analyze(run),allow_nan=False))
        a['p1_metrics_reproduced']=stored==fresh;a['p1_status']=fresh['status'];a['p1_problems']=fresh.get('problems')
        a['p1']=row_of(fresh) if fresh['status']=='MEASURED' else None
        a['passed']=a['passed'] and not a['output_chain_gate_errors'] and a['p1_metrics_reproduced'] and fresh['status']=='MEASURED'
        runs.append(a)
    steps=sum(r['output_chain_counts']['steps'] for r in runs if r['output_chain_counts']);over=sum(r['output_chain_counts']['overwritten'] for r in runs if r['output_chain_counts'])
    groups={}
    for r in runs:
        if r['p1']:groups.setdefault(r['kind'],{}).setdefault(r['condition'],[]).append(r)
    table={}
    keys=['speed_at_change_m_s','max_altitude_loss_m','recovery_from_change_s','recovery_from_trigger_s','max_tilt_deg','max_error_to_active_target_m',
          'max_deviation_from_final_target_m','overshoot_along_axis_m','motor_step_at_change','motor_max_step_window','saturation_any_s','trigger_to_change_ms']
    for kind,conds in groups.items():
        for cond,rows in conds.items():
            prints=[x['p1']['fingerprint'] for x in rows]
            table.setdefault(kind,{})[cond]={'runs':len(rows),'settled':sum(x['p1']['recovery_status']=='SETTLED' for x in rows),
                'constraints_satisfied':sum(bool(x['p1']['constraints_satisfied']) for x in rows),
                'violations':sorted({v for x in rows for v in x['p1']['violated']}),
                'reference_classifications':sorted({x['p1']['reference_classification'] for x in rows}),
                **{k:summary([x['p1'][k] for x in rows]) for k in keys},
                'repeatability':{'identical_trajectory_fingerprints':len(set(prints))<len(prints),'distinct_fingerprints':len(set(prints)),
                    'all_identical':len(set(prints))==1,'note':'fingerprint = SHA-256 of the first 500 local-position samples after the change'}}
    handovers=[r for r in runs if r['kind'] in ['p1_c_to_n','p1_n_to_c']]
    out={'batch':str(batch.relative_to(ROOT)),'audit_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['p1_audit.py','p1_metrics.py','p0_metrics.py','recovery.py','preparation_audit.py']},
        'runner_results':{k:results[k] for k in results if k!='runs'},
        'output_chain':{'gate':GATE,'neural_motor_steps':steps,'overwritten_motor_commands':over,'overwritten_fraction':over/steps if steps else None,
            'fraction_gate_met':bool(steps) and over/steps<GATE['overwritten_fraction'],'per_run_gate_failures':[r['id'] for r in runs if r['output_chain_gate_errors']]},
        'runs_checked':len(runs),'handovers_checked':len(handovers),'all_runs_passed':bool(runs) and all(r['passed'] for r in runs),
        'summary':table,'runs':runs,
        'scope':'Exploratory P1 batch on one frozen candidate, headless SITL only. Repeats share seed and configuration; identical fingerprints mean repeated runs are not independent samples.'}
    out['passed']=out['all_runs_passed'] and out['output_chain']['fraction_gate_met'] and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged')
    (batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print('runs',len(runs),'passed',out['passed']);return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
