#!/usr/bin/env python3
"""Independently re-check a finished P3 batch from raw run evidence and summarize it; never modifies runs.

Per run: P0 audit checks (PX4 exit, crash markers, ULog hash, analyzer verdict, recovery, executor, trace), per-motor
output-chain gate, and fresh recomputation of p3_metrics and p3_memory compared with the stored files. Batch: output-chain
overwrite fraction; in-batch RAPTOR continuous-hover baseline motor and GRU curves (aligned at its re-capture); per run
the motor RMS deviation in [change, change+0.5 s) and GRU distance to that baseline for both C->N; group summaries per
(condition, treatment) for the second C->N, the N->C and the first C->N; elimination ratios (N0 - Nx)/(N0 - baseline)
per deactivation condition; memory-length summary. Only runs of this batch are used (no splicing).
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from preparation_audit import flight
from p0_closure import GATE
from p2_batch import chain_errors
import p3_metrics,p3_memory
ROOT=Path(__file__).resolve().parents[1]
GRID=np.arange(0,500,1)*1000
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stats(values):
    a=np.array([v for v in values if v is not None],float)
    return {'n':int(len(a)),'mean':float(a.mean()),'min':float(a.min()),'max':float(a.max()),'spread':float(a.max()-a.min())} if len(a) else None
def zoh(t_s,values,grid_us):
    t=np.round(np.asarray(t_s)*1e6).astype(np.int64);i=np.searchsorted(t,grid_us,side='right')-1
    v=np.asarray(values,float)[np.maximum(i,0)];v[i<0]=np.nan;return v
def motor_curve(e):return zoh(e['curves']['motor_t_s'],e['curves']['motor'],GRID)
def gru_at(curve,offsets):
    if not curve or not len(curve['t_s']):return None
    t=np.round(np.asarray(curve['t_s'])*1e6).astype(np.int64);g=np.asarray(curve['gru'],float);out=[]
    for o in offsets:
        i=np.searchsorted(t,int(o*1e6),side='right')-1;out.append(g[i] if i>=0 else np.full(16,np.nan))
    return np.array(out)

def event_row(e):
    jr=e['joint_recovery']
    return {'motor_step_at_change':e['motor']['step_at_change'],'motor_max_step_window':e['motor']['max_step_in_window'],
        'max_altitude_loss_m':e['max_altitude_loss_m'],'recovery_from_change_s':jr.get('from_change_s'),'recovery_status':jr['status'],
        'max_tilt_deg':e['max_tilt_deg'],'max_error_to_active_target_m':e['max_error_to_active_target_m'],'trigger_to_change_ms':e['trigger_to_change_ms'],
        'saturation_any_s':e['motor']['saturation_any_s'],'reference':(e.get('reference_at_takeover') or {}).get('classification')}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);args=p.parse_args()
    batch=args.batch.resolve();results=json.loads((batch/'results.json').read_text());plan=json.loads((batch/'plan.json').read_text())
    cfg=json.loads((ROOT/plan['config']).read_text());offsets=cfg['p3']['gru_distance_offsets_s'];P=p3_memory.load_policy()
    runs=[];metrics={};memory={}
    for r in results['runs']:
        run=ROOT/r['directory']
        if r['status']=='NOT_RUN' or not run.exists():continue
        a={'id':r['id'],'kind':r['kind'],'condition':r['condition'],'treatment':r['treatment'],**flight(run,r['kind'])}
        oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
        v=json.loads((run/'validation.json').read_text()) if (run/'validation.json').exists() else {}
        a['output_chain_gate_errors'],a['output_chain_errors_attributed_to_abort']=chain_errors(oc,str(v.get('reason') or '').startswith('safety:'))
        a['output_chain_counts']={'steps':sum(x['neural']['steps'] for x in oc.get('motors',{}).values()),
            'overwritten':sum(x['neural']['commands_overwritten_in_gazebo'] for x in oc.get('motors',{}).values())+4*(oc.get('px4_overwritten_publications',{}).get('neural_bracketed') or 0),
            'max_applied_age_us':max((x['neural'].get('applied_age_us') or {}).get('max') or 0 for x in oc.get('motors',{}).values())} if oc else None
        infra=a['px4_exit_codes']==[0] and not a['crash_markers'] and a['ulog_sha256_matches'] and not a['output_chain_gate_errors'] and (a.get('trace') or {}).get('status')=='MEASURED'
        stored=json.loads((run/'p3-metrics.json').read_text()) if (run/'p3-metrics.json').exists() else None
        fresh=json.loads(json.dumps(p3_metrics.analyze(run),allow_nan=False));metrics[r['id']]=fresh
        stored_m=json.loads((run/'p3-memory.json').read_text()) if (run/'p3-memory.json').exists() else None
        fresh_m=json.loads(json.dumps(p3_memory.analyze(run,P),allow_nan=False)) if fresh.get('p3_status')=='MEASURED' else None;memory[r['id']]=fresh_m
        a['metrics_reproduced']=stored==fresh;a['memory_reproduced']=stored_m==fresh_m;a['p3_status']=fresh['p3_status'];a['problems']=fresh.get('problems')
        a['memory_status']=(fresh_m or {}).get('status');a['replay_validation']=(fresh_m or {}).get('validation')
        a['flight_outcome']=(fresh.get('flight_outcome') or {}).get('outcome');a['flight_failure_reasons']=(fresh.get('flight_outcome') or {}).get('reasons')
        a['deactivation']=fresh.get('deactivation')
        a['evidence']={k:(fresh.get(k) or {}).get('status') for k in ['first_entry','exit','second_entry','teacher_forcing']}
        a['events']={n:event_row(e) for n,e in fresh.get('events',{}).items()}
        if 'N_to_C' in fresh.get('events',{}):a['events']['N_to_C']['motor_rms_vs_classic_hold']=fresh['events']['N_to_C']['motor_rms_vs_classic_hold_0_0p5s']
        measured=a['metrics_reproduced'] and a['memory_reproduced'] and fresh['p3_status']=='MEASURED' and a['memory_status']=='MEASURED'
        a['flight_failure']=bool(infra and measured and a['flight_outcome']=='FAILURE')
        a['passed']=bool(infra and measured and (a['passed'] or a['flight_failure']))
        runs.append(a)
    # In-batch RAPTOR continuous-hover baseline (re-capture), motor and GRU curves.
    base=[r for r in runs if r['kind']=='p3_baseline_raptor' and r['id'] in metrics and 'baseline_recapture' in metrics[r['id']].get('events',{})]
    bcurves={b['id']:motor_curve(metrics[b['id']]['events']['baseline_recapture']) for b in base}
    bgru={b['id']:gru_at(metrics[b['id']]['gru_curves']['baseline_recapture'],offsets) for b in base}
    bmean=np.nanmean(np.stack(list(bcurves.values())),0) if bcurves else None
    gvals=[g for g in bgru.values() if g is not None];gmean=np.nanmean(np.stack(gvals),0) if gvals else None
    baseline={'runs':[b['id'] for b in base],'mean_motor_at_recapture':bmean[0].tolist() if bmean is not None else None}
    for r in runs:
        m=metrics.get(r['id']) or {}
        for name in ['first_C_to_N','second_C_to_N','baseline_recapture']:
            if name not in m.get('events',{}) or bmean is None:continue
            c=motor_curve(m['events'][name])
            loo=r['kind']=='p3_baseline_raptor' and name=='baseline_recapture' and len(base)>=2
            ref=np.nanmean(np.stack([v for k,v in bcurves.items() if k!=r['id']]),0) if loo else bmean
            r['events'][name]['motor_rms_vs_baseline']=float(np.sqrt(np.nanmean((c-ref)**2)))
            r['events'][name]['motor_rms_reference']='in-batch baseline re-capture mean'+(' (leave-one-out)' if loo else '')
            g=gru_at((m.get('gru_curves') or {}).get(name),offsets)
            if g is not None and gmean is not None:
                gref=np.nanmean(np.stack([v for k,v in bgru.items() if k!=r['id'] and v is not None]),0) if loo else gmean
                r['events'][name]['gru_distance_to_baseline']={str(o):float(np.linalg.norm(g[i]-gref[i])) for i,o in enumerate(offsets)}
    # Group summaries.
    keys=['motor_step_at_change','motor_max_step_window','max_altitude_loss_m','recovery_from_change_s','max_tilt_deg','max_error_to_active_target_m','trigger_to_change_ms','saturation_any_s','motor_rms_vs_baseline']
    def summarize(rows,event):
        ev=[x['events'][event] for x in rows if event in x['events']]
        g={'runs':len(ev),'ids':[x['id'] for x in rows if event in x['events']],'recovery':sorted({e['recovery_status'] for e in ev}),'references':sorted({str(e['reference']) for e in ev})}
        for k in keys+(['motor_rms_vs_classic_hold'] if event=='N_to_C' else []):g[k]=stats([e.get(k) for e in ev])
        for o in offsets:
            vals=[(e.get('gru_distance_to_baseline') or {}).get(str(o)) for e in ev]
            if any(v is not None for v in vals):g.setdefault('gru_distance_to_baseline',{})[str(o)]=stats(vals)
        return g
    groups={}
    for r in runs:groups.setdefault((r['kind'],r['condition'],r['treatment']),[]).append(r)
    table={'second_C_to_N':{},'N_to_C':{},'first_C_to_N':{},'baseline_recapture':{}}
    for (kind,cond,treat),rows in sorted(groups.items()):
        key=f'{cond}:{treat}'
        if kind=='p3_baseline_raptor':table['baseline_recapture'][key]=summarize(rows,'baseline_recapture')
        else:
            table['second_C_to_N'][key]=summarize(rows,'second_C_to_N');table['N_to_C'][key]=summarize(rows,'N_to_C')
            table['second_C_to_N'][key]['evidence_verified']=sum(all(v=='VERIFIED' for v in x['evidence'].values()) for x in rows)
            table['second_C_to_N'][key]['flight_failures']=sum(bool(x['flight_failure']) for x in rows)
            table['second_C_to_N'][key]['deactivation_actual_s']=stats([(x['deactivation'] or {}).get('actual_owner_s') for x in rows])
            table['second_C_to_N'][key]['deactivation_request_interval_s']=stats([(x['deactivation'] or {}).get('request_interval_s') for x in rows])
            table['second_C_to_N'][key]['displacement_horizontal_m']=stats([float(np.hypot(*x['deactivation']['displacement_ned_m'][:2])) for x in rows if x['deactivation']])
            table['second_C_to_N'][key]['yaw_change_deg']=stats([x['deactivation']['yaw_change_deg'] for x in rows if x['deactivation']])
            dm=[(metrics[x['id']].get('deactivation_memory') or {}).get('distance_to_exit_gru') for x in rows]
            table['second_C_to_N'][key]['shadow_gru_distance_to_exit']={k:stats([d[k] for d in dm if d]) for k in ['max','last']}
        table['first_C_to_N'][key]=summarize(rows,'first_C_to_N')
    table['first_C_to_N_pooled']=summarize(runs,'first_C_to_N')
    # Elimination ratios at the second C->N, per deactivation condition, against the in-batch baseline re-capture.
    b=table['baseline_recapture'].get('R:B');elimination={}
    for key,g in table['second_C_to_N'].items():
        cond,treat=key.split(':');c=table['second_C_to_N'].get(f'{cond}:N0')
        if treat=='N0' or not c or not b:continue
        ratios={}
        for metric in ['motor_step_at_change','max_altitude_loss_m','motor_rms_vs_baseline']:
            if not (c.get(metric) and b.get(metric) and g.get(metric)):continue
            gap=c[metric]['mean']-b[metric]['mean']
            ratios[metric]={'control_mean':c[metric]['mean'],'treatment_mean':g[metric]['mean'],'baseline_mean':b[metric]['mean'],'ratio':(c[metric]['mean']-g[metric]['mean'])/gap if abs(gap)>1e-12 else None}
        elimination[key]=ratios
    # Memory length.
    mem={}
    for r in runs:
        for s in (memory.get(r['id']) or {}).get('segments',[]):
            k=f"{s['segment']}|{s['initial']}"+(f"|{r['condition']}:{r['treatment']}" if s['segment'].startswith(('second_entry','teacher','shadow')) else '')
            mem.setdefault(k,[]).append((s['steps_to_stay_below'],s['seconds_to_stay_below'],s['steps_compared']))
    memory_summary={k:{'cases':len(v),'not_reached':sum(x[0] is None for x in v),'steps':stats([x[0] for x in v]),'seconds':stats([x[1] for x in v]),
                       'median_steps':float(np.median([x[0] for x in v if x[0] is not None])) if any(x[0] is not None for x in v) else None} for k,v in sorted(mem.items())}
    replay={'max_abs_error':max(((r['replay_validation'] or {}).get('max_abs_error') or 0) for r in runs) if runs else None,
            'steps_checked':sum(((r['replay_validation'] or {}).get('checked') or 0) for r in runs),
            'steps_over_1e-5':sum(((r['replay_validation'] or {}).get('steps_over_1e-5') or 0) for r in runs)}
    steps=sum(r['output_chain_counts']['steps'] for r in runs if r['output_chain_counts']);over=sum(r['output_chain_counts']['overwritten'] for r in runs if r['output_chain_counts'])
    out={'batch':str(batch.relative_to(ROOT)),'config':plan['config'],
        'audit_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['p3_audit.py','p3_metrics.py','p3_memory.py','p2_metrics.py','p1_metrics.py','p0_metrics.py','recovery.py','preparation_audit.py','p2_action_map.py']},
        'policy_sha256':P['sha256'],'policy_example_max_abs_error':p3_memory.example_check(P),
        'runner_results':{k:results[k] for k in results if k!='runs'},
        'output_chain':{'gate':GATE,'neural_motor_steps':steps,'overwritten_motor_commands':over,'overwritten_fraction':over/steps if steps else None,
            'fraction_gate_met':bool(steps) and over/steps<GATE['overwritten_fraction'],'per_run_gate_failures':[r['id'] for r in runs if r['output_chain_gate_errors']],
            'max_applied_age_us':max((r['output_chain_counts'] or {}).get('max_applied_age_us',0) for r in runs) if runs else None},
        'runs_checked':len(runs),'all_runs_passed':bool(runs) and all(r['passed'] for r in runs),'flight_failures':[r['id'] for r in runs if r.get('flight_failure')],
        'baseline':baseline,'summary':table,'elimination_ratios':elimination,'memory_length':memory_summary,'replay_validation':replay,'runs':runs,
        'definitions':{'motor_rms':'RMS over [change, change+0.5 s) (1 ms zero-order hold) and four motors of run minus the in-batch RAPTOR continuous-hover baseline mean curve aligned at its re-capture; baseline runs use the leave-one-out mean',
            'gru_distance':'Euclidean distance between the committed GRU at the given offset after the change and the in-batch baseline mean at the same offset after its re-capture',
            'elimination_ratio':'(N0 - Nx) / (N0 - baseline) of group means at the second C->N within one deactivation condition',
            'memory_length':cfg['p3']['memory_length']['method']},
        'scope':'One frozen candidate, headless SITL only. Repeats share seed and configuration; exploratory budget, not a statistical test.'}
    out['passed']=bool(out['all_runs_passed'] and out['output_chain']['fraction_gate_met'] and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged'))
    (batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print('runs',len(runs),'passed',out['passed'],'flight_failures',out['flight_failures']);return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
