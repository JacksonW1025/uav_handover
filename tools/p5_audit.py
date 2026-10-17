#!/usr/bin/env python3
"""Independently re-check a finished P5 batch from raw run evidence and summarize it; never modifies runs.

Per run: P0 audit checks (PX4 exit, crash markers, ULog hash, analyzer verdict, recovery, executor, trace), per-motor
output-chain gate, fresh recomputation of every stored metrics file the batch produced (p2_metrics, p4_metrics,
p4c_metrics, p5_metrics), each compared byte-for-byte (as JSON) with the stored file. Batch: per group
(condition x treatment) flight failures and the P5 metrics (E1: flight direction relative to RAPTOR's target yaw,
per-axis clipping, true error magnitude; E2/E3: per-gap timing, capture, target jump vs 0.5*a*D^2 and the exact
prediction, catch-up, per-cycle altitude and lag; E4: N->C window). Exploration: 1-2 runs per cell, values are listed
per run; no statistical conclusions. Only runs of this batch enter the group results.
"""
import argparse,json
from pathlib import Path
from preparation_audit import flight
from p0_closure import GATE
from p2_batch import chain_errors
from p4_audit import stats,fresh,sha
import p2_metrics,p4_metrics,p4c_metrics,p5_metrics
ROOT=Path(__file__).resolve().parents[1]
GAP_KEYS=['silence_s','planned_D_s','catch_up_s','catch_up_search_s','profile_rows','initial_target_speed_m_s','stop_time_s']
RESUME_KEYS=['capture_to_resume_s','jump_along_axis_m','jump_horizontal_m','jump_vertical_m','velocity_jump_along_axis_m_s','velocity_jump_horizontal_m_s',
             'estimate_half_a_D2_m','estimate_half_a_Dcr2_m','offset_at_capture_along_axis_m','prediction_m','t1_stopped_before_resume']

def clip_summary(c):
    if not c:return None
    return {n:{k:(c.get(n) or {}).get(k) for k in ['triggered','duration_s','longest_continuous_s','per_axis_duration_s','both_horizontal_axes_s','first_s','last_s','max_abs_component']} for n in ['position','velocity']}

def run_metrics(kind,f5,fc):
    """Flat per-run values for the group tables."""
    if kind=='p5_gap':
        wh=f5.get('whole') or {};gaps=[]
        for g in f5.get('gaps',[]):
            gaps.append({**{k:g.get(k) for k in GAP_KEYS},'capture_after_last_reception_s':(g.get('capture') or {}).get('after_last_reception_s'),
                'capture_mode':(g.get('capture') or {}).get('mode'),'capture_decel_m_s2':(g.get('capture') or {}).get('decel_m_s2'),
                'captured_speed_m_s':((sum(x*x for x in (g.get('capture') or {}).get('vehicle_velocity_ned_m_s',[0,0])[:2]))**.5) if g.get('capture') else None,
                **{k:(g.get('resume') or {}).get(k) for k in RESUME_KEYS},'window':g.get('window'),'cycle_end':g.get('cycle_end'),
                'observation_first_after_resume':g.get('observation_first_after_resume'),'observation_last_before_capture':g.get('observation_last_before_capture'),
                'clipping_in_gap':clip_summary(g.get('clipping_in_gap')),'clipping_after_resume':clip_summary(g.get('clipping_after_resume'))})
        return {**{k:wh.get(k) for k in ['max_tilt_deg','max_altitude_loss_m','motor_saturation_any_s','motor_longest_continuous_saturation_s','max_angular_rate_rad_s','max_horizontal_radius_m']},
            'settle_after_rest_s':(f5.get('settle_after_rest') or {}).get('settle_time_s'),'joint_recovery_after_final_capture':f5.get('joint_recovery_after_final_capture'),
            'direction':f5.get('direction'),'tracking_before_first_gap':f5.get('tracking_before_first_gap'),'clipping_whole':clip_summary(f5.get('clipping_whole')),
            'gaps':gaps,'aborted':f5.get('aborted'),'failure_reason':f5.get('failure_reason')}
    m=dict(f5.get('metrics') or {});m['direction']=f5.get('direction')
    if kind=='p2_c_to_n':
        m['clipping']=clip_summary(f5.get('clipping'));m['true_error']=f5.get('true_error')
        st=(fc or {}).get('settle') or {};m.update({k:st.get(k) for k in ['settled','settle_time_s','settle_distance_m','settle_distance_along_axis_m','max_travel_along_axis_m']})
        m['target_check']=((fc or {}).get('target') or {}).get('status')
    return m

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);args=p.parse_args()
    batch=args.batch.resolve();results=json.loads((batch/'results.json').read_text());plan=json.loads((batch/'plan.json').read_text())
    planned={r['id']:r for r in plan['runs']};runs=[]
    for r in results['runs']:
        run=ROOT/r['directory']
        if r['status']=='NOT_RUN' or not run.exists():continue
        cfg=json.loads((ROOT/r['config']).read_text())
        a={'id':r['id'],'kind':r['kind'],'condition':r['condition'],'treatment':r['treatment'],'config':r['config'],'sim_seed':planned[r['id']]['sim_seed'],
           'initial_yaw_deg':planned[r['id']]['initial_yaw_deg'],**flight(run,r['kind'])}
        oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
        v=json.loads((run/'validation.json').read_text()) if (run/'validation.json').exists() else {}
        a['output_chain_gate_errors'],a['output_chain_errors_attributed_to_abort']=chain_errors(oc,str(v.get('reason') or '').startswith('safety:'))
        a['output_chain_counts']={'steps':sum(x['neural']['steps'] for x in oc.get('motors',{}).values()),
            'overwritten':sum(x['neural']['commands_overwritten_in_gazebo'] for x in oc.get('motors',{}).values())+4*(oc.get('px4_overwritten_publications',{}).get('neural_bracketed') or 0),
            'max_applied_age_us':max((x['neural'].get('applied_age_us') or {}).get('max') or 0 for x in oc.get('motors',{}).values())} if oc else None
        infra=a['px4_exit_codes']==[0] and not a['crash_markers'] and a['ulog_sha256_matches'] and not a['output_chain_gate_errors'] and (a.get('trace') or {}).get('status')=='MEASURED'
        stored=lambda n:json.loads((run/n).read_text()) if (run/n).exists() else None
        checks={};fc=None;f5={}
        if r['kind'].startswith('p2_'):
            f2=fresh(p2_metrics.analyze(run));checks['p2']=(stored('p2-metrics.json')==f2,f2.get('p2_status')=='MEASURED',f2.get('problems'))
            f4=fresh(p4_metrics.analyze(run));checks['p4']=(stored('p4-metrics.json')==f4,f4['status']=='MEASURED',f4['problems'])
            a['takeover_state']=(f4.get('takeover_state') or {}).get('subject');a['teacher_forcing_coverage']=f4.get('teacher_forcing_coverage');a['planned_path']=f4.get('planned_path')
            a['max_horizontal_radius_m']=f4.get('max_horizontal_radius_m');a['independence']=f4.get('independence')
            a['evidence']={'entry':(f2.get('entry') or {}).get('status'),'teacher_forcing':(f2.get('teacher_forcing') or {}).get('status'),'capture':(f2.get('reference_at_takeover') or {}).get('classification')}
            a['flight_outcome']=(f2.get('flight_outcome') or {}).get('outcome');a['flight_failure_reasons']=(f2.get('flight_outcome') or {}).get('reasons')
            if r['kind']=='p2_c_to_n' and 'p4c' in cfg:
                fc=fresh(p4c_metrics.analyze(run));checks['p4c']=(stored('p4c-metrics.json')==fc,fc['status']=='MEASURED',fc['problems']);a['evidence']['target']=(fc.get('target') or {}).get('status')
        if 'p5' in cfg:
            f5=fresh(p5_metrics.analyze(run));checks['p5']=(stored('p5-metrics.json')==f5,f5['status']=='MEASURED',f5['problems'])
            if r['kind']=='p5_gap':
                a['flight_outcome']=(f5.get('flight_outcome') or {}).get('outcome');a['flight_failure_reasons']=(f5.get('flight_outcome') or {}).get('reasons')
                a['independence']=f5.get('independence');a['max_horizontal_radius_m']=(f5.get('whole') or {}).get('max_horizontal_radius_m')
                a['evidence']={'setup_entry':(f5.get('setup_entry') or {}).get('status'),'gap_problems':[q for g in f5.get('gaps',[]) for q in g.get('problems',[])]}
        a['recomputed']={k:{'reproduced':x[0],'measured':x[1],'problems':x[2]} for k,x in checks.items()}
        ok=bool(checks) and all(x[0] and x[1] for x in checks.values())
        a['metrics']=run_metrics(r['kind'],f5,fc)
        a['flight_failure']=bool(infra and ok and a.get('flight_outcome')=='FAILURE')
        a['passed']=bool(infra and ok and (a['passed'] or a['flight_failure']))
        runs.append(a)
    groups={}
    for r in runs:groups.setdefault(f"{r['kind']}:{r['condition']}:{r['treatment']}",[]).append(r)
    summary={}
    for k,g in sorted(groups.items()):
        s={'runs':len(g),'ids':[r['id'] for r in g],'flight_failures':sum(r['flight_failure'] for r in g),'failure_reasons':[r['flight_failure_reasons'] for r in g if r['flight_failure']]}
        for m in ['max_tilt_deg','max_altitude_loss_m','motor_saturation_any_s','motor_step_at_change','joint_recovery_from_change_s','settle_time_s','settle_after_rest_s']:
            vals=[r['metrics'].get(m) for r in g]
            if any(x is not None for x in vals):s[m]=stats(vals)
        if g[0]['kind']=='p5_gap':
            s['per_gap']=[[{q:gp.get(q) for q in ['silence_s','capture_after_last_reception_s','jump_along_axis_m','velocity_jump_along_axis_m_s','estimate_half_a_D2_m','prediction_m','catch_up_s']}|
                           {'max_tilt_deg':(gp.get('window') or {}).get('max_tilt_deg'),'max_altitude_loss_m':(gp.get('window') or {}).get('max_altitude_loss_m'),
                            'cycle_end':gp.get('cycle_end'),'clipped_after_resume_s':{n:((gp.get('clipping_after_resume') or {}).get(n) or {}).get('duration_s') for n in ['position','velocity']}}
                           for gp in r['metrics']['gaps']] for r in g]
        else:
            s['direction_relative_to_target_yaw_deg']=[(r['metrics'].get('direction') or {}).get('relative_to_target_yaw_deg') for r in g]
            s['clipping']=[r['metrics'].get('clipping') for r in g]
        summary[k]=s
    steps=sum(r['output_chain_counts']['steps'] for r in runs if r['output_chain_counts']);over=sum(r['output_chain_counts']['overwritten'] for r in runs if r['output_chain_counts'])
    seeds=[r['sim_seed'] for r in runs]
    out={'batch':str(batch.relative_to(ROOT)),'config':plan['config'],
        'audit_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['p5_audit.py','p5_metrics.py','p4c_metrics.py','p4_metrics.py','p2_metrics.py','p1_metrics.py','p0_metrics.py','recovery.py','preparation_audit.py']},
        'runner_results':{k:results[k] for k in results if k!='runs'},
        'output_chain':{'gate':GATE,'neural_motor_steps':steps,'overwritten_motor_commands':over,'overwritten_fraction':over/steps if steps else None,
            'fraction_gate_met':bool(steps) and over/steps<GATE['overwritten_fraction'],'per_run_gate_failures':[r['id'] for r in runs if r['output_chain_gate_errors']],
            'max_applied_age_us':max((r['output_chain_counts'] or {}).get('max_applied_age_us',0) for r in runs) if runs else None},
        'runs_checked':len(runs),'all_runs_passed':bool(runs) and all(r['passed'] for r in runs),'flight_failures':[r['id'] for r in runs if r.get('flight_failure')],
        'independence':{'runs':len(runs),'distinct_seeds':len(set(seeds))},'summary':summary,
        'max_horizontal_radius_m':max((r.get('max_horizontal_radius_m') or 0) for r in runs) if runs else None,'runs':runs,
        'scope':'One frozen candidate, headless SITL only, x500, each run its own Gazebo seed; 1-2 runs per cell (exploration, no statistical conclusions).'}
    out['passed']=bool(out['all_runs_passed'] and out['output_chain']['fraction_gate_met'] and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged')
                       and out['independence']['distinct_seeds']==len(runs))
    (batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print('runs',len(runs),'passed',out['passed'],'flight_failures',out['flight_failures']);return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
