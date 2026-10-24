#!/usr/bin/env python3
"""Post-frozen read-only figures/diagnostics; never an input to a search or fit. Explicitly allows only the known original missing102.

Kept outside tools/ while the candidate is running to preserve its identity.
Run only after COMPLETE and the independent audit/report exist. New output only.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--formal',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    formal=json.loads((a.formal/'results.json').read_text())
    report=json.loads((a.report/'results.json').read_text())
    audit=json.loads((a.audit/'audit.json').read_text())
    if formal['status']!='COMPLETE_WITH_ORIGINAL_INFRA_MISSING' or report['execution_status']!='COMPLETE_WITH_ORIGINAL_INFRA_MISSING':
        raise SystemExit('Continuation complete with original missing102 required')
    manifest=json.loads((ROOT/'data/p9-20261024-freeze/manifest.json').read_text())
    if any(sha(ROOT/k)!=h for k,h in manifest['files'].items()):
        raise SystemExit('Frozen input drift; preserve all evidence and inspect')
    if formal.get('original_missing_id')!='C-CZ15-g0.1-reference-P9-Z' or report['attempts']!={'development':10,'formal':173}:raise SystemExit('unexpected missing/count contract')
    a.output.mkdir(parents=True,exist_ok=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,
                         'savefig.dpi':180,'figure.constrained_layout.use':True})
    rows=list(csv.DictReader((a.report/'prediction-measurement-ledger.csv').open()))
    def val(r,k):return None if r[k] in ['', 'None'] else float(r[k])
    def full(r):return r['full_horizon_comparable']=='True'
    def save(fig,name):
        fig.savefig(a.output/(name+'.png'));fig.savefig(a.output/(name+'.pdf'));plt.close(fig)
    colors={15.:'#0072B2',45.:'#D55E00',75.:'#009E73'}
    fig,axes=plt.subplots(2,2,figsize=(11,7),sharex='col')
    for j,arm in enumerate(['P9-Z','P9-C']):
        rr=[r for r in rows if r['stage']=='B' and r['treatment']==arm and '-single' not in r['id']]
        for h,c in colors.items():
            ss=sorted([r for r in rr if val(r,'heading_deg')==h and '-repeat-' not in r['id']],key=lambda r:val(r,'phase_s'))
            x=[val(r,'phase_s') for r in ss];pred=[val(r,'predicted_tilt_deg') for r in ss]
            axes[0,j].plot(x,pred,'--',color=c,label=f'{h:g} deg prediction')
            axes[0,j].fill_between(x,[val(r,'predicted_tilt_lower_deg') for r in ss],
                                  [val(r,'predicted_tilt_upper_deg') for r in ss],color=c,alpha=.07)
            for r in [r for r in rr if val(r,'heading_deg')==h]:
                marker='o' if full(r) else '^'
                axes[0,j].scatter(val(r,'phase_s'),val(r,'observed_tilt_deg'),marker=marker,color=c,s=30)
                axes[1,j].scatter(val(r,'phase_s'),val(r,'observed_altitude_loss_m'),marker=marker,color=c,s=30)
        axes[0,j].axhline(45,color='black',lw=.8);axes[1,j].axhline(1,color='black',lw=.8)
        axes[0,j].set_title(arm+(' (D=0.36 s)' if arm=='P9-Z' else ' (D=0.58 s)'))
        axes[0,j].set_ylabel('Peak tilt (deg)');axes[1,j].set_ylabel('Altitude loss (m)')
        axes[1,j].set_xlabel('First restoration gap g (s); complementary second gap')
        axes[0,j].legend(fontsize=7)
    fig.suptitle('B: fixed trajectory/window; triangles are observed lower bounds after censoring\nShading: development empirical band, not guaranteed coverage')
    save(fig,'B-phase-predictions')

    controls=report['B_single_multi_controls']
    fig,axes=plt.subplots(2,len(controls),figsize=(12,6),squeeze=False)
    for j,c in enumerate(controls):
        axes[0,j].bar(range(4),c['single_peak_tilts_deg']+[c['multi_peak_tilt_deg']],color=['#999999']*3+['#0072B2'])
        axes[1,j].bar(range(4),c['single_altitude_losses_m']+[c['multi_altitude_loss_m']],color=['#999999']*3+['#0072B2'])
        axes[0,j].set_title(f"{c['treatment']}, {c['heading_deg']:g} deg")
        for ax in axes[:,j]:ax.set_xticks(range(4),['Single1','Single2','Single3','Multi'],rotation=30)
        axes[0,j].axhline(45,color='black',lw=.8);axes[1,j].axhline(1,color='black',lw=.8)
    axes[0,0].set_ylabel('Peak tilt (deg)');axes[1,0].set_ylabel('Altitude loss (m)')
    fig.suptitle('B: exact phase controls at g=0.4; different fresh seeds, descriptive comparison\nThese controlled multi cases did not fail tilt; failures at other phases lack exact single controls')
    save(fig,'B-single-multi-controls')

    families=sorted({s['family'] for s in formal['searches']})
    fig,axes=plt.subplots(2,len(families),figsize=(13,7),squeeze=False)
    for col,family in enumerate(families):
        ref=sorted([r for r in rows if r['stage']=='C-reference' and r['family']==family],key=lambda r:val(r,'phase_s'))
        for ri,method in enumerate(['ledger','replay']):
            s=next(s for s in formal['searches'] if s['family']==family and s['method']==method)
            ax=axes[ri,col]
            for r in ref:
                fail=r['tilt_failure']=='True';known=full(r) or fail
                ax.scatter(val(r,'phase_s'),0,c='#D55E00' if fail else ('#0072B2' if known else '#999999'),
                           marker='x' if fail else ('o' if known else '$?$'),s=30)
            if s['history']:
                ax.plot([h['phase_s'] for h in s['history']],range(1,len(s['history'])+1),color='#bbbbbb',lw=.8)
            for i,h in enumerate(s['history'],1):
                ax.scatter(h['phase_s'],i,c='#D55E00' if h['failure'] else '#0072B2',marker='x' if h['failure'] else 'o',s=35)
            if s['final'].get('censored_query_id'):
                q=next(r for r in rows if r['id']==s['final']['censored_query_id'])
                ax.scatter(val(q,'phase_s'),s['final']['counted_queries'],color='gray',marker='s')
            if s['final'].get('bracket'):
                lo,hi=s['final']['bracket'];ax.axvspan(.1+.05*lo,.1+.05*hi,color='#009E73',alpha=.1)

            measured_phases={val(r,'phase_s') for r in ref}
            for phase in [round(.1+.05*k,2) for k in range(12)]:
                if phase not in measured_phases:ax.scatter(phase,0,c='gray',marker='$?$',s=40)
            ax.set_ylim(-.5,10.7);ax.set_xlim(.075,.675);ax.set_yticks(range(0,11))
            ax.set_ylabel('Own query number; row 0 = post-hoc reference')
            ax.set_xlabel('g (s)');ax.set_title(f"{family} / {method}\n{s['final']['status']}",fontsize=8)
    fig.suptitle('C: independent noisy reference observed only after all searches were sealed\nRed x = observed tilt failure; blue circle = full-window below threshold; gray = unresolved')
    save(fig,'C-search-histories')

    arms=['P9-Z','P9-C','P9-R','P9-CR'];dr=[r for r in rows if r['stage']=='D']
    fig,axes=plt.subplots(2,2,figsize=(11,7))
    for ax,key,label,threshold in [(axes[0,0],'observed_tilt_deg','Peak tilt (deg)',45),
                                  (axes[0,1],'observed_altitude_loss_m','Altitude loss (m)',1),
                                  (axes[1,0],'max_lag_m','Whole-window maximum lag (m)',4.5)]:
        for k,cluster in enumerate(sorted({r['cluster'] for r in dr})):
            rr=[next(r for r in dr if r['cluster']==cluster and r['treatment']==arm) for arm in arms]
            xx=np.arange(4)+(k-4)*.015;yy=[val(r,key) for r in rr]
            ax.plot(xx,yy,color='#bbbbbb',lw=.8)
            for x,y,r in zip(xx,yy,rr):ax.scatter(x,y,marker='o' if full(r) else '^',s=24,color=f'C{k%10}')
        ax.set_xticks(range(4),arms);ax.set_ylabel(label);ax.axhline(threshold,color='black',lw=.8)
    ax=axes[1,1];bottom=np.zeros(4)
    for outcome,color in [('SUCCESS','#009E73'),('FAILURE','#D55E00'),('CENSORED','#E69F00'),('UNOBSERVED_FINAL_RESUME','#999999')]:
        counts=np.array([sum(r['treatment']==arm and r['final_task_cost_outcome']==outcome for r in dr) for arm in arms])
        ax.bar(range(4),counts,bottom=bottom,label=outcome,color=color);bottom+=counts
    ax.set_xticks(range(4),arms);ax.set_ylabel('Final task-cost outcome (nine paired sequence clusters)');ax.legend(fontsize=7)
    fig.suptitle('D: fixed held-out sequences and shared seed within each four-arm cluster\nTriangles: censored peak/loss/lag lower bounds; no recovery time imputed for missing catch-up')
    save(fig,'D-repair-and-task-cost')

    diagnostics=[];inputs={}
    for r in formal['runs']:
        if r['stage'] not in ['B','D']:continue
        path=ROOT/r['directory']/'p7-metrics.json';m=json.loads(path.read_text());inputs[str(path.relative_to(ROOT))]=sha(path)
        for g in m.get('gaps') or []:
            capture=g.get('capture') or {};resume=g.get('resume') or {};window=g.get('window') or {}
            diagnostics.append({'id':r['id'],'stage':r['stage'],'arm':r['treatment'],'event_index':g['index'],
                'capture_delay_after_last_read_s':capture.get('after_last_reception_s'),
                'capture_mode':capture.get('mode'),'capture_vehicle_velocity_ned_m_s':json.dumps(capture.get('vehicle_velocity_ned_m_s')),
                'capture_target_velocity_ned_m_s':json.dumps(capture.get('target_velocity_ned_m_s')),
                'resume_jump_along_m':resume.get('jump_along_axis_m'),'resume_velocity_jump_along_m_s':resume.get('velocity_jump_along_axis_m_s'),
                'capture_offset_along_m':resume.get('offset_at_capture_along_axis_m'),
                'local_segment_peak_tilt_deg':window.get('max_tilt_deg'),'local_segment_altitude_loss_m':window.get('max_altitude_loss_m'),
                'scope_note':'existing P7 per-event segment window; altitude baseline is local, not P9 whole-window task loss'})
    with (a.output/'event-diagnostics.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(diagnostics[0]));w.writeheader();w.writerows(diagnostics)
    write(a.output/'recovery-records.json',{'rows':[{'id':r['id'],'stage':r['stage'],'arm':r['treatment'],
        'recoveries':r['p9']['recoveries'],'final_task_cost_outcome':r['p9']['final_task_cost_outcome']} for r in formal['runs'] if r['stage']=='D'],
        'limits':'vehicle catch-up differs from virtual-target convergence; null remains censored or missing, never an achieved time'})
    write(a.output/'event-observation-status.json',{'rows':[{'id':r['id'],'stage':r['stage'],
        'planned_interruptions':r['p9']['planned_interruptions'],'closed_observed_interruptions':r['p9']['closed_observed_interruptions'],
        'open_gap':r['p9']['open_gap'],'complete_window':r['p9']['complete_window']} for r in formal['runs'] if r['stage'] in ['B','D']],
        'event_csv_scope':'closed-observed events only; unclosed/missing events are not counted as observed in the diagnostic CSV'})
    repeated=[]
    for family in families:
        phases=sorted({val(r,'phase_s') for r in rows if r['stage'] in ['C-search','C-reference'] and r['family']==family})
        for phase in phases:
            rr=[r for r in rows if r['stage'] in ['C-search','C-reference'] and r['family']==family and val(r,'phase_s')==phase]
            if len(rr)<2:continue
            known=[r for r in rr if full(r) or r['tilt_failure']=='True']
            repeated.append({'family':family,'phase_s':phase,'n':len(rr),
                'observed_tilt_deg':[val(r,'observed_tilt_deg') for r in rr],
                'complete_window':[full(r) for r in rr],'observed_tilt_failure':[r['tilt_failure']=='True' for r in rr],
                'seeds':[int(r['sim_seed']) for r in rr],'ids':[r['id'] for r in rr],
                'full_horizon_known_n':len(known),'full_horizon_unknown_n':len(rr)-len(known),
                'mixed_known_binary_outcomes':len({r['tilt_failure'] for r in known})>1})
    write(a.output/'C-condition-seed-variation.json',{'rows':repeated,
        'scope':'post-hoc same-condition seed diagnostic across sealed searches and later independent reference; never supplied to searches',
        'limit':'adaptive condition selection and few seeds; descriptive ranges/flips, no failure-probability estimate or CI; censored peaks are lower bounds'})
    for path in [a.formal/'results.json',a.report/'results.json',a.report/'prediction-measurement-ledger.csv',a.audit/'audit.json',Path(__file__)]:
        inputs[str(path.resolve().relative_to(ROOT))]=sha(path)
    ledger_path=ROOT/'data/p9-20261024-preparation/attempts.jsonl'
    ledger=[json.loads(s) for s in ledger_path.read_text().splitlines()]
    starts=[s for s in ledger if s['event']=='START_INTENT'];ends={s['id']:s for s in ledger if s['event']=='FINISH'}
    plan=json.loads((ROOT/'data/p9-20261024-freeze/plan.json').read_text())
    formal_start_map={s['id']:s for s in starts if s['budget_class']=='formal'}
    formal_attempt_count=sum(s['budget_class']=='formal' for s in starts)
    planned=plan['runs']+plan['search_slots'];planned_ids={r['id'] for r in planned}
    accounting=[];budget_errors=[]
    for r in planned:
        started=r['id'] in formal_start_map;ended=r['id'] in ends
        state='FINISHED' if started and ended else ('ORIGINAL_INFRA_MISSING' if r['id']=='C-CZ15-g0.1-reference-P9-Z' and started else ('STARTED_UNRESOLVED' if started else 'NOT_STARTED_FROZEN_SEARCH_STOP'))
        stop=None
        if not started:
            if r['stage']!='C-search':budget_errors.append('required static run missing: '+r['id']);state='MISSING_REQUIRED_START'
            else:stop=next(s['final']['status'] for s in formal['searches'] if s['family']==r['family'] and s['method']==r['method'])
        if started and not ended and r['id']!='C-CZ15-g0.1-reference-P9-Z':budget_errors.append('unexpected started without finish: '+r['id'])
        accounting.append({'id':r['id'],'stage':r['stage'],'state':state,'search_stop_reason':stop})
    if set(formal_start_map)-planned_ids:budget_errors.append('unplanned starts')
    if len(formal_start_map)!=formal_attempt_count:budget_errors.append('duplicate formal attempt id')
    if formal_attempt_count>180 or sum(s['budget_class']=='development' for s in starts)>12:budget_errors.append('hard cap exceeded')
    ref_start=[i for i,s in enumerate(ledger) if s['event']=='START_INTENT' and s.get('stage')=='C-reference']
    search_end=[i for i,s in enumerate(ledger) if s['event']=='FINISH' and s.get('stage')=='C-search']
    d_start=[i for i,s in enumerate(ledger) if s['event']=='START_INTENT' and s.get('stage')=='D']
    ref_end=[i for i,s in enumerate(ledger) if s['event']=='FINISH' and s.get('stage')=='C-reference']
    if ref_start and search_end and min(ref_start)<=max(search_end):budget_errors.append('reference preceded end of searches')
    if d_start and ref_end and min(d_start)<=max(ref_end):budget_errors.append('D preceded end of reference')
    write(a.output/'budget-accounting.json',{'status':'FAIL' if budget_errors else 'ACCOUNTING_CLOSED_WITH_KNOWN_INFRA_MISSING','original_missing_id':'C-CZ15-g0.1-reference-P9-Z','overall_acceptance_pass':False,'errors':budget_errors,
          'rows':accounting,'formal_started':formal_attempt_count,'formal_cap':180,
          'development_started':sum(s['budget_class']=='development' for s in starts),'development_cap':12,
          'scope':'every static run and search slot, including unspent slots; unused search budget never transferred'})
    cost_rows=[]
    for s in starts:
        end=ends.get(s['id']);files=[x for x in (ROOT/s['output']).rglob('*') if stat.S_ISREG(os.lstat(x).st_mode)]
        cost_rows.append({'id':s['id'],'budget_class':s['budget_class'],'stage':s.get('stage','development'),
             'start_time':s['time'],'finish_time':end.get('time') if end else None,
             'elapsed_s':end.get('elapsed_s') if end else None,'infrastructure_ok':end.get('infrastructure_ok') if end else None,
             'flight_failure':end.get('flight_failure') if end else None,
             'regular_file_logical_bytes':sum(x.stat().st_size for x in files),
             'regular_file_allocated_bytes':sum(x.stat().st_blocks*512 for x in files)})
    fs=[s for s in starts if s['budget_class']=='formal'];formal_span=None
    if fs and all(s['id'] in ends for s in fs):
        formal_span=(max(datetime.fromisoformat(ends[s['id']]['time']) for s in fs)-min(datetime.fromisoformat(s['time']) for s in fs)).total_seconds()
    cost={'rows':cost_rows,'development_elapsed_s':sum(r['elapsed_s'] or 0 for r in cost_rows if r['budget_class']=='development'),
          'formal_campaign_recorded_span_s':formal_span,'formal_attempt_elapsed_s':report['cost']['formal_elapsed_s'],
          'new_identification_flights':0,'historical_identification_runs':26,
          'human_adaptation_labor_hours':None,'initial_fit_elapsed_s':None,'prefreeze_prediction_total_elapsed_s':None,
          'separately_timed_deterministic_rebuild':report['cost']['deterministic_rebuild'],
          'per_query_prediction_compute_s':report['cost']['per_query_prediction_compute_s'],
          'search_pool_compute_s':report['cost']['search_pool_compute_s'],
          'limits':'wall times include harness/measurement/export, not pure physics or CPU/GPU time; regular file bytes exclude directories/symlinks; unrecorded cost components stay NA'}
    write(a.output/'cost-audit.json',cost);inputs[str(ledger_path.relative_to(ROOT))]=sha(ledger_path)
    write(a.output/'input-manifest.json',inputs)
    write(a.output/'analysis.json',{'execution_status':formal['status'],'audit_status':audit['status'],
          'purpose':'read-only post-frozen display and existing event/recovery extraction; no fitting, selection, or query feedback',
          'overall_acceptance':'NO_PASS_ORIGINAL_INFRA_MISSING','reference_missing_n':1,'execution_epochs_separate':True,'unknown_height_predictions':True,'empty_skip_set_failure_rate':'not estimable; no zero-miss-rate or effective-skipping claim',
          'scientific_limits':['conditional complete-window errors exclude censored peaks','reference is single-seed noisy grid, not a true probability boundary',
          'D has nine related sequence clusters, not 36 independent samples','controlled g=.4 B multi cases did not fail tilt; other-phase failure mechanism lacks exact controls']})
    notes=['# P9 正式结果审阅材料（须人工审阅后发布）','',
           f"执行 {formal['status']}；续接71条原始数据审计 {audit['status']}（原批完整性FAIL仍保留）；正式启动 {report['attempts']['formal']}/180，开发 {report['attempts']['development']}/12。",'',
           '跳过集合为空，集合失败率不可估；既不声称零漏判，也不证明跳过有效。高度未建模，不能声称整体安全。',
           '完整窗口误差有删失选择；已观察到的越阈单列，未越阈的删失不算安全。', '',
           '|阶段|已测n|完整窗n|主失败|倾角失败/已知n|掉高失败/已知n|任务失败/已知n|任务删失|完整窗MAE|完整窗Spearman|',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    def fmt(v):return 'NA' if v is None else (f'{v:.4f}' if isinstance(v,float) else str(v))
    for g in report['groups']:
        notes.append('|'+ '|'.join(map(str,[g['stage'],g['n'],g['complete_horizon_n'],g['primary_failure_n'],
           f"{g['tilt_failure_n']}/{g['tilt_known_denominator']}",f"{g['altitude_failure_n']}/{g['altitude_known_denominator']}",
           f"{g['task_failure_n']}/{g['task_known_denominator']}",g['task_censored_n'],fmt(g['mae_complete_horizon_deg']),fmt(g['spearman_complete_horizon'])]))+'|')
    notes+=['','## C：逐族搜索结果','',
            '|族|方法|实际查询/10|停止状态|局部夹逼|参考转变区间|参考未知n|与唯一参考中点误差s|',
            '|---|---|---:|---|---|---|---:|---:|']
    for s in report['searches']:
        notes.append('|'+ '|'.join(map(str,[s['family'],s['method'],s['queries'],s['status'],s['confirmed_local_bracket'],
              s['reference_transition_intervals'],s['reference_unresolved_n'],fmt(s['error_vs_unique_empirical_reference_s'])]))+'|')
    notes+=['','参考网格每格只有一个独立种子，局部稳定夹逼不排除其他转变；多转变/未知时不捏造唯一边界误差。',
            '理论结构未构成 Lyapunov 证书，两法比较只涉及三个冻结族与同样的上限，不作总体效率保证。','',
            '## D：九个配对序列簇','',
            '|处理|n|完整窗n|主失败|倾角失败/已知n|掉高失败/已知n|任务失败/已知n|成本SUCCESS/FAILURE/CENSORED/末接回未观察|已观察到末次追回n|',
            '|---|---:|---:|---:|---:|---:|---:|---|---:|']
    for arm in arms:
        rr=[r for r in dr if r['treatment']==arm]
        tk=sum(full(r) or r['tilt_failure']=='True' for r in rr);ak=sum(full(r) or r['altitude_failure']=='True' for r in rr)
        qk=sum(r['task_outcome'] in ['SUCCESS','FAILURE'] for r in rr)
        cs=[sum(r['final_task_cost_outcome']==s for r in rr) for s in ['SUCCESS','FAILURE','CENSORED','UNOBSERVED_FINAL_RESUME']]
        notes.append('|'+ '|'.join(map(str,[arm,len(rr),sum(full(r) for r in rr),sum(r['primary_failure']=='True' for r in rr),
            f"{sum(r['tilt_failure']=='True' for r in rr)}/{tk}",f"{sum(r['altitude_failure']=='True' for r in rr)}/{ak}",
            f"{sum(r['task_outcome']=='FAILURE' for r in rr)}/{qk}",'/'.join(map(str,cs)),sum(val(r,'last_catch_up_s') is not None for r in rr)]))+'|')
    notes+=['','|选定组合CR对原规则的配对判据|已知簇n|原失败→组合成功|原成功→组合失败|同成功|同失败|',
            '|---|---:|---:|---:|---:|---:|']
    for criterion in ['primary_failure','tilt_failure','altitude_failure','task_outcome']:
        bb=[b for b in report['D_paired_binary_outcomes'] if b['arm']=='P9-CR' and b['criterion']==criterion]
        notes.append('|'+ '|'.join(map(str,[criterion,len(bb),sum(b['original_failure'] and not b['repair_failure'] for b in bb),
             sum(not b['original_failure'] and b['repair_failure'] for b in bb),sum(not b['original_failure'] and not b['repair_failure'] for b in bb),
             sum(b['original_failure'] and b['repair_failure'] for b in bb)]))+'|')
    notes+=['','D主比较为冻结选定组合CR对Z；C/R单臂是因子诊断，不能根据本批挑选新获胜修复并称为已验证。',
            '连续值配对bootstrap只用双臂完整窗口，最多九簇，为条件性的探索描述；所有失败/删失仍在二元账本。',
            '追回null保持未追回或删失，未观察末次计划接回不冒充最后接回；虚拟目标收敛与机体追回不同。','',
            '## 成本','',f"正式各尝试elapsed合计 {report['cost']['formal_elapsed_s']:.3f}s（含每次运行/测量/导出，并非纯仿真物理时长）。",
            f"每查询预测计算合计 {report['cost']['per_query_prediction_compute_s']:.6f}s；搜索候选池离线计算合计 {report['cost']['search_pool_compute_s']:.6f}s（每族只计一次共享池）。",
            f"十次开发/等价性尝试elapsed合计 {cost['development_elapsed_s']:.3f}s；正式首启动至末完成墙钟跨度 {fmt(formal_span)}s。",
            '复用历史普通辨识26次，新辨识飞行0。模型适配/开发十次另列；人工工时、初次拟合单独耗时与冻结前全部预测耗时未完整计时，均NA，不能用重建耗时冒充初次工程总成本。',
            '原历史事件墙钟跨度不算新P9成本；逐尝试耗时及本地常规文件字节见cost-audit.json。',
            '完整原始ULog、遥测和物理步电机数据仅在Thor本地；远端并非全原始数据。']
    (a.output/'review-notes.md').write_text('\n'.join(notes)+'\n')
    write(a.output/'output-manifest.json',{str(x.relative_to(a.output)):sha(x) for x in sorted(a.output.rglob('*')) if x.is_file() and x.name!='output-manifest.json'})
    if budget_errors:raise SystemExit('Postanalysis accounting failure; inspect budget-accounting.json, do not rerun flights')
    print('POSTANALYSIS COMPLETE; independent audit status',audit['status'])


if __name__=='__main__':main()
