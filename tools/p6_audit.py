#!/usr/bin/env python3
"""Independently re-check a finished P6 batch from raw run evidence and summarize it; never modifies runs.

Per run: P0 audit checks (PX4 exit, crash markers, ULog hash, analyzer verdict, recovery, executor, trace), per-motor
output-chain gate, fresh recomputation of the stored metrics (p6_metrics, or the frozen p5_metrics for config/p5.json runs)
compared as JSON with the stored file. Batch: identification runs (outcome class, max tilt and its time, first >= 45 deg,
altitude loss, clipping, chase switch) and, for p5_gap, the per-family table (treatment x speed x axis): each D with its
outcome, max tilt, first >= 45 deg, interruption timing and capture, resume jump vs the exact prediction, and the
success/failure bracket. No model fitting and no kernel classification (held-out test, done by the project).
"""
import argparse,json
from pathlib import Path
from preparation_audit import flight
from p0_closure import GATE
from p2_batch import chain_errors
from p4_audit import fresh,sha
import p5_metrics,p6_metrics,p6_conditions
from p6_batch import bracket
ROOT=Path(__file__).resolve().parents[1]

def gap_values(m):
    wh=m.get('whole') or {};p6=m.get('p6') or {};tl=p6.get('tilt') or {};og=p6.get('open_gap') or {}
    gaps=[{'silence_s':g.get('silence_s'),'planned_D_s':g.get('planned_D_s'),'capture_after_last_reception_s':(g.get('capture') or {}).get('after_last_reception_s'),
           'capture_mode':(g.get('capture') or {}).get('mode'),'captured_speed_m_s':((g.get('capture') or {}).get('vehicle_velocity_ned_m_s') and sum(x*x for x in g['capture']['vehicle_velocity_ned_m_s'][:2])**.5),
           'jump_along_axis_m':(g.get('resume') or {}).get('jump_along_axis_m'),'prediction_m':(g.get('resume') or {}).get('prediction_m'),
           'velocity_jump_along_axis_m_s':(g.get('resume') or {}).get('velocity_jump_along_axis_m_s'),'catch_up_s':g.get('catch_up_s'),
           'max_tilt_deg':(g.get('window') or {}).get('max_tilt_deg'),'max_altitude_loss_m':(g.get('window') or {}).get('max_altitude_loss_m')} for g in m.get('gaps',[])]
    return {'max_tilt_deg':wh.get('max_tilt_deg'),'max_altitude_loss_m':wh.get('max_altitude_loss_m'),'max_angular_rate_rad_s':wh.get('max_angular_rate_rad_s'),
            'max_horizontal_radius_m':wh.get('max_horizontal_radius_m'),'motor_saturation_any_s':wh.get('motor_saturation_any_s'),
            'max_tilt_at_s':tl.get('max_tilt_at_s'),'first_at_or_above_45_s':tl.get('first_at_or_above_45_s'),'aborted':m.get('aborted'),'failure_reason':m.get('failure_reason'),
            'open_gap':{k:og.get(k) for k in ['open_gap','silence_until_raptor_end_s','max_tilt_deg_until_raptor_end','capture_to_45deg_s']} if og else None,
            'open_gap_capture':og.get('capture'),'direction':m.get('direction'),'gaps':gaps,
            'clipping_whole':{n:((m.get('clipping_whole') or {}).get(n) or {}).get('duration_s') for n in ['position','velocity']}}

def ident_values(m):
    wh=m.get('whole') or {};tl=m.get('tilt') or {};cl=m.get('clipping') or {}
    return {'family':m.get('family'),'outcome':(m.get('ident_outcome') or {}).get('class'),'max_tilt_deg':tl.get('max_tilt_deg'),'max_tilt_at_s':tl.get('max_tilt_at_s'),
            'first_at_or_above_45_s':tl.get('first_at_or_above_45_s'),'at_or_above_45_s':tl.get('at_or_above_45_s'),'max_altitude_loss_m':wh.get('max_altitude_loss_m'),
            'max_angular_rate_rad_s':wh.get('max_angular_rate_rad_s'),'max_horizontal_radius_m':wh.get('max_horizontal_radius_m'),'motor_saturation_any_s':wh.get('motor_saturation_any_s'),
            'max_speed_along_axis_m_s':m.get('max_speed_along_axis_m_s'),'chase_switch':m.get('chase_switch'),'gap':m.get('gap'),'aborted':m.get('aborted'),'failure_reason':m.get('failure_reason'),
            'clipping_s':{n:(cl.get(n) or {}).get('duration_s') for n in ['position','velocity']},'clipping_both_axes_s':{n:(cl.get(n) or {}).get('both_horizontal_axes_s') for n in ['position','velocity']}}

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
        name,mod=('p6-metrics.json',p6_metrics) if 'p6' in cfg else ('p5-metrics.json',p5_metrics)
        f=fresh(mod.analyze(run));stored=json.loads((run/name).read_text()) if (run/name).exists() else None
        a['recomputed']={'file':name,'reproduced':stored==f,'measured':f.get('status')=='MEASURED','problems':f.get('problems')}
        ok=a['recomputed']['reproduced'] and a['recomputed']['measured'];a['independence']=f.get('independence')
        if r['kind']=='p6_ident':
            a['metrics']=ident_values(f);a['outcome']=a['metrics']['outcome'];a['flight_failure']=False
            a['passed']=bool(infra and ok and a['outcome'] in ['IDENT_OK','IDENT_EXCEEDED_45','IDENT_ABORTED'] and (a['passed'] or a['outcome']=='IDENT_ABORTED'))
        else:
            a['metrics']=gap_values(f);a['outcome']=(f.get('flight_outcome') or {}).get('outcome');a['flight_failure_reasons']=(f.get('flight_outcome') or {}).get('reasons')
            a['flight_failure']=bool(infra and ok and a['outcome']=='FAILURE');a['passed']=bool(infra and ok and (a['passed'] or a['flight_failure']))
        a['max_horizontal_radius_m']=a['metrics'].get('max_horizontal_radius_m');runs.append(a)
    families={}
    for r in runs:
        if r['kind']!='p5_gap':continue
        m=p6_conditions.GAP_NAME.match(r['condition'])
        key=f"{r['treatment']}@{m['v']}@{m['axis']}" if m else f"{r['treatment']}@{r['condition']}"
        families.setdefault(key,[]).append({'D_s':float(m['D']) if m else None,'id':r['id'],'outcome':r['outcome'],'max_tilt_deg':r['metrics']['max_tilt_deg'],
            'first_at_or_above_45_s':r['metrics']['first_at_or_above_45_s'],'max_altitude_loss_m':r['metrics']['max_altitude_loss_m'],'sim_seed':r['sim_seed'],
            'jumps_m':[g['jump_along_axis_m'] for g in r['metrics']['gaps']],'velocity_jumps_m_s':[g['velocity_jump_along_axis_m_s'] for g in r['metrics']['gaps']]})
    fam_summary={}
    for k,rows in sorted(families.items()):
        rows.sort(key=lambda x:(x['D_s'] is None,x['D_s'] or 0,x['id']));pts=[(x['D_s'],'S' if x['outcome']=='SUCCESS' else 'F') for x in rows if x['D_s'] is not None and x['outcome'] in ['SUCCESS','FAILURE']]
        _,state,ls,ff=bracket(sorted(pts)) if pts else (None,None,None,None)
        fam_summary[k]={'runs':rows,'state_in_this_batch':state,'last_success_D_s':ls,'first_failure_D_s':ff}
    steps=sum(r['output_chain_counts']['steps'] for r in runs if r['output_chain_counts']);over=sum(r['output_chain_counts']['overwritten'] for r in runs if r['output_chain_counts'])
    seeds=[r['sim_seed'] for r in runs]
    out={'batch':str(batch.relative_to(ROOT)),'stage':plan.get('stage'),'config':plan['config'],
        'audit_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['p6_audit.py','p6_metrics.py','p5_metrics.py','p5_open_gap.py','p6_batch.py','p6_conditions.py','p1_metrics.py','p0_metrics.py','recovery.py','preparation_audit.py']},
        'runner_results':{k:results[k] for k in results if k!='runs'},
        'output_chain':{'gate':GATE,'neural_motor_steps':steps,'overwritten_motor_commands':over,'overwritten_fraction':over/steps if steps else None,
            'fraction_gate_met':bool(steps) and over/steps<GATE['overwritten_fraction'],'per_run_gate_failures':[r['id'] for r in runs if r['output_chain_gate_errors']],
            'max_applied_age_us':max((r['output_chain_counts'] or {}).get('max_applied_age_us',0) for r in runs) if runs else None},
        'runs_checked':len(runs),'all_runs_passed':bool(runs) and all(r['passed'] for r in runs),'flight_failures':[r['id'] for r in runs if r.get('flight_failure')],
        'identification_outcomes':{r['id']:r['outcome'] for r in runs if r['kind']=='p6_ident'},
        'independence':{'runs':len(runs),'distinct_seeds':len(set(seeds))},'families':fam_summary,
        'max_horizontal_radius_m':max((r.get('max_horizontal_radius_m') or 0) for r in runs) if runs else None,'runs':runs,
        'scope':'One frozen candidate, headless SITL only, x500, each run its own Gazebo seed. No model fitting or kernel classification here (held-out test).'}
    out['passed']=bool(out['all_runs_passed'] and out['output_chain']['fraction_gate_met'] and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged')
                       and out['independence']['distinct_seeds']==len(runs))
    (batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print('runs',len(runs),'passed',out['passed'],'flight_failures',len(out['flight_failures']),'ident',out['identification_outcomes']);return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
