#!/usr/bin/env python3
"""New read-only report of completed P9 evidence after external interruption.

Preserves the frozen generator's outputs in a separate subdirectory, then adds
explicit interruption/denominator/search annotations. No experiment or fitting.
"""
from pathlib import Path
from datetime import datetime
import argparse,csv,json,sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
from p9_report import report as frozen_report
from p9_search import observed_brackets


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'data/p9-20261024-report-interrupted-v1')
    args=parser.parse_args()
    prep=ROOT/'data/p9-20261024-preparation';formal=ROOT/'data/p9-20261024-formal'
    diagnostic=ROOT/'data/p9-20261024-interruption-v1';auditdir=ROOT/'data/p9-20261024-audit-interrupted-v1'
    out=args.output.resolve()
    audit=json.loads((auditdir/'audit.json').read_text())
    assessment=json.loads((diagnostic/'interruption-assessment.json').read_text())
    seal=json.loads((formal/'searches-sealed-before-reference.json').read_text())
    out.mkdir(exist_ok=False)
    baseline=out/'frozen-generator-output'
    # Absolute paths are required by this frozen CLI implementation's relative_to(ROOT).
    # Do not alter the frozen source to work around its relative-path CLI limitation.
    frozen_report(prep,formal,baseline)
    s=json.loads((baseline/'results.json').read_text())
    per_run_pass=all(r['passed'] for r in audit['runs'])
    expected_global=['started attempts missing from aggregate; inspect unfinished/failed attempt']
    subset_ok=per_run_pass and audit['runs_checked']==101 and audit['errors']==expected_global
    write(out/'completed-audit-assessment.json',{'completed_subset_status':'PASS' if subset_ok else 'REQUIRES_REVIEW',
        'completed_runs_checked':audit['runs_checked'],'all_completed_rows_pass':per_run_pass,
        'whole_campaign_audit_status':audit['status'],'whole_campaign_errors':audit['errors'],
        'formal_started':s['attempts']['formal'],'formal_with_results':s['formal_runs_with_results'],
        'no_campaign_pass_claim':True,'source_audit_sha256':sha(auditdir/'audit.json')})
    searches=[]
    for x in seal['searches']:
        b=x['final'].get('bracket')
        searches.append({'family':x['family'],'method':x['method'],
          'queries':x['final'].get('counted_queries',len(x['history'])),'status':x['final']['status'],
          'confirmed_local_bracket':None if b is None else [round(.1+.05*i,2) for i in b],
          'reference_grid_n':0,'reference_transition_intervals':None,'reference_unresolved_n':12,
          'local_target_precision_met':b is not None,
          'all_observed_transition_intervals':observed_brackets([{'phase_s':round(.1+.05*i,2)} for i in range(12)],x['history']),
          'unmatched_reference_intervals':None,'error_vs_unique_empirical_reference_s':None,
          'noisy_indices':x['final'].get('noisy_indices',[]),
          'reference_limit':'reference first attempt interrupted; no valid reference measurements; accuracy cannot be evaluated'})
    s.update(execution_status='INTERRUPTED_INCOMPLETE',source_aggregate_last_written_status=s['execution_status'],
             searches=searches,completed_subset_audit_pass=subset_ok,whole_campaign_audit_status=audit['status'],
             detected_infrastructure_interruptions=1,unmeasured_started_attempt='C-CZ15-g0.1-reference-P9-Z',
             remaining_required_static_not_run=71,unused_frozen_search_slots=7,
             D_validation_status='NOT_RUN_NO_HELDOUT_REPAIR_EVIDENCE',reference_accuracy_status='NOT_ESTIMABLE',
             postprocessor='interruption-v1: frozen generator preserved, explicit new annotations only')
    s['cost']['search_pool_compute_s']=sum(x['shared_pool_compute_s'] for x in seal['searches'] if x['method']=='ledger')
    cleanup=json.loads((diagnostic/'cleanup-result.json').read_text())
    interrupted=assessment['latest_started']
    s['cost']['interrupted_start_to_cleanup_wall_s']=(datetime.fromisoformat(cleanup['checked_at'])-datetime.fromisoformat(interrupted['time'])).total_seconds()
    s['cost']['interrupted_cost_note']='includes uncontrolled orphan tail; no FINISH or valid planned flight result. Never count missing elapsed as zero cost.'
    s['cost']['completed_attempt_elapsed_note']='formal_elapsed_s sums only the 101 completed attempts including run/measure/export, not the interrupted attempt'
    s['cost']['development_elapsed_s']=sum(x.get('elapsed_s',0.) for x in map(json.loads,(prep/'attempts.jsonl').read_text().splitlines()) if x['event']=='FINISH' and x.get('stage') is None)
    write(out/'results.json',s)
    planned=json.loads((ROOT/'data/p9-20261024-freeze/plan.json').read_text())
    events=[json.loads(x) for x in (prep/'attempts.jsonl').read_text().splitlines()]
    starts={x['id']:x for x in events if x['event']=='START_INTENT' and x['budget_class']=='formal'}
    ends={x['id']:x for x in events if x['event']=='FINISH'}
    account=[]
    for r in planned['runs']+planned['search_slots']:
        state='FINISHED' if r['id'] in ends else ('INFRA_INTERRUPTED_UNMEASURED' if r['id'] in starts else ('UNUSED_SEARCH_STOP' if r['stage']=='C-search' else 'NOT_RUN_AFTER_INFRA_STOP'))
        account.append({'id':r['id'],'stage':r['stage'],'state':state})
    write(out/'budget-accounting.json',{'rows':account,'formal_started':102,'formal_finished':101,'formal_cap':180,
         'development_started':10,'development_cap':12,'unused_search_slots':7,'not_run_required_static':71,
         'retry_count':0,'all_started_attempts_remain_counted':True})
    rows=list(csv.DictReader((baseline/'prediction-measurement-ledger.csv').open()))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    figdir=out/'figures';figdir.mkdir()
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
    def save(fig,name):
        fig.tight_layout();fig.savefig(figdir/(name+'.png'));fig.savefig(figdir/(name+'.pdf'));plt.close(fig)
    fig,ax=plt.subplots(1,2,figsize=(11,4.5))
    for arm,c in [('P9-Z','#0072B2'),('P9-C','#D55E00')]:
        rr=[r for r in rows if r['stage']=='B' and r['treatment']==arm]
        for complete,marker in [(True,'o'),(False,'^')]:
            z=[r for r in rr if (r['full_horizon_comparable']=='True')==complete]
            ax[0].scatter([float(r['predicted_tilt_deg']) for r in z],[float(r['observed_tilt_deg']) for r in z],c=c,marker=marker,label=arm+(' complete' if complete else ' censored lower bound'))
            ax[1].scatter([float(r['observed_tilt_deg']) for r in z],[float(r['observed_altitude_loss_m']) for r in z],c=c,marker=marker)
    xx=np.array([15.,65.]);band=json.loads((prep/'model.json').read_text())['error_rule']['empirical_peak_abs_band_deg']
    ax[0].plot(xx,xx,color='black',lw=.8);ax[0].fill_between(xx,xx-band,xx+band,color='gray',alpha=.08)
    ax[0].set(xlabel='Predicted peak tilt (deg)',ylabel='Observed peak tilt (deg)',title='B: empirical development band, not a guarantee')
    ax[0].legend(fontsize=7);ax[1].set(xlabel='Observed peak tilt (deg)',ylabel='Observed altitude loss (m)',title='B: tilt and task criteria remain distinct')
    ax[0].axvline(45,color='gray',lw=.7);ax[0].axhline(45,color='gray',lw=.7);ax[1].axvline(45,color='gray',lw=.7);ax[1].axhline(1,color='gray',lw=.7)
    save(fig,'B-prediction-and-task')
    families=sorted({x['family'] for x in seal['searches']});fig,axs=plt.subplots(2,3,figsize=(12,7))
    for col,family in enumerate(families):
        for ri,method in enumerate(['ledger','replay']):
            x=next(x for x in seal['searches'] if x['family']==family and x['method']==method);a=axs[ri,col]
            h=x['history'];a.plot([z['phase_s'] for z in h],range(1,len(h)+1),color='lightgray')
            for i,z in enumerate(h,1):a.scatter(z['phase_s'],i,c='#D55E00' if z['failure'] else '#0072B2',marker='x' if z['failure'] else 'o')
            if x['final'].get('bracket'):
                lo,hi=x['final']['bracket'];a.axvspan(.1+.05*lo,.1+.05*hi,color='green',alpha=.1)
            a.set(xlabel='Restoration gap g (s)',ylabel='Own query number',title=f"{family}/{method}\n{x['final']['status']}",ylim=(.5,10.5),xlim=(.075,.675))
            a.title.set_fontsize(8)
    fig.suptitle('C: sealed histories; no valid independent reference available after interruption',fontsize=10);fig.subplots_adjust(top=.88,hspace=.5)
    save(fig,'C-sealed-search-histories')
    notes=['# P9：中断后的可复核阶段结果','',
        '**执行未完成，不能作为全批PASS或修复验证成功。** 原始aggregate最后写入RUNNING，进程现已失联；该原文件未改写。',
        '正式102次启动，101次完成，1次基础设施中断未测；开发10次。B48与C搜索53完成，参考有效0/36，D0/36。',
        '第102次不能重跑冒充同一尝试；未开始71次留NOT_RUN，7个搜索余额不挪用。',
        f"已完成101条的原始重测逐条通过={subset_ok}；全批审计仍为{audit['status']}，错误为{audit['errors']}。",'',
        '## 已完成数据','',
        '|阶段|n|完整窗n|主失败|倾角失败/已知n|高度失败/已知n|任务失败/已知n|完整窗MAE|完整窗Spearman|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for g in s['groups']:
        if not g['n']:continue
        notes.append(f"|{g['stage']}|{g['n']}|{g['complete_horizon_n']}|{g['primary_failure_n']}|{g['tilt_failure_n']}/{g['tilt_known_denominator']}|{g['altitude_failure_n']}/{g['altitude_known_denominator']}|{g['task_failure_n']}/{g['task_known_denominator']}|{g['mae_complete_horizon_deg']:.4f}|{g['spearman_complete_horizon']:.4f}|")
    notes+=['','误差、排序、经验带覆盖只用完整窗口，有删失选择；不能外推为全体峰值保证。',
        '跳过集合为空，集合失败率不可估；不能声称零漏判或证明跳过有效。高度未建模，整体安全拒判。',
        'C局部复核与参考准确性严格区分：参考有效分母0，因此边界误差、漏掉的参考转变均NA。',
        'D未执行，模型上选择RREC1及开发试验不能代替独立留出修复证据。',
        '失配账本不构成延迟实际系统Lyapunov证书；集合外不判必败；3族且种子不同，不作总体效率保证。',
        '完整原始ULog及电机/遥测只在Thor，远端不是完整原始数据。',
        'frozen-generator-output/保留未改写的冻结生成器输出；根目录results.json为本中断版本的明确注释，二者均可追溯。']
    (out/'report.md').write_text('\n'.join(notes)+'\n')
    inputs=[formal/'results.json',formal/'searches-sealed-before-reference.json',prep/'attempts.jsonl',
        diagnostic/'interruption-assessment.json',diagnostic/'cleanup-result.json',diagnostic/'raw-manifest.json',auditdir/'audit.json',Path(__file__).resolve(),ROOT/'tools/p9_report.py']
    write(out/'input-manifest.json',{str(x.relative_to(ROOT)):sha(x) for x in inputs})
    write(out/'output-manifest.json',{str(x.relative_to(out)):sha(x) for x in sorted(out.rglob('*')) if x.is_file() and x!=out/'output-manifest.json'})
    print('PARTIAL REPORT COMPLETE; completed subset pass',subset_ok,'whole campaign incomplete')


if __name__=='__main__':main()
