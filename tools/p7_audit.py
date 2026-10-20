#!/usr/bin/env python3
"""Independently re-check a finished P7 batch from raw run evidence and summarize it; never modifies runs.

Per run (as P6): P0 audit checks (PX4 exit, crash markers, ULog hash, analyzer verdict, recovery, executor, trace), per-motor
output-chain gate, fresh recomputation of the stored p7-metrics.json (p6-metrics.json for config/p6.json runs) compared as
JSON with the stored file. Batch tables (measurements only; no model fitting, prediction or classification):
  A  per group (capture, axis, D) the q4 runs ordered by the interval g, with the single-interruption reference
  B  per random sequence
  C  per run: outcome, max tilt, per resume the catch-up duration of the virtual target and the lag behind the trajectory
"""
import argparse,json
from pathlib import Path
from preparation_audit import flight
from p0_closure import GATE
from p2_batch import chain_errors
from p4_audit import fresh,sha
import p6_metrics,p7_metrics,p7_conditions
from p6_audit import gap_values
ROOT=Path(__file__).resolve().parents[1]

def p7_values(m):
    p7=m.get('p7') or {};rec=p7.get('recovery') or {};lag={x['gap']:x for x in p7.get('lag') or []}
    rows=[]
    for g in m.get('gaps') or []:
        r=next((x for x in rec.get('recoveries') or [] if x.get('gap')==g['index']),{});lg=lag.get(g['index'],{})
        rows.append({'gap':g['index'],'planned_D_s':g.get('planned_D_s'),'silence_s':g.get('silence_s'),'captured_speed_m_s':((g.get('capture') or {}).get('vehicle_velocity_ned_m_s') and sum(x*x for x in g['capture']['vehicle_velocity_ned_m_s'][:2])**.5),
            'setpoint_jump_along_axis_m':(g.get('resume') or {}).get('jump_along_axis_m'),'setpoint_velocity_jump_along_axis_m_s':(g.get('resume') or {}).get('velocity_jump_along_axis_m_s'),
            'observed_jump_along_axis_m':r.get('observed_jump_along_axis_m'),'recovery_end':r.get('end'),'catch_up_s':r.get('catch_up_s'),'recovery_duration_s':r.get('duration_s'),
            'acceleration_limited_s':(r.get('replay') or {}).get('limited_s'),'replay_max_position_residual_m':(r.get('replay') or {}).get('max_position_residual_m'),
            'max_along_track_lag_m':lg.get('max_along_track_lag_m'),'along_track_lag_at_6s_m':lg.get('along_track_lag_at_window_end_m'),'max_horizontal_distance_m':lg.get('max_horizontal_distance_m'),
            'horizontal_distance_at_6s_m':lg.get('horizontal_distance_at_window_end_m'),'lag_window_truncated':lg.get('truncated'),'lag_window_cut_by_next_interruption':lg.get('cut_by_next_interruption'),
            'max_tilt_deg':(g.get('window') or {}).get('max_tilt_deg')})
    return {'rrec':(p7.get('parameters') or {}).get('MC_RAPTOR_RREC'),'recovery_status':rec.get('status'),'recovery_rows':rec.get('rows'),'per_resume':rows}

def tilt_of(r):
    og=r['metrics'].get('open_gap') or {}
    if r['metrics']['max_tilt_deg'] is None and og.get('open_gap'):return og.get('max_tilt_deg_until_raptor_end'),True
    return r['metrics']['max_tilt_deg'],False

def tables(runs,cfg):
    out={'A':{},'B':{},'C':[]}
    if not cfg or 'p7' not in cfg:return out
    p7=cfg['p7'];single={}
    for r in runs:
        m=p7_conditions.SINGLE.match(r['condition'])
        if m and not r['condition'].startswith('h-'):single[(r['treatment'],m['axis'],float(m['D']))]=r
    for g in p7['a']['groups']:
        for D in g['durations_s']:
            key=f"{g['name']} {g['treatment']} {g['axis']} D{p7_conditions.fmt(D)}";rows=[]
            for gap in p7['a']['intervals_s']:
                name=p7_conditions.seq4_name(D,gap,g['axis']);r=next((x for x in runs if x['condition']==name and x['treatment']==g['treatment']),None)
                cancelled=f"{name}:{g['treatment']}" in p7.get('cancelled',[])
                if r is None:rows.append({'g_s':gap,'condition':name,'cancelled':cancelled,'flown':False});continue
                t,op=tilt_of(r);rows.append({'g_s':gap,'condition':name,'flown':True,'id':r['id'],'outcome':r['outcome'],'max_tilt_deg':t,'max_tilt_from_open_gap':op,
                    'first_at_or_above_45_s':r['metrics']['first_at_or_above_45_s'],'max_altitude_loss_m':r['metrics']['max_altitude_loss_m'],
                    'gaps_completed':len(r['metrics']['gaps']),'per_interruption_max_tilt_deg':[x['max_tilt_deg'] for x in r['metrics']['gaps']],
                    'setpoint_jumps_m':[x['jump_along_axis_m'] for x in r['metrics']['gaps']],'captured_speeds_m_s':[x['captured_speed_m_s'] for x in r['metrics']['gaps']]})
            ref=single.get((g['treatment'],g['axis'],float(D)))
            out['A'][key]={'single_reference':None if ref is None else {'id':ref['id'],'condition':ref['condition'],'outcome':ref['outcome'],'max_tilt_deg':tilt_of(ref)[0]},'by_interval':rows}
    for r in runs:
        pat,_,axis=r['condition'].rpartition('-')
        if pat in (p7['b'].get('sequences') or {}):
            s=p7['b']['sequences'][pat];t,op=tilt_of(r)
            out['B'][pat]={'id':r['id'],'windows_s':s['windows_s'],'count':s['count'],'durations_s':s['durations_s'],'intervals_s':s['intervals_s'],'total_interruption_s':s['total_interruption_s'],'span_s':s['span_s'],
                'outcome':r['outcome'],'max_tilt_deg':t,'max_tilt_from_open_gap':op,'first_at_or_above_45_s':r['metrics']['first_at_or_above_45_s'],'max_altitude_loss_m':r['metrics']['max_altitude_loss_m'],
                'gaps_completed':len(r['metrics']['gaps']),'per_interruption_max_tilt_deg':[x['max_tilt_deg'] for x in r['metrics']['gaps']],'setpoint_jumps_m':[x['jump_along_axis_m'] for x in r['metrics']['gaps']]}
        if r['condition'].startswith('h-'):
            t,op=tilt_of(r)
            out['C'].append({'id':r['id'],'condition':r['condition'],'treatment':r['treatment'],'outcome':r['outcome'],'max_tilt_deg':t,'max_tilt_from_open_gap':op,
                'first_at_or_above_45_s':r['metrics']['first_at_or_above_45_s'],'max_altitude_loss_m':r['metrics']['max_altitude_loss_m'],'max_horizontal_radius_m':r['metrics']['max_horizontal_radius_m'],
                'rrec':r['p7']['rrec'],'per_resume':r['p7']['per_resume']})
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);args=p.parse_args()
    batch=args.batch.resolve();results=json.loads((batch/'results.json').read_text());plan=json.loads((batch/'plan.json').read_text())
    planned={r['id']:r for r in plan['runs']};runs=[];cfg7=None
    for r in results['runs']:
        run=ROOT/r['directory']
        if r['status']=='NOT_RUN' or not run.exists():continue
        cfg=json.loads((ROOT/r['config']).read_text())
        if 'p7' in cfg:cfg7=cfg
        a={'id':r['id'],'kind':r['kind'],'condition':r['condition'],'treatment':r['treatment'],'config':r['config'],'sim_seed':(planned.get(r['id']) or r)['sim_seed'],**flight(run,r['kind'])}
        oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
        v=json.loads((run/'validation.json').read_text()) if (run/'validation.json').exists() else {}
        a['output_chain_gate_errors'],a['output_chain_errors_attributed_to_abort']=chain_errors(oc,str(v.get('reason') or '').startswith('safety:'))
        a['output_chain_counts']={'steps':sum(x['neural']['steps'] for x in oc.get('motors',{}).values()),
            'overwritten':sum(x['neural']['commands_overwritten_in_gazebo'] for x in oc.get('motors',{}).values())+4*(oc.get('px4_overwritten_publications',{}).get('neural_bracketed') or 0),
            'max_applied_age_us':max((x['neural'].get('applied_age_us') or {}).get('max') or 0 for x in oc.get('motors',{}).values())} if oc else None
        infra=a['px4_exit_codes']==[0] and not a['crash_markers'] and a['ulog_sha256_matches'] and not a['output_chain_gate_errors'] and (a.get('trace') or {}).get('status')=='MEASURED'
        name,mod=('p7-metrics.json',p7_metrics) if 'p7' in cfg else ('p6-metrics.json',p6_metrics)
        f=fresh(mod.analyze(run));stored=json.loads((run/name).read_text()) if (run/name).exists() else None
        a['recomputed']={'file':name,'reproduced':stored==f,'measured':f.get('status')=='MEASURED','problems':f.get('problems')}
        ok=a['recomputed']['reproduced'] and a['recomputed']['measured'];a['independence']=f.get('independence')
        a['metrics']=gap_values(f);a['p7']=p7_values(f) if 'p7' in cfg else None
        a['outcome']=(f.get('flight_outcome') or {}).get('outcome');a['flight_failure_reasons']=(f.get('flight_outcome') or {}).get('reasons')
        a['flight_failure']=bool(infra and ok and a['outcome']=='FAILURE');a['passed']=bool(infra and ok and (a['passed'] or a['flight_failure']))
        a['max_horizontal_radius_m']=a['metrics'].get('max_horizontal_radius_m');runs.append(a)
    steps=sum(r['output_chain_counts']['steps'] for r in runs if r['output_chain_counts']);over=sum(r['output_chain_counts']['overwritten'] for r in runs if r['output_chain_counts'])
    seeds=[r['sim_seed'] for r in runs]
    out={'batch':str(batch.relative_to(ROOT)),'stage':plan.get('stage'),'config':plan['config'],
        'audit_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['p7_audit.py','p7_metrics.py','p6_metrics.py','p5_metrics.py','p5_open_gap.py','p7_batch.py','p7_conditions.py','p6_audit.py','p1_metrics.py','p0_metrics.py','recovery.py','preparation_audit.py']},
        'runner_results':{k:results[k] for k in results if k!='runs'},
        'output_chain':{'gate':GATE,'neural_motor_steps':steps,'overwritten_motor_commands':over,'overwritten_fraction':over/steps if steps else None,
            'fraction_gate_met':bool(steps) and over/steps<GATE['overwritten_fraction'],'per_run_gate_failures':[r['id'] for r in runs if r['output_chain_gate_errors']],
            'max_applied_age_us':max((r['output_chain_counts'] or {}).get('max_applied_age_us',0) for r in runs) if runs else None},
        'runs_checked':len(runs),'all_runs_passed':bool(runs) and all(r['passed'] for r in runs),'flight_failures':[r['id'] for r in runs if r.get('flight_failure')],
        'independence':{'runs':len(runs),'distinct_seeds':len(set(seeds))},'tables':tables(runs,cfg7),
        'max_horizontal_radius_m':max((r.get('max_horizontal_radius_m') or 0) for r in runs) if runs else None,'runs':runs,
        'scope':'One frozen candidate, headless SITL only, x500, each run its own Gazebo seed. Measurements only: no model fitting, prediction or classification.'}
    out['passed']=bool(out['all_runs_passed'] and out['output_chain']['fraction_gate_met'] and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged')
                       and out['independence']['distinct_seeds']==len(runs))
    (batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print('runs',len(runs),'passed',out['passed'],'flight_failures',len(out['flight_failures']));return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
