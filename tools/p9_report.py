#!/usr/bin/env python3
"""Read-only P9 outcome/cost/denominator report, including partial/negative runs."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import numpy as np
from scipy.stats import spearmanr
from p9_model import ROOT, sha, write
from p9_run import budget_counts
from p9_search import observed_brackets


def wilson(k,n):
    if not n:return None
    z=1.959963984540054;p=k/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,mid-r),min(1.,mid+r)]


def report(preparation,formal,out):
    out.mkdir(parents=True,exist_ok=False)
    doc=json.loads((formal/'results.json').read_text()) if (formal/'results.json').exists() else {'status':'NOT_STARTED','runs':[]}
    items=[json.loads(x) for x in (preparation/'attempts.jsonl').read_text().splitlines()]
    rows=[]
    for r in doc['runs']:
        p=json.loads((formal/r['id']/'prediction-before-query.json').read_text())['prediction'];m=r.get('p9',{})
        comparable=bool(m.get('complete_window') and m.get('max_tilt_deg') is not None)
        peak=m.get('max_tilt_deg');pred=p['point_tilt_deg']
        row={'id':r['id'],'stage':r['stage'],'treatment':r['treatment'],'sim_seed':r['sim_seed'],'condition':r['condition'],
             'family':r.get('family'),'phase_s':r.get('phase_s'),'cluster':r.get('cluster'),'elapsed_s':r.get('elapsed_s'),
             'speed_m_s':r['case']['speed_m_s'],'heading_deg':r['case']['heading_deg'],
             'windows_s':json.dumps(r['case']['windows_s'],separators=(',',':')),
             'pre_gap_s':r['case'].get('pre_gap_s',1.),'post_gap_s':r['case'].get('post_gap_s',2.),
             'infrastructure_ok':r.get('infrastructure_ok'),'predicted_tilt_deg':pred,
             'predicted_tilt_upper_deg':p['empirical_tilt_range_deg'][1],'predicted_tilt_lower_deg':p['empirical_tilt_range_deg'][0],
             'predicted_altitude_loss_m':None,
             'observed_tilt_deg':peak,'observed_altitude_loss_m':m.get('max_altitude_loss_m'),
             'full_horizon_comparable':comparable,'censored':m.get('censored',True),
             'peak_error_pred_minus_observed_deg':pred-peak if comparable else None,
             'danger_underestimated':None if peak is None else peak>=45. and pred<45.,
             'exceeds_empirical_upper':None if peak is None else peak>p['empirical_tilt_range_deg'][1],
             'tilt_skip':p['tilt_only_screen_skip'],'overall_skip':p['overall_skip'],'overall_decision':p['overall_decision'],
             'primary_failure':None if m.get('frozen_primary_outcome') is None else m['frozen_primary_outcome']=='FAILURE','tilt_failure':m.get('tilt_ge_45_failure'),
             'altitude_failure':m.get('altitude_failure'),'task_outcome':m.get('task_outcome'),
             'max_lag_m':m.get('max_lag_m'),'integrated_abs_lag_m_s':m.get('integrated_abs_lag_m_s'),
             'planned_interruptions':len(r['case']['windows_s']),
             'closed_observed_interruptions':m.get('closed_observed_interruptions'),
             'final_resume_observed':bool(m.get('recoveries') and m['recoveries'][-1]['index']==len(r['case']['windows_s'])-1),
             'final_task_cost_outcome':m.get('final_task_cost_outcome'),
             'evidence_directory':str((formal/r['id']).relative_to(ROOT))}
        final=(m.get('recoveries') or [{}])[-1] if row['final_resume_observed'] else {}
        row.update(last_catch_up_s=final.get('vehicle_catch_up_10s_s'),
                   last_catch_up_censored=final.get('vehicle_catch_up_censored',True),
                   last_within_task_cost=None if m.get('final_task_cost_outcome') not in ['SUCCESS','FAILURE'] else m['final_task_cost_outcome']=='SUCCESS')
        rows.append(row)
    if rows:
        with (out/'prediction-measurement-ledger.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    groups=[]
    for stage in ['B','C-search','C-reference','D']:
        rr=[r for r in rows if r['stage']==stage];comp=[r for r in rr if r['full_horizon_comparable']]
        corr=None
        if len(comp)>2 and len({r['predicted_tilt_deg'] for r in comp})>1 and len({r['observed_tilt_deg'] for r in comp})>1:
            corr=float(spearmanr([r['predicted_tilt_deg'] for r in comp],[r['observed_tilt_deg'] for r in comp]).statistic)
        measured=[r for r in rr if r['primary_failure'] is not None]
        groups.append({'stage':stage,'n':len(rr),'measured_n':len(measured),'complete_horizon_n':len(comp),'censored_n':sum(bool(r['censored']) for r in rr),
                       'primary_failure_n':sum(bool(r['primary_failure']) for r in rr),
                       'tilt_failure_n':sum(bool(r['tilt_failure']) for r in rr),'altitude_failure_n':sum(bool(r['altitude_failure']) for r in rr),
                       'tilt_known_denominator':sum(not r['censored'] or r['tilt_failure'] is True for r in rr),
                       'altitude_known_denominator':sum(not r['censored'] or r['altitude_failure'] is True for r in rr),
                       'task_failure_n':sum(r['task_outcome']=='FAILURE' for r in rr),
                       'task_censored_n':sum(r['task_outcome']=='CENSORED' for r in rr),
                       'task_known_denominator':sum(r['task_outcome'] in ['SUCCESS','FAILURE'] for r in rr),
                       'task_unmeasured_n':sum(r['task_outcome'] is None for r in rr),
                       'mae_complete_horizon_deg':statistics.mean(abs(r['peak_error_pred_minus_observed_deg']) for r in comp) if comp else None,
                       'spearman_complete_horizon':corr,'danger_underestimated_n':sum(bool(r['danger_underestimated']) for r in rr),
                       'empirical_band_coverage_n':sum(r['predicted_tilt_lower_deg']<=r['observed_tilt_deg']<=r['predicted_tilt_upper_deg'] for r in comp),
                       'empirical_band_coverage_denominator':len(comp),
                       'tilt_skip_n':sum(r['tilt_skip'] for r in rr),'overall_skip_n':sum(r['overall_skip'] for r in rr),
                       'skip_failure_rate':None,'skip_failure_rate_denominator':0,
                       'nominal_wilson_primary_95':wilson(sum(bool(r['primary_failure']) for r in measured),len(measured)),
                       'CI_limit':'descriptive only; heterogeneous conditions/adaptive queries/paired seeds are not IID'})
    searches=[]
    for s in doc.get('searches',[]):
        family=s['family'];ref=sorted([r for r in rows if r['stage']=='C-reference' and r['family']==family],key=lambda r:r['phase_s'])
        brackets=[]
        for a,b in zip(ref,ref[1:]):
            known_a=not a['censored'] or a['tilt_failure'] is True
            known_b=not b['censored'] or b['tilt_failure'] is True
            if known_a and known_b and a['tilt_failure']!=b['tilt_failure']:brackets.append([a['phase_s'],b['phase_s']])
        est=None
        if s['final'].get('bracket'):
            grid=[round(.1+.05*i,2) for i in range(12)];a,b=s['final']['bracket'];est=[grid[a],grid[b]]
        ref_unknown=sum(r['censored'] and not r['tilt_failure'] for r in ref)
        distance=abs(sum(est)/2-sum(brackets[0])/2) if est is not None and len(brackets)==1 and len(ref)==12 and not ref_unknown else None
        pool=[{'phase_s':round(.1+.05*i,2)} for i in range(12)]
        all_found=observed_brackets(pool,s['history'])
        missed=[b for b in brackets if not any(abs(sum(b)/2-sum(e)/2)<=.05+1e-9 for e in all_found)]
        searches.append({'family':family,'method':s['method'],'queries':s['final'].get('counted_queries',len(s['history'])),'status':s['final']['status'],
                         'confirmed_local_bracket':est,'reference_grid_n':len(ref),'reference_transition_intervals':brackets,
                         'reference_unresolved_n':ref_unknown,'local_target_precision_met':est is not None,
                         'all_observed_transition_intervals':all_found,'unmatched_reference_intervals':missed,
                         'error_vs_unique_empirical_reference_s':distance,
                         'reference_limit':'one new seed per grid point; a noisy empirical grid, not a probability boundary'})
    pairs=[];binary_pairs=[];bootstrap=[]
    for cluster in sorted({r['cluster'] for r in rows if r['stage']=='D'}):
        rr={r['treatment']:r for r in rows if r['stage']=='D' and r['cluster']==cluster}
        if len(rr)!=4 or any(x['observed_tilt_deg'] is None or x['observed_altitude_loss_m'] is None for x in rr.values()):continue
        for arm in ['P9-C','P9-R','P9-CR']:
            a,b=rr[arm],rr['P9-Z']
            for criterion in ['primary_failure','tilt_failure','altitude_failure','task_outcome']:
                def known(x):
                    if criterion=='primary_failure':return x[criterion] is not None
                    if criterion=='task_outcome':return x[criterion] in ['SUCCESS','FAILURE']
                    return not x['censored'] or x[criterion] is True
                if known(a) and known(b):
                    va=(a[criterion]=='FAILURE') if criterion=='task_outcome' else bool(a[criterion])
                    vb=(b[criterion]=='FAILURE') if criterion=='task_outcome' else bool(b[criterion])
                    binary_pairs.append({'cluster':cluster,'arm':arm,'criterion':criterion,'repair_failure':va,'original_failure':vb,'difference':int(va)-int(vb)})
            pairs.append({'cluster':cluster,'arm':arm,'tilt_difference_deg':a['observed_tilt_deg']-b['observed_tilt_deg'],
                          'altitude_loss_difference_m':a['observed_altitude_loss_m']-b['observed_altitude_loss_m'],
                          'max_lag_difference_m':a['max_lag_m']-b['max_lag_m'],
                          'both_complete_horizon':a['full_horizon_comparable'] and b['full_horizon_comparable'],
                          'both_task_cost_within':a['last_within_task_cost'] and b['last_within_task_cost']})
    rng=np.random.default_rng(202610249)
    for arm in ['P9-C','P9-R','P9-CR']:
        rr=[r for r in pairs if r['arm']==arm and r['both_complete_horizon']]
        for metric in ['tilt_difference_deg','altitude_loss_difference_m','max_lag_difference_m']:
            vals=np.array([r[metric] for r in rr]);n=len(vals)
            boots=np.mean(rng.choice(vals,size=(5000,n),replace=True),axis=1) if n else np.array([])
            bootstrap.append({'arm':arm,'metric':metric,'complete_pair_clusters':n,'mean':float(vals.mean()) if n else None,
                              'percentile_95':np.quantile(boots,[.025,.975]).tolist() if n else None,
                              'limit':'exploratory paired-sequence bootstrap; at most 9 clusters; censored peaks excluded, failures still in ledger'})
    summary={'execution_status':doc['status'],'attempts':budget_counts(items),'groups':groups,'searches':searches,
             'D_paired_results':pairs,'D_paired_binary_outcomes':binary_pairs,'D_bootstrap':bootstrap,'formal_runs_with_results':len(rows),
             'formal_unique_sim_seeds':len({r['sim_seed'] for r in rows}),
             'cost':{'formal_elapsed_s':sum(r.get('elapsed_s') or 0 for r in rows),
                     'per_query_prediction_compute_s':sum(r.get('prediction_compute_s') or 0 for r in doc['runs']),
                     'search_pool_compute_s':sum(s.get('shared_pool_compute_s',0.) for s in doc.get('searches',[]) if s['method']=='ledger'),
                     'development_starts':budget_counts(items)['development'],'identification_reused_runs':26,
                     'identification_new_flights':0,'model_adaptation':'source/event interpretation and surrogate fitting; separate from formal queries',
                     'deterministic_rebuild':json.loads((preparation/'determinism.json').read_text()) if (preparation/'determinism.json').exists() else None},
             'historical_validation_denominator':0,'height':'unmodelled: no overall-safety claim','raw_remote_complete':False}
    phase_groups=[];seed_pairs=[];interactions=[]
    b_rows=[r for r in rows if r['stage']=='B']
    for arm in ['P9-Z','P9-C']:
        for h in [15.,45.,75.]:
            rr=[r for r in b_rows if r['treatment']==arm and r['heading_deg']==h and '-single' not in r['id']]
            comp=[r for r in rr if r['full_horizon_comparable']]
            phase_groups.append({'treatment':arm,'heading_deg':h,'n':len(rr),'complete_n':len(comp),
                                 'primary_failure_n':sum(bool(r['primary_failure']) for r in rr),
                                 'danger_underestimate_n':sum(bool(r['danger_underestimated']) for r in rr),
                                 'max_peak_underestimate_deg':max((r['observed_tilt_deg']-r['predicted_tilt_deg'] for r in comp),default=None)})
            same=[r for r in rr if r['phase_s']==.4]
            if len(same)==2:
                seed_pairs.append({'treatment':arm,'heading_deg':h,'n':2,'tilt_values_deg':[r['observed_tilt_deg'] for r in same],
                                   'flip':same[0]['tilt_failure']!=same[1]['tilt_failure'],'inference':'two development-independent seeds only; no stochastic-boundary guarantee'})
            controls=[r for r in b_rows if r['treatment']==arm and r['heading_deg']==h and '-single' in r['id']]
            multi=next((r for r in same if '-repeat-' not in r['id']),None)
            if len(controls)==3 and multi and all(r['observed_tilt_deg'] is not None for r in controls):
                interactions.append({'treatment':arm,'heading_deg':h,'multi_id':multi['id'],'single_ids':[r['id'] for r in controls],
                                     'multi_peak_tilt_deg':multi['observed_tilt_deg'],'single_peak_tilts_deg':[r['observed_tilt_deg'] for r in controls],
                                     'multi_altitude_loss_m':multi['observed_altitude_loss_m'],'single_altitude_losses_m':[r['observed_altitude_loss_m'] for r in controls],
                                     'all_complete_horizons':all(r['full_horizon_comparable'] for r in controls+[multi]),
                                     'interpretation':'same target trajectory; different seeds; descriptive interaction check, not a guaranteed additive law'})
    summary.update(B_phase_groups=phase_groups,B_seed_pairs=seed_pairs,B_single_multi_controls=interactions)
    summary['cost']['adaptation_and_identification_baseline']=json.loads((preparation/'cost-baseline.json').read_text())
    summary['detailed_search_files']=[str(p.relative_to(ROOT)) for p in sorted(formal.glob('search-*.json'))]
    write(out/'results.json',summary)
    inputs=[formal/'results.json',preparation/'attempts.jsonl',preparation/'model.json',preparation/'input-manifest.json',
            preparation/'cost-baseline.json',ROOT/'config/p9.json']
    if (ROOT/'config/p9.json').exists():
        frozen=ROOT/json.loads((ROOT/'config/p9.json').read_text())['p9']['formal_freeze']
        inputs.extend([frozen/'manifest.json',frozen/'receipt.json'])
    write(out/'input-manifest.json',{str(p.relative_to(ROOT)):sha(p) for p in inputs if p.exists()})
    text=['# Thor P9：执行与结果报告','',f"状态：{doc['status']}；开发启动 {summary['attempts']['development']}/12，正式启动 {summary['attempts']['formal']}/180。",'',
          'P8 原模型缺失记录保持；P9 使用新模型。旧900次和24次探索均不进入本报告的新验证分母。',
          '高度未建模，所有整体安全/跳过判断拒判。失配账本不是带延迟系统的 Lyapunov 证书；未证明安全集外必败。','',
          '| 阶段 | 实测n | 完整窗n | 主失败 | 倾角失败 | 掉高失败 | 任务失败 | 任务删失 |',
          '|---|---:|---:|---:|---:|---:|---:|---:|']
    for g in groups:text.append(f"|{g['stage']}|{g['n']}|{g['complete_horizon_n']}|{g['primary_failure_n']}|{g['tilt_failure_n']}|{g['altitude_failure_n']}|{g['task_failure_n']}|{g['task_censored_n']}|")
    text+=['','逐条预测—实测、搜索状态/参考区间、修复配对差、成本和分母见本目录 CSV/JSON。',
           '所有失败和删失保留。完整时域误差/排序只用完整窗口，删失中的已观测越阈另报危险低估。',
           '参考仅每格一个独立种子，D仅9个序列簇；Wilson和bootstrap为描述性，不能给严格总体保证。',
           '原始ULog、逐物理步电机轨迹、完整遥测仅存Thor本地；远端并非全原始数据。']
    (out/'report.md').write_text('\n'.join(text)+'\n')
    write(out/'output-manifest.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='output-manifest.json'})
    print(json.dumps({'status':doc['status'],'counts':summary['attempts'],'results':len(rows)},ensure_ascii=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('preparation',type=Path);p.add_argument('--formal',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();report(a.preparation,a.formal,a.output)


if __name__=='__main__':main()
