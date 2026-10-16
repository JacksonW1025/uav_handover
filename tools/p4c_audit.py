#!/usr/bin/env python3
"""Independently re-check a finished P4-01c batch from raw run evidence and summarize it; never modifies runs.

Per run: P0 audit checks (PX4 exit, crash markers, ULog hash, analyzer verdict, recovery, executor, trace), per-motor
output-chain gate, fresh recomputation of p2_metrics, p4_metrics and p4c_metrics, each compared with the stored file;
takeover-target evidence (capture mode, initial target velocity, deceleration, closed-form profile). Batch: per group
(speed level x target) flight failures, means with 95% t intervals (all runs; settle metrics over the runs that
settled), observation clipping, T0 - T1 differences with 95% bootstrap intervals, and at 1.0 m/s the part of the
capture cost removed by T1 relative to the P4 01b M1 RAPTOR baseline (config p4c.capture_cost_reference; cross-batch
reference as requested, not an acceptance splice). Only runs of this batch enter the group results.
"""
import argparse,json
from pathlib import Path
import numpy as np
from preparation_audit import flight
from p0_closure import GATE
from p2_batch import chain_errors
from p1_audit import row_of
from p4_audit import stats,fresh,sha
import p2_metrics,p4_metrics,p4c_metrics
ROOT=Path(__file__).resolve().parents[1]
METRICS=['max_tilt_deg','max_altitude_loss_m','motor_step_at_change','motor_max_step_window','motor_saturation_any_s','motor_longest_continuous_saturation_s','max_angular_rate_rad_s']
SETTLE=['settle_time_s','settle_distance_m','settle_distance_along_axis_m']
TRAVEL='max_travel_along_axis_m'
CAPTURE_METRICS={'motor_step_at_change':'motor_step_at_change','max_altitude_loss_m':'max_altitude_loss_m','max_tilt_deg':'max_tilt_deg'}

def boot_diff(a,b,rng,n):
    a,b=np.asarray(a,float),np.asarray(b,float);A=a[rng.integers(0,len(a),(n,len(a)))].mean(1);B=b[rng.integers(0,len(b),(n,len(b)))].mean(1);d=A-B
    return {'difference':float(a.mean()-b.mean()),'ci95':[float(np.percentile(d,2.5)),float(np.percentile(d,97.5))]}

def boot_removed(t0,t1,base,rng,n):
    """(T0 - T1) / baseline, groups resampled independently."""
    t0,t1,base=(np.asarray(x,float) for x in (t0,t1,base))
    A=t0[rng.integers(0,len(t0),(n,len(t0)))].mean(1);B=t1[rng.integers(0,len(t1),(n,len(t1)))].mean(1);C=base[rng.integers(0,len(base),(n,len(base)))].mean(1)
    ok=np.abs(C)>1e-9;r=(A[ok]-B[ok])/C[ok]
    return {'removed_fraction':float((t0.mean()-t1.mean())/base.mean()),'ci95':[float(np.percentile(r,2.5)),float(np.percentile(r,97.5))],'resamples_used':int(ok.sum())}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);args=p.parse_args()
    batch=args.batch.resolve();results=json.loads((batch/'results.json').read_text());plan=json.loads((batch/'plan.json').read_text())
    cfg=json.loads((ROOT/plan['config']).read_text());p4=cfg['p4'];pc=cfg['p4c'];planned={r['id']:r for r in plan['runs']};runs=[]
    for r in results['runs']:
        run=ROOT/r['directory']
        if r['status']=='NOT_RUN' or not run.exists():continue
        a={'id':r['id'],'kind':r['kind'],'condition':r['condition'],'treatment':r['treatment'],'sim_seed':planned[r['id']]['sim_seed'],**flight(run,r['kind'])}
        oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
        v=json.loads((run/'validation.json').read_text()) if (run/'validation.json').exists() else {}
        a['output_chain_gate_errors'],a['output_chain_errors_attributed_to_abort']=chain_errors(oc,str(v.get('reason') or '').startswith('safety:'))
        a['output_chain_counts']={'steps':sum(x['neural']['steps'] for x in oc.get('motors',{}).values()),
            'overwritten':sum(x['neural']['commands_overwritten_in_gazebo'] for x in oc.get('motors',{}).values())+4*(oc.get('px4_overwritten_publications',{}).get('neural_bracketed') or 0),
            'max_applied_age_us':max((x['neural'].get('applied_age_us') or {}).get('max') or 0 for x in oc.get('motors',{}).values())} if oc else None
        infra=a['px4_exit_codes']==[0] and not a['crash_markers'] and a['ulog_sha256_matches'] and not a['output_chain_gate_errors'] and (a.get('trace') or {}).get('status')=='MEASURED'
        stored=lambda n:json.loads((run/n).read_text()) if (run/n).exists() else None
        f2=fresh(p2_metrics.analyze(run));a['p2_reproduced']=stored('p2-metrics.json')==f2;a['p2_status']=f2.get('p2_status');a['p2_problems']=f2.get('problems')
        f4=fresh(p4_metrics.analyze(run));a['p4_reproduced']=stored('p4-metrics.json')==f4;a['p4_status']=f4['status'];a['p4_problems']=f4['problems']
        fc=fresh(p4c_metrics.analyze(run));a['p4c_reproduced']=stored('p4c-metrics.json')==fc;a['p4c_status']=fc['status'];a['p4c_problems']=fc['problems']
        ok=a['p2_reproduced'] and a['p4_reproduced'] and a['p4c_reproduced'] and a['p2_status']=='MEASURED' and a['p4_status']=='MEASURED' and a['p4c_status']=='MEASURED'
        a['evidence']={'entry':(f2.get('entry') or {}).get('status'),'teacher_forcing':(f2.get('teacher_forcing') or {}).get('status'),
                       'capture':(f2.get('reference_at_takeover') or {}).get('classification'),'target':(fc.get('target') or {}).get('status')}
        tgt=fc.get('target') or {}
        a['target']={k:tgt.get(k) for k in ['planned_mode','planned_decel_m_s2','initial_target_velocity_ned_m_s','initial_target_speed_m_s','stop_time_s','stop_distance_m',
                     'profile_rows_in_window','profile_max_abs_error','profile_max_gap_us','end_point_ned_m']}
        a['target']['capture_decel_m_s2']=(tgt.get('capture') or {}).get('decel_m_s2');a['target']['capture_mode']=(tgt.get('capture') or {}).get('mode')
        a['takeover_state']=(f4.get('takeover_state') or {}).get('subject');a['teacher_forcing_coverage']=f4.get('teacher_forcing_coverage');a['planned_path']=f4.get('planned_path')
        a['metrics']={**(fc.get('metrics') or {}),**{k:(fc.get('settle') or {}).get(k) for k in SETTLE+['settled','settle_minus_target_end_along_axis_m',TRAVEL]}}
        a['clipping']={n:{k:(fc.get('clipping') or {}).get(n,{}).get(k) for k in ['triggered','rows','duration_s','longest_continuous_s','first_after_change_s','last_after_change_s']} for n in ['position','velocity']}
        a['speed_at_change_m_s']=fc.get('speed_at_change_m_s');a['flight_outcome']=fc.get('flight_outcome');a['flight_failure_reasons']=fc.get('flight_failure_reasons')
        a['max_horizontal_radius_m']=f4.get('max_horizontal_radius_m');a['window_truncated']=fc.get('window_truncated') is not None
        a['flight_failure']=bool(infra and ok and a['flight_outcome']=='FAILURE')
        a['passed']=bool(infra and ok and (a['passed'] or a['flight_failure']))
        runs.append(a)
    rng=np.random.default_rng(p4['independence']['master_seed']);nboot=20000
    groups={}
    for r in runs:groups.setdefault(f"{r['condition']}:{r['treatment']}",[]).append(r)
    summary={}
    for k,g in sorted(groups.items()):
        ok=[r for r in g if not r['flight_failure']];settled=[r for r in g if r['metrics'].get('settled')]
        s={'runs':len(g),'ids':[r['id'] for r in g],'flight_failures':sum(r['flight_failure'] for r in g),'failure_reasons':[r['flight_failure_reasons'] for r in g if r['flight_failure']],
           'settled':len(settled),'speed_at_change_m_s':stats([r['speed_at_change_m_s'] for r in g]),
           'acceleration_at_change_m_s2':stats([(r['takeover_state'] or {}).get('acceleration_along_axis_m_s2') for r in g]),
           'all_runs':{m:stats([r['metrics'].get(m) for r in g]) for m in METRICS+[TRAVEL]},
           'successful_runs':{m:stats([r['metrics'].get(m) for r in ok]) for m in METRICS} if ok else None,
           'settle':{m:stats([r['metrics'].get(m) for r in settled]) for m in SETTLE+['settle_minus_target_end_along_axis_m']} if settled else None,
           'clipping':{n:{'runs_triggered':sum(bool(r['clipping'][n]['triggered']) for r in g),'duration_s':stats([r['clipping'][n]['duration_s'] for r in g]),
                          'longest_continuous_s':stats([r['clipping'][n]['longest_continuous_s'] for r in g]),'last_after_change_s':stats([r['clipping'][n]['last_after_change_s'] for r in g])} for n in ['position','velocity']},
           'target':{'capture_modes':sorted({r['target']['capture_mode'] for r in g}),'capture_decel_m_s2':sorted({r['target']['capture_decel_m_s2'] for r in g}),
                     'initial_target_speed_m_s':stats([r['target'].get('initial_target_speed_m_s') for r in g]),'stop_distance_m':stats([r['target'].get('stop_distance_m') for r in g]),
                     'max_profile_position_error_m':max([(r['target'].get('profile_max_abs_error') or {}).get('position_m') or 0 for r in g]),
                     'max_profile_velocity_error_m_s':max([(r['target'].get('profile_max_abs_error') or {}).get('velocity_m_s') or 0 for r in g]),
                     'evidence_verified':sum(r['evidence']['target']=='VERIFIED' for r in g)},
           'teacher_forcing_native_steps_before_entry':stats([(r['teacher_forcing_coverage'] or {}).get('consecutive_teacher_forced_native_steps') for r in g])}
        summary[k]=s
    # T0 - T1 per level (where both were flown; all runs, aborted runs measured up to the abort).
    comparison={}
    for lvl in sorted({r['condition'] for r in runs}):
        a,b=groups.get(f'{lvl}:T0'),groups.get(f'{lvl}:T1')
        if not a or not b:continue
        comparison[lvl]={'flight_failures':{'T0':sum(r['flight_failure'] for r in a),'T1':sum(r['flight_failure'] for r in b)}}
        for m in METRICS:
            x=[r['metrics'].get(m) for r in a];y=[r['metrics'].get(m) for r in b]
            if None in x+y:continue
            comparison[lvl][m]=boot_diff(x,y,rng,nboot);comparison[lvl][m]['note']='T0 - T1'
    # 1.0 m/s: part of the capture cost removed by T1 (01b M1 RAPTOR baseline = capture part).
    ref=pc['capture_cost_reference'];capture={}
    rb=json.loads((ROOT/ref['batch']/'results.json').read_text())['runs']
    def rows01b(group):
        kind,cond,treat=group.split(':');return [row_of(json.loads((ROOT/x['directory']/'p2-metrics.json').read_text())) for x in rb if (x['kind'],x['condition'],x['treatment'])==(kind,cond,treat) and x.get('accepted')]
    base,n2=rows01b(ref['baseline_group']),rows01b(ref['n2_group'])
    t0,t1=groups.get('V1.0:T0'),groups.get('V1.0:T1')
    if t0 and t1 and base:
        capture={'reference_batch':ref['batch'],'baseline_runs':len(base),'n2_runs':len(n2),'definition':ref['definition']}
        for m,key in CAPTURE_METRICS.items():
            bv=[x[key] for x in base];nv=[x[key] for x in n2];a=[r['metrics'][m] for r in t0];b=[r['metrics'][m] for r in t1]
            capture[m]={'baseline_01b':stats(bv),'n2_01b':stats(nv),'T0':stats(a),'T1':stats(b),**boot_removed(a,b,bv,rng,nboot),
                        'T0_minus_01b_N2':boot_diff(a,nv,rng,nboot),'T1_minus_01b_baseline':boot_diff(b,bv,rng,nboot)}
    steps=sum(r['output_chain_counts']['steps'] for r in runs if r['output_chain_counts']);over=sum(r['output_chain_counts']['overwritten'] for r in runs if r['output_chain_counts'])
    seeds=[r['sim_seed'] for r in runs]
    out={'batch':str(batch.relative_to(ROOT)),'config':plan['config'],
        'audit_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['p4c_audit.py','p4c_metrics.py','p4_metrics.py','p2_metrics.py','p1_metrics.py','p0_metrics.py','recovery.py','preparation_audit.py']},
        'runner_results':{k:results[k] for k in results if k!='runs'},
        'output_chain':{'gate':GATE,'neural_motor_steps':steps,'overwritten_motor_commands':over,'overwritten_fraction':over/steps if steps else None,
            'fraction_gate_met':bool(steps) and over/steps<GATE['overwritten_fraction'],'per_run_gate_failures':[r['id'] for r in runs if r['output_chain_gate_errors']],
            'max_applied_age_us':max((r['output_chain_counts'] or {}).get('max_applied_age_us',0) for r in runs) if runs else None},
        'runs_checked':len(runs),'all_runs_passed':bool(runs) and all(r['passed'] for r in runs),'flight_failures':[r['id'] for r in runs if r.get('flight_failure')],
        'independence':{'runs':len(runs),'distinct_seeds':len(set(seeds))},'summary':summary,'t0_minus_t1':comparison,'capture_cost_1p0':capture,
        'max_horizontal_radius_m':max((r['max_horizontal_radius_m'] or 0) for r in runs) if runs else None,'runs':runs,
        'definitions':{'groups':'speed level (V1.0..V3.0) x takeover target (T0 zero-velocity capture, T1 speed-matched with 2.0 m/s^2), N2 memory in all runs',
            'all_runs':'every run including flight failures (a failed run is measured up to the runner safety abort)','successful_runs':'runs without a flight failure',
            'settle':pc['settle']['definition'],'clipping':pc['clipping']['definition'],'group_ci':p4['statistics']['group_ci'],
            'bootstrap':'95% percentile bootstrap, groups resampled independently, 20000 resamples, numpy default_rng(master_seed)',
            'capture_cost':ref['definition']},
        'scope':'One frozen candidate, headless SITL only, x500, heading 0, each run its own Gazebo seed; n = 3 per group.'}
    out['passed']=bool(out['all_runs_passed'] and out['output_chain']['fraction_gate_met'] and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged')
                       and out['independence']['distinct_seeds']==len(runs))
    (batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print('runs',len(runs),'passed',out['passed'],'flight_failures',out['flight_failures']);return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
