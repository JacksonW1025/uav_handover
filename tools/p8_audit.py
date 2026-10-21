#!/usr/bin/env python3
"""Independently re-check a finished P8 batch from raw run evidence and summarize it; never modifies runs.

Per run (P6 audit checks, tools/p6_audit.py): PX4 exit, crash markers, ULog hash, analyzer verdict, recovery, executor,
trace, per-motor output-chain gate, fresh recomputation of the stored metrics (p8_metrics for config/p8.json, the frozen
p6_metrics for config/p6.json) compared as JSON with the stored file. A table per identification run: outcome class,
max tilt and its time, first >= 45 deg, altitude loss and its time, descent speed, motor command range, jump timing and
size, realized cruise, catch-up, chase switch, the task criterion (P8 fixed second criterion). No model fitting.
"""
import argparse,json
from pathlib import Path
from preparation_audit import flight
from p0_closure import GATE
from p2_batch import chain_errors
from p4_audit import fresh,sha
import p6_metrics,p8_metrics
from p6_audit import ident_values
ROOT=Path(__file__).resolve().parents[1]

def p8_values(m):
    p8=m.get('p8') or {};j=p8.get('jump') or {};lg=p8.get('lag') or {};vt=p8.get('vertical') or {};ch=p8.get('chase') or {}
    return {'jump':{k:j.get(k) for k in ['jump_m','planned_jump_m','family_time_s','planned_family_time_s','realized_pre_jump_cruise_s','realized_post_jump_cruise_s','planned_post_jump_cruise_s','raptor_read_delay_s']} if j else None,
            'chase':ch or None,'lag':{k:lg.get(k) for k in ['initial_lag_m','max_lag_m','max_lag_at_s','catch_up_s','min_lag_m','max_speed_along_axis_m_s','max_speed_along_axis_at_s']} if lg else None,
            'vertical':{k:vt.get(k) for k in ['altitude_at_family_start_m','min_altitude_m','max_altitude_loss_m','max_altitude_loss_at_s','max_descent_speed_m_s','max_climb_speed_m_s','motor_command_mean_min','motor_command_mean_max','motor_any_at_limit_s']} if vt else None,
            'task_criterion':p8.get('task_criterion'),'parameters':p8.get('parameters')}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);args=p.parse_args()
    batch=args.batch.resolve();results=json.loads((batch/'results.json').read_text());plan=json.loads((batch/'plan.json').read_text())
    planned={r['id']:r for r in plan['runs']};runs=[]
    for r in results['runs']:
        run=ROOT/r['directory']
        if r['status']=='NOT_RUN' or not run.exists():continue
        cfg=json.loads((ROOT/r['config']).read_text())
        a={'id':r['id'],'kind':r['kind'],'condition':r['condition'],'treatment':r['treatment'],'config':r['config'],'sim_seed':(planned.get(r['id']) or r)['sim_seed'],**flight(run,r['kind'])}
        oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
        v=json.loads((run/'validation.json').read_text()) if (run/'validation.json').exists() else {}
        a['output_chain_gate_errors'],a['output_chain_errors_attributed_to_abort']=chain_errors(oc,str(v.get('reason') or '').startswith('safety:'))
        a['output_chain_counts']={'steps':sum(x['neural']['steps'] for x in oc.get('motors',{}).values()),
            'overwritten':sum(x['neural']['commands_overwritten_in_gazebo'] for x in oc.get('motors',{}).values())+4*(oc.get('px4_overwritten_publications',{}).get('neural_bracketed') or 0),
            'max_applied_age_us':max((x['neural'].get('applied_age_us') or {}).get('max') or 0 for x in oc.get('motors',{}).values())} if oc else None
        infra=a['px4_exit_codes']==[0] and not a['crash_markers'] and a['ulog_sha256_matches'] and not a['output_chain_gate_errors'] and (a.get('trace') or {}).get('status')=='MEASURED'
        name,mod=('p8-metrics.json',p8_metrics) if 'p8' in cfg else ('p6-metrics.json',p6_metrics)
        f=fresh(mod.analyze(run));stored=json.loads((run/name).read_text()) if (run/name).exists() else None
        a['recomputed']={'file':name,'reproduced':stored==f,'measured':f.get('status')=='MEASURED','problems':f.get('problems')}
        ok=a['recomputed']['reproduced'] and a['recomputed']['measured'];a['independence']=f.get('independence')
        a['metrics']=ident_values(f);a['outcome']=a['metrics']['outcome'];a['flight_failure']=False
        if 'p8' in cfg:a['p8']=p8_values(f)
        a['passed']=bool(infra and ok and a['outcome'] in ['IDENT_OK','IDENT_EXCEEDED_45','IDENT_ABORTED'] and (a['passed'] or a['outcome']=='IDENT_ABORTED'))
        a['max_horizontal_radius_m']=a['metrics'].get('max_horizontal_radius_m');runs.append(a)
    steps=sum(r['output_chain_counts']['steps'] for r in runs if r['output_chain_counts']);over=sum(r['output_chain_counts']['overwritten'] for r in runs if r['output_chain_counts'])
    seeds=[r['sim_seed'] for r in runs]
    out={'batch':str(batch.relative_to(ROOT)),'stage':plan.get('stage'),'config':plan['config'],
        'audit_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['p8_audit.py','p8_metrics.py','p6_metrics.py','p5_metrics.py','p8_batch.py','p8_conditions.py','p6_conditions.py','p1_metrics.py','p0_metrics.py','recovery.py','preparation_audit.py']},
        'runner_results':{k:results[k] for k in results if k!='runs'},
        'output_chain':{'gate':GATE,'neural_motor_steps':steps,'overwritten_motor_commands':over,'overwritten_fraction':over/steps if steps else None,
            'fraction_gate_met':bool(steps) and over/steps<GATE['overwritten_fraction'],'per_run_gate_failures':[r['id'] for r in runs if r['output_chain_gate_errors']],
            'max_applied_age_us':max((r['output_chain_counts'] or {}).get('max_applied_age_us',0) for r in runs) if runs else None},
        'runs_checked':len(runs),'all_runs_passed':bool(runs) and all(r['passed'] for r in runs),
        'identification_outcomes':{r['id']:r['outcome'] for r in runs},
        'task_criterion_exceeded':{r['id']:((r.get('p8') or {}).get('task_criterion') or {}).get('reasons') for r in runs if ((r.get('p8') or {}).get('task_criterion') or {}).get('exceeded')},
        'independence':{'runs':len(runs),'distinct_seeds':len(set(seeds))},
        'max_horizontal_radius_m':max((r.get('max_horizontal_radius_m') or 0) for r in runs) if runs else None,'runs':runs,
        'scope':'One frozen candidate, headless SITL only, x500, each run its own Gazebo seed. Flies and exports only; no model fitting or prediction.'}
    out['passed']=bool(out['all_runs_passed'] and out['output_chain']['fraction_gate_met'] and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged')
                       and out['independence']['distinct_seeds']==len(runs))
    (batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print('runs',len(runs),'passed',out['passed'],'ident',out['identification_outcomes'],'task',out['task_criterion_exceeded']);return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
