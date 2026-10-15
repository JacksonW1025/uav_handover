#!/usr/bin/env python3
"""Independently re-check a finished P2 batch from raw run evidence and summarize it; never modifies runs.

Per run: P0 audit checks (PX4 exit, crash markers, ULog hash, analyzer verdict, recovery, executor, trace), per-motor
output-chain gate, and fresh recomputation of p1/p2 metrics compared with the stored files. Batch: output-chain
overwrite fraction; per (kind, condition, treatment) summaries; in-batch baseline motor curves and the RMS deviation of
each run in [change, change+0.5 s]; GRU distance to the in-batch RAPTOR baseline; elimination ratios
(N0 - Nx) / (N0 - baseline). Only runs of this batch are used (no splicing).
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from preparation_audit import flight
from p0_closure import GATE
from p1_batch import chain_gate
from p1_audit import row_of
import p1_metrics,p2_metrics
ROOT=Path(__file__).resolve().parents[1]
BASELINE={'p2_c_to_n':'p2_baseline_raptor','p2_n_to_c':'p2_baseline_classic'}
CONTROL={'p2_c_to_n':'N0','p2_n_to_c':'C0'}
GRID=np.arange(0,500,1)*1000  # 1 ms grid over [0, 0.5 s) in us
GRU_OFFSETS_S=[0.0,0.1,0.25,0.5,1.0,2.0]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stats(values):
    a=np.array([v for v in values if v is not None],float)
    return {'n':int(len(a)),'mean':float(a.mean()),'min':float(a.min()),'max':float(a.max()),'spread':float(a.max()-a.min())} if len(a) else None
def zoh(t_s,values,grid_us):
    t=np.round(np.asarray(t_s)*1e6).astype(np.int64);i=np.searchsorted(t,grid_us,side='right')-1
    v=np.asarray(values,float)[np.maximum(i,0)];v[i<0]=np.nan;return v

def motor_curve(m):return zoh(m['curves']['motor_t_s'],m['curves']['motor'],GRID)
def gru_at(m,offsets):
    c=m.get('gru_curves')
    if not c or not len(c['t_s']):return None
    t=np.round(np.asarray(c['t_s'])*1e6).astype(np.int64);g=np.asarray(c['gru'],float)
    out=[]
    for o in offsets:
        i=np.searchsorted(t,int(o*1e6),side='right')-1
        out.append(g[i] if i>=0 else np.full(16,np.nan))
    return np.array(out)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);args=p.parse_args()
    batch=args.batch.resolve();results=json.loads((batch/'results.json').read_text());plan=json.loads((batch/'plan.json').read_text())
    # Flight failures are results in exploration batches and in standard batches pre-registered that way.
    exploration=plan.get('mode')=='exploration' or bool(plan.get('flight_failures_are_results'));runs=[];metrics={}
    for r in results['runs']:
        run=ROOT/r['directory']
        if r['status']=='NOT_RUN' or not run.exists():continue
        a={'id':r['id'],'kind':r['kind'],'condition':r['condition'],'treatment':r['treatment'],**flight(run,r['kind'])}
        oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
        a['output_chain_gate_errors']=chain_gate(oc) if oc else ['missing']
        a['output_chain_counts']={'steps':sum(v['neural']['steps'] for v in oc.get('motors',{}).values()),
            'overwritten':sum(v['neural']['commands_overwritten_in_gazebo'] for v in oc.get('motors',{}).values())+4*(oc.get('px4_overwritten_publications',{}).get('neural_bracketed') or 0),
            'max_applied_age_us':max((v['neural'].get('applied_age_us') or {}).get('max') or 0 for v in oc.get('motors',{}).values())} if oc else None
        infra=a['px4_exit_codes']==[0] and not a['crash_markers'] and a['ulog_sha256_matches'] and not a['output_chain_gate_errors'] and (a.get('trace') or {}).get('status')=='MEASURED'
        if r['kind'].startswith('p2_'):
            stored=json.loads((run/'p2-metrics.json').read_text()) if (run/'p2-metrics.json').exists() else None
            fresh=json.loads(json.dumps(p2_metrics.analyze(run),allow_nan=False));metrics[r['id']]=fresh
            a['metrics_reproduced']=stored==fresh;a['p2_status']=fresh['p2_status'];a['problems']=fresh.get('problems')
            a['p1']=row_of(fresh) if 'primary' in fresh else None
            a['p2']={'entry':(fresh.get('entry') or {}).get('status'),'teacher_forcing':(fresh.get('teacher_forcing') or {}).get('status'),
                'coordination':(fresh.get('coordination') or {}).get('status'),'flight_outcome':(fresh.get('flight_outcome') or {}).get('outcome'),
                'flight_failure_reasons':(fresh.get('flight_outcome') or {}).get('reasons'),
                'longest_saturation_s':(fresh.get('flight_outcome') or {}).get('longest_continuous_saturation_s'),
                'gru_norm_written':(fresh.get('entry') or {}).get('gru_norm_written'),'clipped_total':(fresh.get('teacher_forcing') or {}).get('clipped_total')}
            measured=a['metrics_reproduced'] and fresh['p2_status']=='MEASURED'
            flight_failure=exploration and a['p2']['flight_outcome']=='FAILURE'
            a['flight_failure']=bool(infra and measured and flight_failure)
            a['passed']=bool(infra and measured and (a['passed'] or a['flight_failure']))
        elif r['kind'].startswith('p1_'):
            stored=json.loads((run/'p1-metrics.json').read_text()) if (run/'p1-metrics.json').exists() else None
            fresh=json.loads(json.dumps(p1_metrics.analyze(run),allow_nan=False));metrics[r['id']]=fresh
            a['metrics_reproduced']=stored==fresh;a['p1_status']=fresh['status'];a['p1']=row_of(fresh) if fresh['status']=='MEASURED' else None
            a['passed']=bool(a['passed'] and infra and a['metrics_reproduced'] and fresh['status']=='MEASURED')
        else:a['passed']=bool(a['passed'] and infra)
        runs.append(a)
    # In-batch baselines: motor mean curves and GRU curves per (baseline kind, condition).
    by=lambda kind,cond,treat=None:[r for r in runs if r['kind']==kind and r['condition']==cond and (treat is None or r['treatment']==treat) and r['id'] in metrics and 'curves' in metrics[r['id']]]
    rms_rows={};baselines={}
    for kind,bkind in BASELINE.items():
        for cond in sorted({r['condition'] for r in runs if r['kind']==kind}):
            base=by(bkind,cond)
            if not base:continue
            curves={b['id']:motor_curve(metrics[b['id']]) for b in base};mean=np.nanmean(np.stack(list(curves.values())),0)
            gru={b['id']:gru_at(metrics[b['id']],GRU_OFFSETS_S) for b in base};gvals=[g for g in gru.values() if g is not None]
            gmean=np.nanmean(np.stack(gvals),0) if gvals else None
            baselines[f'{bkind}:{cond}']={'runs':[b['id'] for b in base],'mean_motor_at_change':mean[0].tolist()}
            for r in by(kind,cond)+base:
                c=motor_curve(metrics[r['id']])
                ref=mean if r['kind']==kind or len(base)<2 else np.nanmean(np.stack([v for k,v in curves.items() if k!=r['id']]),0)
                row={'motor_rms_vs_baseline_0_0p5s':float(np.sqrt(np.nanmean((c-ref)**2))),'reference':'in-batch baseline mean'+(' (leave-one-out)' if r['kind']==bkind and len(base)>=2 else '')}
                g=gru_at(metrics[r['id']],GRU_OFFSETS_S)
                if g is not None and gmean is not None:row['gru_distance_to_baseline']={str(o):float(np.linalg.norm(g[i]-gmean[i])) for i,o in enumerate(GRU_OFFSETS_S)}
                rms_rows[r['id']]=row
    for r in runs:
        if r['id'] in rms_rows:r['vs_baseline']=rms_rows[r['id']]
    # Group summaries and elimination ratios.
    keys=['speed_at_change_m_s','max_altitude_loss_m','recovery_from_change_s','max_tilt_deg','max_error_to_active_target_m',
          'motor_step_at_change','motor_max_step_window','saturation_any_s','trigger_to_change_ms']
    table={}
    for r in runs:
        if not r.get('p1'):continue
        g=table.setdefault(f"{r['kind']}:{r['condition']}:{r['treatment']}",{'rows':[]});g['rows'].append(r)
    for name,g in table.items():
        rows=g.pop('rows');g['runs']=len(rows);g['ids']=[x['id'] for x in rows]
        g['settled']=sum(x['p1']['recovery_status']=='SETTLED' for x in rows)
        g['reference_classifications']=sorted({str(x['p1']['reference_classification']) for x in rows})
        for k in keys:g[k]=stats([x['p1'][k] for x in rows])
        g['motor_rms_vs_baseline_0_0p5s']=stats([x.get('vs_baseline',{}).get('motor_rms_vs_baseline_0_0p5s') for x in rows])
        for o in GRU_OFFSETS_S:
            vals=[(x.get('vs_baseline',{}).get('gru_distance_to_baseline') or {}).get(str(o)) for x in rows]
            if any(v is not None for v in vals):g.setdefault('gru_distance_to_baseline',{})[str(o)]=stats(vals)
        if rows[0].get('p2'):
            g['entry_verified']=sum(x['p2']['entry']=='VERIFIED' for x in rows);g['flight_failures']=sum(bool(x.get('flight_failure')) for x in rows)
            g['flight_failure_reasons']=sorted({y for x in rows for y in (x['p2']['flight_failure_reasons'] or [])})
    elimination={}
    for kind,control in CONTROL.items():
        for cond in sorted({r['condition'] for r in runs if r['kind']==kind}):
            c=table.get(f'{kind}:{cond}:{control}');b=table.get(f'{BASELINE[kind]}:{cond}:B')
            if not c or not b:continue
            for name,g in table.items():
                k,cc,t=name.split(':')
                if k!=kind or cc!=cond or t==control:continue
                ratios={}
                for metric in ['motor_step_at_change','max_altitude_loss_m','motor_rms_vs_baseline_0_0p5s']:
                    if not (c.get(metric) and b.get(metric) and g.get(metric)):continue
                    gap=c[metric]['mean']-b[metric]['mean']
                    ratios[metric]={'control_mean':c[metric]['mean'],'treatment_mean':g[metric]['mean'],'baseline_mean':b[metric]['mean'],
                        'ratio':(c[metric]['mean']-g[metric]['mean'])/gap if abs(gap)>1e-12 else None}
                elimination[name]=ratios
    steps=sum(r['output_chain_counts']['steps'] for r in runs if r['output_chain_counts']);over=sum(r['output_chain_counts']['overwritten'] for r in runs if r['output_chain_counts'])
    out={'batch':str(batch.relative_to(ROOT)),'mode':plan.get('mode'),
        'audit_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['p2_audit.py','p2_metrics.py','p1_metrics.py','p0_metrics.py','recovery.py','preparation_audit.py','p2_action_map.py']},
        'runner_results':{k:results[k] for k in results if k!='runs'},
        'output_chain':{'gate':GATE,'neural_motor_steps':steps,'overwritten_motor_commands':over,'overwritten_fraction':over/steps if steps else None,
            'fraction_gate_met':bool(steps) and over/steps<GATE['overwritten_fraction'],'per_run_gate_failures':[r['id'] for r in runs if r['output_chain_gate_errors']],
            'max_applied_age_us':max((r['output_chain_counts'] or {}).get('max_applied_age_us',0) for r in runs) if runs else None},
        'runs_checked':len(runs),'all_runs_passed':bool(runs) and all(r['passed'] for r in runs),
        'flight_failures':[r['id'] for r in runs if r.get('flight_failure')],
        'baselines':baselines,'summary':table,'elimination_ratios':elimination,'runs':runs,
        'definitions':{'motor_rms':'RMS over [change, change+0.5 s) (1 ms zero-order hold) and four motors of run minus the in-batch same-condition baseline mean curve; baseline runs use the leave-one-out mean',
            'gru_distance':'Euclidean distance between the committed GRU state at the given offset after the change and the in-batch RAPTOR baseline mean at the same offset',
            'elimination_ratio':'(control - treatment) / (control - baseline) of group means; control N0 (C->N) or C0 (N->C)'},
        'scope':'One frozen candidate, headless SITL only. Repeats share seed and configuration; exploratory budget, not a statistical test.'}
    out['passed']=bool(out['all_runs_passed'] and out['output_chain']['fraction_gate_met'] and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged'))
    (batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print('runs',len(runs),'passed',out['passed'],'flight_failures',out['flight_failures']);return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
