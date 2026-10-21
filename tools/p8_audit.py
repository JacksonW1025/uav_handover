#!/usr/bin/env python3
"""Independently re-check a finished P8 batch from raw run evidence and summarize it; never modifies runs.

Per run (P6 audit checks, tools/p6_audit.py): PX4 exit, crash markers, ULog hash, analyzer verdict, recovery, executor,
trace, per-motor output-chain gate, fresh recomputation of the stored metrics (p8_metrics for config/p8.json, the frozen
p6_metrics for config/p6.json) compared as JSON with the stored file.
A (identification): outcome class, max tilt and its time, first >= 45 deg, altitude loss and its time, descent speed,
motor command range, jump timing and size, realized cruise, catch-up, chase switch, the task criterion.
B (p5_gap cases; campaign batches of tools/p8_campaign.py): primary outcome, task criterion, max tilt, altitude loss,
gap_timing, the budget check recomputed (p8_space.budget == gap_spec); per campaign from its state file: one counted run
per round, offline lists flown in order, online proposals reproduced by replaying p8_methods from the seed with the
recorded history (every proposed case must be identical), history entries equal to the fresh measurement (max tilt,
primary failure); tables per system under test x method (failures primary / task over the 3 seeds, distinct failure
cells p8_space.cell, round of the first failure per seed). No model fitting or prediction.
  p8_audit.py data/<batch> [--jobs N]
"""
import argparse,json
from pathlib import Path
from multiprocessing import Pool
from preparation_audit import flight
from p0_closure import GATE
from p2_batch import chain_errors
from p4_audit import fresh,sha
import p6_metrics,p8_metrics,p8_conditions
from p6_audit import ident_values
import p8_space,p8_methods
ROOT=Path(__file__).resolve().parents[1]

def p8_values(m):
    p8=m.get('p8') or {};j=p8.get('jump') or {};lg=p8.get('lag') or {};vt=p8.get('vertical') or {};ch=p8.get('chase') or {}
    return {'jump':{k:j.get(k) for k in ['jump_m','planned_jump_m','family_time_s','planned_family_time_s','realized_pre_jump_cruise_s','realized_post_jump_cruise_s','planned_post_jump_cruise_s','raptor_read_delay_s']} if j else None,
            'chase':ch or None,'lag':{k:lg.get(k) for k in ['initial_lag_m','max_lag_m','max_lag_at_s','catch_up_s','min_lag_m','max_speed_along_axis_m_s','max_speed_along_axis_at_s']} if lg else None,
            'vertical':{k:vt.get(k) for k in ['altitude_at_family_start_m','min_altitude_m','max_altitude_loss_m','max_altitude_loss_at_s','max_descent_speed_m_s','max_climb_speed_m_s','motor_command_mean_min','motor_command_mean_max','motor_any_at_limit_s']} if vt else None,
            'task_criterion':p8.get('task_criterion'),'parameters':p8.get('parameters')}

def gap_values(m):
    p8=m.get('p8') or {};res=p8.get('result') or {};wh=m.get('whole') or {}
    return {'outcome':(m.get('flight_outcome') or {}).get('outcome'),'reasons':(m.get('flight_outcome') or {}).get('reasons'),'fail_task':res.get('fail_task'),'task_reasons':res.get('task_reasons'),
            'max_tilt_deg':res.get('max_tilt_deg'),'max_tilt_at_s':res.get('max_tilt_at_s'),'max_altitude_loss_m':res.get('max_altitude_loss_m'),'aborted':m.get('aborted'),
            'max_horizontal_radius_m':wh.get('max_horizontal_radius_m'),'gap_timing':(p8.get('gap_timing') or {}).get('status'),'parameters':p8.get('parameters'),
            'captures':[(g.get('capture_after_last_reception_s'),g.get('capture_mode')) for g in (p8.get('gap_timing') or {}).get('gaps') or []]}

def audit_run(job):
    r,sim_seed=job;run=ROOT/r['directory'];cfg=json.loads((ROOT/r['config']).read_text())
    a={'id':r['id'],'kind':r['kind'],'condition':r['condition'],'treatment':r['treatment'],'config':r['config'],'sim_seed':sim_seed,**{k:r.get(k) for k in ['campaign','k','infra_rerun']},**flight(run,r['kind'])}
    oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
    v=json.loads((run/'validation.json').read_text()) if (run/'validation.json').exists() else {}
    a['output_chain_gate_errors'],a['output_chain_errors_attributed_to_abort']=chain_errors(oc,str(v.get('reason') or '').startswith('safety:'))
    a['output_chain_counts']={'steps':sum(x['neural']['steps'] for x in oc.get('motors',{}).values()),
        'overwritten':sum(x['neural']['commands_overwritten_in_gazebo'] for x in oc.get('motors',{}).values())+4*(oc.get('px4_overwritten_publications',{}).get('neural_bracketed') or 0),
        'max_applied_age_us':max((x['neural'].get('applied_age_us') or {}).get('max') or 0 for x in oc.get('motors',{}).values())} if oc else None
    infra=a['px4_exit_codes']==[0] and not a['crash_markers'] and a['ulog_sha256_matches'] and not a['output_chain_gate_errors'] and (a.get('trace') or {}).get('status')=='MEASURED'
    name,mod=('p8-metrics.json',p8_metrics) if 'p8' in cfg else ('p6-metrics.json',p6_metrics)
    try:f=fresh(mod.analyze(run))
    except Exception as e:f={'status':'ERROR','problems':[repr(e)]}
    stored=json.loads((run/name).read_text()) if (run/name).exists() else None
    a['recomputed']={'file':name,'reproduced':stored==f,'measured':f.get('status')=='MEASURED','problems':f.get('problems')}
    ok=a['recomputed']['reproduced'] and a['recomputed']['measured'];a['independence']=f.get('independence')
    if r['kind']=='p6_ident':
        a['metrics']=ident_values(f);a['outcome']=a['metrics']['outcome'];a['flight_failure']=False
        if 'p8' in cfg:a['p8']=p8_values(f)
        a['passed']=bool(infra and ok and a['outcome'] in ['IDENT_OK','IDENT_EXCEEDED_45','IDENT_ABORTED'] and (a['passed'] or a['outcome']=='IDENT_ABORTED'))
    else:
        a['metrics']=gap_values(f);a['outcome']=a['metrics']['outcome']
        a['flight_failure']=bool(infra and ok and a['outcome']=='FAILURE');a['passed']=bool(infra and ok and (a['passed'] or a['flight_failure']))
        if r.get('case'):
            chk=p8_conditions.budget_check(cfg,r['case'],r['treatment']);a['budget_check']=chk
            if not chk['equal'] or chk['condition']!=r['condition']:a['passed']=False
        a['counted']=None
    a['max_horizontal_radius_m']=a['metrics'].get('max_horizontal_radius_m');return a

def campaigns_check(state,order,rounds,audited):
    """Per campaign: counted runs, list order / online replay, history vs fresh measurement."""
    lists=json.loads((ROOT/'tools/p8/p8_lists.json').read_text())['lists'];by_id={a['id']:a for a in audited};out={}
    for cid in order:
        st=json.loads((state/'campaigns'/(cid.replace('/','_')+'.json')).read_text());res={'k_done':st['k_done'],'problems':[]}
        dev=[x for x in st['runs'] if x.get('status')=='DEVELOPMENT_FAILED']
        if dev:res['development_failed_rounds']=[x['k'] for x in dev];st['runs']=[x for x in st['runs'] if x.get('status')!='DEVELOPMENT_FAILED']
        ks=[x['k'] for x in st['runs']]
        if ks!=list(range(1,len(ks)+1)):res['problems'].append('counted rounds not 1..N')
        if st['method'] in ['fuzz','bo']:
            m={'fuzz':p8_methods.Fuzz,'bo':p8_methods.BO}[st['method']](st['sut'],st['seed'],p8_space.fits);hist=[]
            for x,h in zip(st['runs'],st['history']):
                c=m.propose(hist)
                if c!=x['case'] or h[0]!=x['case']:res['problems'].append(f"round {x['k']}: replayed proposal differs");break
                hist.append((h[0],h[1],h[2]))
            if len(st['history'])!=len(st['runs']):res['problems'].append('history length differs from counted runs')
            if m.rng.bit_generator.state!=st['rng_state'] and st['pending'] is None:res['problems'].append('rng state differs from replay')
            res['replayed']=len(hist)
        else:
            idx=[x['list_index'] for x in st['runs']]
            if idx!=list(range(len(idx))):res['problems'].append('offline list not flown in order without skips')
            if [x['name'] for x in st['runs']]!=[e['name'] for e in lists[cid][:len(idx)]]:res['problems'].append('names differ from the list')
        for j,x in enumerate(st['runs']):
            a=by_id.get(x['id'])
            if a is None:continue
            a['counted']=True
            if a['metrics']['max_tilt_deg']!=x['max_tilt_deg'] or a['flight_failure']!=x['fail_primary']:res['problems'].append(f"round {x['k']}: state result differs from the fresh measurement")
            if st['method'] in ['fuzz','bo'] and (st['history'][j][1]!=a['metrics']['max_tilt_deg'] or st['history'][j][2]!=a['flight_failure']):res['problems'].append(f"round {x['k']}: history entry differs")
        res['runs_in_this_batch']=sum(1 for x in st['runs'] if rounds[0]<=x['k']<=rounds[1])
        if res['runs_in_this_batch']!=rounds[1]-rounds[0]+1:res['problems'].append('not every round of this batch counted')
        out[cid]=res
    return out

def tables(state,order,upto):
    rows={}
    for cid in order:
        st=json.loads((state/'campaigns'/(cid.replace('/','_')+'.json')).read_text());key=f"{st['sut']}/{st['method']}"
        t=rows.setdefault(key,{'sut':st['sut'],'method':st['method'],'seeds':{}})
        runs=[x for x in st['runs'] if x.get('status')!='DEVELOPMENT_FAILED' and x['k']<=upto]
        fp=[x for x in runs if x['fail_primary']];ft=[x for x in runs if x['fail_task']]
        t['seeds'][st['seed']]={'runs':len(runs),'fail_primary':len(fp),'fail_task':len(ft),'first_fail_primary_k':fp[0]['k'] if fp else None,'first_fail_task_k':ft[0]['k'] if ft else None,
                                'cells_primary':sorted({tuple(x['cell']) for x in fp}),'cells_task':sorted({tuple(x['cell']) for x in ft})}
    for t in rows.values():
        s=t['seeds'];t['fail_primary']=sum(x['fail_primary'] for x in s.values());t['fail_task']=sum(x['fail_task'] for x in s.values())
        t['distinct_cells_primary']=len({c for x in s.values() for c in x['cells_primary']});t['distinct_cells_task']=len({c for x in s.values() for c in x['cells_task']})
        t['distinct_cells_primary_per_seed']=[len(s[k]['cells_primary']) for k in sorted(s)]
        t['first_fail_primary_k_per_seed']=[s[k]['first_fail_primary_k'] for k in sorted(s)]
        for x in s.values():x['cells_primary']=[list(c) for c in x['cells_primary']];x['cells_task']=[list(c) for c in x['cells_task']]
    return dict(sorted(rows.items()))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);p.add_argument('--jobs',type=int,default=1);args=p.parse_args()
    batch=args.batch.resolve();results=json.loads((batch/'results.json').read_text());plan=json.loads((batch/'plan.json').read_text())
    planned={r['id']:r for r in plan.get('runs',[])}
    jobs=[(r,(planned.get(r['id']) or r)['sim_seed']) for r in results['runs'] if r['status']!='NOT_RUN' and (ROOT/r['directory']).exists()]
    if args.jobs>1:
        with Pool(args.jobs) as pool:runs=pool.map(audit_run,jobs,chunksize=1)
    else:runs=[audit_run(j) for j in jobs]
    steps=sum(r['output_chain_counts']['steps'] for r in runs if r['output_chain_counts']);over=sum(r['output_chain_counts']['overwritten'] for r in runs if r['output_chain_counts'])
    seeds=[r['sim_seed'] for r in runs];campaign=bool(plan.get('state'))
    out={'batch':str(batch.relative_to(ROOT)),'stage':plan.get('stage'),'config':plan['config'],
        'audit_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['p8_audit.py','p8_metrics.py','p6_metrics.py','p5_metrics.py','p8_batch.py','p8_campaign.py','p8_conditions.py','p6_conditions.py','p1_metrics.py','p0_metrics.py','recovery.py','preparation_audit.py']},
        'runner_results':{k:results[k] for k in results if k!='runs'},
        'output_chain':{'gate':GATE,'neural_motor_steps':steps,'overwritten_motor_commands':over,'overwritten_fraction':over/steps if steps else None,
            'fraction_gate_met':bool(steps) and over/steps<GATE['overwritten_fraction'],'per_run_gate_failures':[r['id'] for r in runs if r['output_chain_gate_errors']],
            'max_applied_age_us':max((r['output_chain_counts'] or {}).get('max_applied_age_us',0) for r in runs) if runs else None,
            'runs_with_8ms_or_more':[r['id'] for r in runs if (r['output_chain_counts'] or {}).get('max_applied_age_us',0)>=8000]},
        'runs_checked':len(runs),'identification_outcomes':{r['id']:r['outcome'] for r in runs if r['kind']=='p6_ident'},
        'task_criterion_exceeded':{r['id']:((r.get('p8') or {}).get('task_criterion') or {}).get('reasons') for r in runs if ((r.get('p8') or {}).get('task_criterion') or {}).get('exceeded')},
        'independence':{'runs':len(runs),'distinct_seeds':len(set(seeds))},
        'max_horizontal_radius_m':max((r.get('max_horizontal_radius_m') or 0) for r in runs) if runs else None,
        'scope':'One frozen candidate, headless SITL only, x500, each run its own Gazebo seed. Flies and exports only; no model fitting or prediction.'}
    if campaign:
        state=ROOT/plan['state'];rounds=plan['rounds']
        out['campaigns']=campaigns_check(state,plan['order'],rounds,runs)
        out['infra_failures']=[r['id'] for r in runs if not r['passed']];out['infra_reruns']=[r['id'] for r in runs if r.get('infra_rerun')]
        uncounted_bad=[r['id'] for r in runs if not r['passed'] and r.get('counted')]
        out['tables']={'this_batch_cumulative_to_round':rounds[1],'by_sut_method':tables(state,plan['order'],rounds[1])}
        out['tables_b1']=tables(state,plan['order'],15) if rounds[1]>15 else None
        out['all_counted_runs_passed']=not uncounted_bad
        out['passed']=bool(not uncounted_bad and all(not c['problems'] for c in out['campaigns'].values()) and out['output_chain']['fraction_gate_met']
                           and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged') and out['independence']['distinct_seeds']==len(runs)
                           and all(r['passed'] for r in runs if r.get('counted')) and all((r.get('budget_check') or {}).get('equal',True) for r in runs))
    else:
        out['all_runs_passed']=bool(runs) and all(r['passed'] for r in runs)
        out['passed']=bool(out['all_runs_passed'] and out['output_chain']['fraction_gate_met'] and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged')
                           and out['independence']['distinct_seeds']==len(runs))
    out['runs']=runs
    (batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False,default=list)+'\n')
    print('runs',len(runs),'passed',out['passed'],'campaign problems',{k:v['problems'] for k,v in (out.get('campaigns') or {}).items() if v['problems']});return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
