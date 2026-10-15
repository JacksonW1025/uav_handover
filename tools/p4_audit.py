#!/usr/bin/env python3
"""Independently re-check a finished P4 batch from raw run evidence and summarize it with 95% intervals; never
modifies runs.

Per run: P0 audit checks (PX4 exit, crash markers, ULog hash, analyzer verdict, recovery, executor, trace), per-motor
output-chain gate, fresh recomputation of p2_metrics or p3_metrics (+ p3_memory) and of p4_metrics, each compared with
the stored file. Batch: output-chain overwrite fraction; per analysis unit (condition) the in-batch RAPTOR baseline
(config p4.baseline_condition) motor and GRU curves aligned at its re-capture; per run the motor RMS deviation in
[change, change+0.5 s) and the GRU distance to that baseline at the measured takeover (P3 kinds: second C->N; P2 kinds:
the C->N); group means with 95% t intervals; total cost N0 - baseline and elimination ratios (N0 - Nx)/(N0 - baseline)
with 95% bootstrap intervals; baseline state matching (01b); seeds and headings; memory length (P3 kinds). Only runs of
this batch are used (no splicing).
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from scipy import stats as sst
from preparation_audit import flight
from p0_closure import GATE
from p2_batch import chain_errors
from p1_audit import row_of
import p2_metrics,p3_metrics,p3_memory,p4_metrics
ROOT=Path(__file__).resolve().parents[1]
GRID=np.arange(0,500,1)*1000
METRICS=['motor_step_at_change','max_altitude_loss_m','motor_rms_vs_baseline','max_tilt_deg']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fresh(x):return json.loads(json.dumps(x,allow_nan=False))
def stats(values):
    a=np.array([v for v in values if v is not None],float)
    if not len(a):return None
    out={'n':int(len(a)),'mean':float(a.mean()),'min':float(a.min()),'max':float(a.max()),'values':a.tolist()}
    if len(a)>1:
        sd=float(a.std(ddof=1));h=float(sst.t.ppf(.975,len(a)-1)*sd/np.sqrt(len(a)));out.update({'sd':sd,'ci95':[out['mean']-h,out['mean']+h]})
    return out
def zoh(t_s,values,grid_us):
    t=np.round(np.asarray(t_s)*1e6).astype(np.int64);i=np.searchsorted(t,grid_us,side='right')-1
    v=np.asarray(values,float)[np.maximum(i,0)];v[i<0]=np.nan;return v
def gru_at(curve,offsets):
    if not curve or not len(curve['t_s']):return None
    t=np.round(np.asarray(curve['t_s'])*1e6).astype(np.int64);g=np.asarray(curve['gru'],float);out=[]
    for o in offsets:
        i=np.searchsorted(t,int(o*1e6),side='right')-1;out.append(g[i] if i>=0 else np.full(16,np.nan))
    return np.array(out)

def p3_event_row(e):
    jr=e['joint_recovery']
    return {'motor_step_at_change':e['motor']['step_at_change'],'motor_max_step_window':e['motor']['max_step_in_window'],'max_altitude_loss_m':e['max_altitude_loss_m'],
        'recovery_from_change_s':jr.get('from_change_s'),'recovery_status':jr['status'],'max_tilt_deg':e['max_tilt_deg'],
        'max_error_to_active_target_m':e['max_error_to_active_target_m'],'trigger_to_change_ms':e['trigger_to_change_ms'],
        'saturation_any_s':e['motor']['saturation_any_s'],'reference':(e.get('reference_at_takeover') or {}).get('classification')}

def bootstrap_ratio(c,t,b,rng,n):
    c,t,b=(np.asarray(x,float) for x in (c,t,b))
    C=c[rng.integers(0,len(c),(n,len(c)))].mean(1);T=t[rng.integers(0,len(t),(n,len(t)))].mean(1);B=b[rng.integers(0,len(b),(n,len(b)))].mean(1)
    ok=np.abs(C-B)>1e-9;r=(C[ok]-T[ok])/(C[ok]-B[ok]);d=C-B
    return {'ratio_ci95':[float(np.percentile(r,2.5)),float(np.percentile(r,97.5))] if len(r) else None,'resamples_used':int(ok.sum()),
            'total_cost_ci95':[float(np.percentile(d,2.5)),float(np.percentile(d,97.5))]}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);args=p.parse_args()
    batch=args.batch.resolve();results=json.loads((batch/'results.json').read_text());plan=json.loads((batch/'plan.json').read_text())
    cfg=json.loads((ROOT/plan['config']).read_text());p4=cfg['p4'];offsets=cfg['p3']['gru_distance_offsets_s'];P=p3_memory.load_policy()
    planned={r['id']:r for r in plan['runs']};runs=[];metrics={};memory={}
    for r in results['runs']:
        run=ROOT/r['directory']
        if r['status']=='NOT_RUN' or not run.exists():continue
        p3kind=r['kind'].startswith('p3_')
        a={'id':r['id'],'kind':r['kind'],'condition':r['condition'],'treatment':r['treatment'],'sim_seed':planned[r['id']]['sim_seed'],
           'initial_yaw_deg':planned[r['id']]['initial_yaw_deg'],**flight(run,r['kind'])}
        oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
        v=json.loads((run/'validation.json').read_text()) if (run/'validation.json').exists() else {}
        a['output_chain_gate_errors'],a['output_chain_errors_attributed_to_abort']=chain_errors(oc,str(v.get('reason') or '').startswith('safety:'))
        a['output_chain_counts']={'steps':sum(x['neural']['steps'] for x in oc.get('motors',{}).values()),
            'overwritten':sum(x['neural']['commands_overwritten_in_gazebo'] for x in oc.get('motors',{}).values())+4*(oc.get('px4_overwritten_publications',{}).get('neural_bracketed') or 0),
            'max_applied_age_us':max((x['neural'].get('applied_age_us') or {}).get('max') or 0 for x in oc.get('motors',{}).values())} if oc else None
        infra=a['px4_exit_codes']==[0] and not a['crash_markers'] and a['ulog_sha256_matches'] and not a['output_chain_gate_errors'] and (a.get('trace') or {}).get('status')=='MEASURED'
        name='p3-metrics.json' if p3kind else 'p2-metrics.json'
        stored=json.loads((run/name).read_text()) if (run/name).exists() else None
        f=fresh((p3_metrics if p3kind else p2_metrics).analyze(run));metrics[r['id']]=f;a['metrics_reproduced']=stored==f
        status=f.get('p3_status') if p3kind else f.get('p2_status');a['metrics_status']=status;a['problems']=f.get('problems')
        ok=a['metrics_reproduced'] and status=='MEASURED'
        if p3kind:
            sm=json.loads((run/'p3-memory.json').read_text()) if (run/'p3-memory.json').exists() else None
            fm=fresh(p3_memory.analyze(run,P)) if status=='MEASURED' else None;memory[r['id']]=fm
            a['memory_reproduced']=sm==fm;a['memory_status']=(fm or {}).get('status');a['replay_validation']=(fm or {}).get('validation')
            ok=ok and a['memory_reproduced'] and a['memory_status']=='MEASURED'
            a['evidence']={k:(f.get(k) or {}).get('status') for k in ['first_entry','exit','second_entry','teacher_forcing']}
            a['deactivation']=f.get('deactivation');fo=f.get('flight_outcome') or {}
            a['events']={n:p3_event_row(e) for n,e in f.get('events',{}).items()}
            if 'N_to_C' in a['events']:a['events']['N_to_C']['motor_rms_vs_classic_hold']=f['events']['N_to_C']['motor_rms_vs_classic_hold_0_0p5s']
        else:
            a['evidence']={'entry':(f.get('entry') or {}).get('status'),'teacher_forcing':(f.get('teacher_forcing') or {}).get('status'),
                           'capture':(f.get('reference_at_takeover') or {}).get('classification')}
            fo=f.get('flight_outcome') or {};name_=('C_to_N' if r['kind']=='p2_c_to_n' else 'baseline_recapture')
            a['events']={name_:{**row_of(f),'reference':(f.get('reference_at_takeover') or {}).get('classification')}} if 'primary' in f else {}
        s4=json.loads((run/'p4-metrics.json').read_text()) if (run/'p4-metrics.json').exists() else None
        f4=fresh(p4_metrics.analyze(run));a['p4_reproduced']=s4==f4;a['p4_status']=f4['status'];a['p4_problems']=f4['problems']
        a['independence']=f4.get('independence');a['takeover_state']=f4.get('takeover_state');a['teacher_forcing_coverage']=f4.get('teacher_forcing_coverage')
        a['max_horizontal_radius_m']=f4.get('max_horizontal_radius_m');a['planned_path']=f4.get('planned_path')
        ok=ok and a['p4_reproduced'] and f4['status']=='MEASURED'
        # Takeover state (speed/acceleration along the motion axis) attached to the measured event.
        ts=f4.get('takeover_state') or {}
        for n,e in a['events'].items():
            key={'C_to_N':'subject','baseline_recapture':'subject' if not p3kind else 'baseline_recapture'}.get(n,n)
            if key in ts:e['speed_along_axis_m_s']=ts[key]['speed_along_axis_m_s'];e['acceleration_along_axis_m_s2']=ts[key]['acceleration_along_axis_m_s2']
        a['flight_outcome']=fo.get('outcome');a['flight_failure_reasons']=fo.get('reasons')
        a['flight_failure']=bool(infra and ok and a['flight_outcome']=='FAILURE')
        a['passed']=bool(infra and ok and (a['passed'] or a['flight_failure']))
        runs.append(a)
    # Measured takeover per run: P3 kinds the second C->N (sequence) or the re-capture (baseline); P2 kinds the C->N or re-capture.
    def measured(r):
        if r['kind']=='p3_sequence':return 'second_C_to_N'
        if r['kind']=='p2_c_to_n':return 'C_to_N'
        return 'baseline_recapture'
    def curves(r):
        m=metrics[r['id']];n=measured(r)
        if r['kind'].startswith('p3_'):e=m['events'][n];return zoh(e['curves']['motor_t_s'],e['curves']['motor'],GRID),gru_at(m['gru_curves'].get(n),offsets)
        return zoh(m['curves']['motor_t_s'],m['curves']['motor'],GRID),gru_at(m.get('gru_curves'),offsets)
    bmap=p4['baseline_condition'];units={}
    for cond in sorted({r['condition'] for r in runs if r['condition'] in bmap}):
        base=[r for r in runs if r['condition']==bmap[cond] and r['treatment']=='B' and r['id'] in metrics and measured(r) in r['events']]
        bc={b['id']:curves(b) for b in base}
        mean=np.nanmean(np.stack([c[0] for c in bc.values()]),0) if bc else None
        gv=[c[1] for c in bc.values() if c[1] is not None];gmean=np.nanmean(np.stack(gv),0) if gv else None
        units[cond]={'baseline_condition':bmap[cond],'baseline_runs':[b['id'] for b in base],'mean_motor_at_recapture':mean[0].tolist() if mean is not None else None}
        members=[r for r in runs if r['condition']==cond and r['treatment']!='B' and r['id'] in metrics and measured(r) in r['events']]+base
        for r in members:
            if mean is None:continue
            c,g=curves(r);e=r['events'][measured(r)];loo=r in base and len(base)>=2
            ref=np.nanmean(np.stack([v[0] for k,v in bc.items() if k!=r['id']]),0) if loo else mean
            e['motor_rms_vs_baseline']=float(np.sqrt(np.nanmean((c-ref)**2)));e['motor_rms_reference']=f"in-batch {bmap[cond]} baseline mean"+(' (leave-one-out)' if loo else '')
            if g is not None and gmean is not None:
                gref=np.nanmean(np.stack([v[1] for k,v in bc.items() if k!=r['id'] and v[1] is not None]),0) if loo else gmean
                e['gru_distance_to_baseline']={str(o):float(np.linalg.norm(g[i]-gref[i])) for i,o in enumerate(offsets)}
    keys=['motor_step_at_change','motor_max_step_window','max_altitude_loss_m','recovery_from_change_s','max_tilt_deg','max_error_to_active_target_m',
          'trigger_to_change_ms','saturation_any_s','motor_rms_vs_baseline','speed_along_axis_m_s','acceleration_along_axis_m_s2']
    def summarize(rows,event):
        ev=[x['events'][event] for x in rows if event in x['events']]
        g={'runs':len(ev),'ids':[x['id'] for x in rows if event in x['events']],'recovery':sorted({str(e['recovery_status']) for e in ev}),'references':sorted({str(e.get('reference')) for e in ev})}
        for k in keys+(['motor_rms_vs_classic_hold'] if event=='N_to_C' else []):g[k]=stats([e.get(k) for e in ev])
        for o in offsets:
            vals=[(e.get('gru_distance_to_baseline') or {}).get(str(o)) for e in ev]
            if any(v is not None for v in vals):g.setdefault('gru_distance_to_baseline',{})[str(o)]=stats(vals)
        g['flight_failures']=sum(bool(x['flight_failure']) for x in rows);g['evidence_all_verified']=sum(all(v in ('VERIFIED','activation_reset_hold','setpoint_timeout_hold',None) for v in x['evidence'].values()) for x in rows)
        return g
    groups={}
    for r in runs:groups.setdefault(f"{r['condition']}:{r['treatment']}",[]).append(r)
    table={k:summarize(v,measured(v[0])) for k,v in sorted(groups.items())}
    for k,v in groups.items():
        if v[0]['kind']=='p3_sequence':
            table[k]['N_to_C']=summarize(v,'N_to_C');table[k]['deactivation_actual_s']=stats([(x['deactivation'] or {}).get('actual_owner_s') for x in v])
            if v[0]['treatment']=='N2':table[k]['teacher_forcing_native_steps_before_entry']=stats([(x['teacher_forcing_coverage'] or {}).get('consecutive_teacher_forced_native_steps') for x in v])
        if v[0]['kind']=='p2_c_to_n' and v[0]['treatment']=='N2':table[k]['teacher_forcing_native_steps_before_entry']=stats([(x['teacher_forcing_coverage'] or {}).get('consecutive_teacher_forced_native_steps') for x in v])
    p3runs=[r for r in runs if r['kind'].startswith('p3_')]
    first=summarize(p3runs,'first_C_to_N') if p3runs else None
    # Cost decomposition per unit and treatment, with bootstrap intervals.
    rng=np.random.default_rng(p4['independence']['master_seed']);nboot=20000;elimination={}
    for cond,u in units.items():
        c=groups.get(f'{cond}:N0');b=groups.get(f"{u['baseline_condition']}:B")
        if not c or not b:continue
        ev_c=measured(c[0]);ev_b='baseline_recapture'
        for t in sorted({r['treatment'] for r in runs if r['condition']==cond and r['treatment'] not in ('N0','B')}):
            g=groups[f'{cond}:{t}'];out={}
            for metric in METRICS:
                cv=[x['events'][ev_c].get(metric) for x in c];tv=[x['events'][ev_c].get(metric) for x in g];bv=[x['events'][ev_b].get(metric) for x in b]
                if None in cv+tv+bv:continue
                gap=np.mean(cv)-np.mean(bv);ratio=(np.mean(cv)-np.mean(tv))/gap if abs(gap)>1e-12 else None
                out[metric]={'control_mean':float(np.mean(cv)),'treatment_mean':float(np.mean(tv)),'baseline_mean':float(np.mean(bv)),'total_cost':float(gap),
                             'ratio':ratio,'remainder_attributed_to_capture':None if ratio is None else 1-ratio,**bootstrap_ratio(cv,tv,bv,rng,nboot)}
            elimination[f'{cond}:{t}']=out
        # Total cost even without a treatment group.
        units[cond]['total_cost']={}
        for metric in METRICS:
            cv=[x['events'][ev_c].get(metric) for x in c];bv=[x['events'][ev_b].get(metric) for x in b]
            if None in cv+bv:continue
            d=np.array([np.mean(np.asarray(cv)[rng.integers(0,len(cv),len(cv))])-np.mean(np.asarray(bv)[rng.integers(0,len(bv),len(bv))]) for _ in range(nboot)])
            units[cond]['total_cost'][metric]={'N0_minus_baseline':float(np.mean(cv)-np.mean(bv)),'ci95':[float(np.percentile(d,2.5)),float(np.percentile(d,97.5))]}
    # Baseline state matching (01b).
    bm=p4['baseline_matching'];matching={}
    for cond,u in units.items():
        if cond in ('D2',):continue
        handover=[x['events'][measured(x)] for x in runs if x['condition']==cond and x['treatment']!='B' and measured(x) in x['events']]
        base=[x for x in runs if x['id'] in u['baseline_runs']]
        if not handover or not base:continue
        hv=float(np.mean([e['speed_along_axis_m_s'] for e in handover]));ha=float(np.mean([e['acceleration_along_axis_m_s2'] for e in handover]))
        rows=[{'id':x['id'],'speed_along_axis_m_s':x['events']['baseline_recapture']['speed_along_axis_m_s'],'acceleration_along_axis_m_s2':x['events']['baseline_recapture']['acceleration_along_axis_m_s2']} for x in base]
        for row in rows:row['matched']=abs(row['speed_along_axis_m_s']-hv)<=bm['speed_tolerance_m_s'] and abs(row['acceleration_along_axis_m_s2']-ha)<=bm['acceleration_tolerance_m_s2']
        matching[cond]={'handover_mean_speed_m_s':hv,'handover_mean_acceleration_m_s2':ha,'baselines':rows,'all_matched':all(x['matched'] for x in rows)}
    # Memory length (P3 kinds).
    mem={}
    for r in p3runs:
        for s in (memory.get(r['id']) or {}).get('segments',[]):
            k=f"{s['segment']}|{s['initial']}"+(f"|{r['condition']}:{r['treatment']}" if s['segment'].startswith(('second_entry','teacher','shadow')) else '')
            mem.setdefault(k,[]).append((s['steps_to_stay_below'],s['seconds_to_stay_below']))
    memory_summary={k:{'cases':len(v),'not_reached':sum(x[0] is None for x in v),'steps':stats([x[0] for x in v]),'seconds':stats([x[1] for x in v])} for k,v in sorted(mem.items())}
    for v in memory_summary.values():
        for s in ('steps','seconds'):
            if v[s]:v[s].pop('values',None)
    replay={'max_abs_error':max(((r.get('replay_validation') or {}).get('max_abs_error') or 0) for r in p3runs) if p3runs else None,
            'steps_checked':sum(((r.get('replay_validation') or {}).get('checked') or 0) for r in p3runs),
            'steps_over_1e-5':sum(((r.get('replay_validation') or {}).get('steps_over_1e-5') or 0) for r in p3runs)}
    seeds=[r['sim_seed'] for r in runs]
    independence={'runs':len(runs),'distinct_seeds':len(set(seeds)),'headings_deg':[r['initial_yaw_deg'] for r in runs],
                  'max_heading_error_deg':max(abs((r['independence'] or {}).get('heading_error_deg') or 0) for r in runs) if runs else None,
                  'seed_on_gazebo_command':all((r['independence'] or {}).get('gazebo_seed_argument')==str(r['sim_seed']) for r in runs)}
    steps=sum(r['output_chain_counts']['steps'] for r in runs if r['output_chain_counts']);over=sum(r['output_chain_counts']['overwritten'] for r in runs if r['output_chain_counts'])
    out={'batch':str(batch.relative_to(ROOT)),'config':plan['config'],
        'audit_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['p4_audit.py','p4_metrics.py','p3_metrics.py','p3_memory.py','p2_metrics.py','p1_metrics.py','p0_metrics.py','recovery.py','preparation_audit.py','p2_action_map.py']},
        'policy_sha256':P['sha256'],'runner_results':{k:results[k] for k in results if k!='runs'},
        'output_chain':{'gate':GATE,'neural_motor_steps':steps,'overwritten_motor_commands':over,'overwritten_fraction':over/steps if steps else None,
            'fraction_gate_met':bool(steps) and over/steps<GATE['overwritten_fraction'],'per_run_gate_failures':[r['id'] for r in runs if r['output_chain_gate_errors']],
            'max_applied_age_us':max((r['output_chain_counts'] or {}).get('max_applied_age_us',0) for r in runs) if runs else None},
        'runs_checked':len(runs),'all_runs_passed':bool(runs) and all(r['passed'] for r in runs),'flight_failures':[r['id'] for r in runs if r.get('flight_failure')],
        'independence':independence,'units':units,'summary':table,'first_C_to_N_pooled':first,'elimination':elimination,'baseline_matching':matching,
        'memory_length':memory_summary,'replay_validation':replay,'max_horizontal_radius_m':max((r['max_horizontal_radius_m'] or 0) for r in runs) if runs else None,'runs':runs,
        'definitions':{'measured_takeover':'p3_sequence: second C->N; p2_c_to_n: the C->N; baselines: RAPTOR re-capture after its 200 ms setpoint timeout',
            'motor_rms':'RMS over [change, change+0.5 s) (1 ms zero-order hold) and four motors of run minus the in-batch baseline mean curve of the unit (config p4.baseline_condition) aligned at its re-capture; baseline runs use the leave-one-out mean',
            'gru_distance':'Euclidean distance between the committed GRU at the given offset after the change and the in-batch baseline mean at the same offset after its re-capture',
            'group_ci':p4['statistics']['group_ci'],'ratio_ci':p4['statistics']['ratio_ci'],'cost_decomposition':p4['cost_decomposition'],
            'takeover_state':'speed along the motion axis at the change and mean EKF acceleration along it over [change - 50 ms, change] (p4_metrics)'},
        'scope':'One frozen candidate, headless SITL only. Each run has its own Gazebo seed (and heading in 01a); intervals describe run-to-run variation of this SITL setup.'}
    out['passed']=bool(out['all_runs_passed'] and out['output_chain']['fraction_gate_met'] and results.get('status')=='PASS' and results.get('complete') and results.get('candidate_unchanged')
                       and independence['distinct_seeds']==len(runs) and independence['seed_on_gazebo_command'])
    (batch/'batch-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print('runs',len(runs),'passed',out['passed'],'flight_failures',out['flight_failures']);return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
