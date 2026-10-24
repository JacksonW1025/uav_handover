#!/usr/bin/env python3
"""Read-only two-epoch analysis; never an overall acceptance PASS.

Original attempts/results remain untouched. New analysis-view copies only the
pre-query JSONs for the frozen report generator; CSV links retain actual sources.
"""
import argparse,csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
from p9_report import report as frozen_report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--formal',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();new=a.formal.resolve();audit=a.audit.resolve();out=a.output.resolve()
    old=ROOT/'data/p9-20261024-formal';prep=ROOT/'data/p9-20261024-preparation'
    prior=json.loads((old/'results.json').read_text());current=json.loads((new/'results.json').read_text())
    seal=json.loads((old/'searches-sealed-before-reference.json').read_text())
    oa=json.loads((ROOT/'data/p9-20261024-audit-interrupted-v1/audit.json').read_text());na=json.loads((audit/'audit.json').read_text())
    out.mkdir(parents=True,exist_ok=False);view=out/'analysis-view';view.mkdir()
    drift=[path for path,h in oa['input_hashes'].items() if sha(ROOT/path)!=h]
    write(out/'original-evidence-immutability.json',{'status':'FAIL' if drift else 'PASS','drift':drift,'files_checked':len(oa['input_hashes']),'original_per_run_audit_pass':all(x['passed'] for x in oa['runs']),'original_campaign_completeness':'FAIL remains, missing attempt102'})
    if drift:raise RuntimeError('original evidence drift; do not combine or overwrite')
    rows=[];sources={}
    for epoch,doc in [('original-v1',prior),('continuation-v1',current)]:
        for r in doc['runs']:
            if not r.get('infrastructure_ok') or not r.get('p9'):continue
            copied=dict(r,analysis_execution_epoch=epoch);rows.append(copied)
            attempt=(ROOT/r['directory']).parent;target=view/r['id'];target.mkdir()
            (target/'prediction-before-query.json').write_bytes((attempt/'prediction-before-query.json').read_bytes())
            sources[r['id']]={'epoch':epoch,'attempt':str(attempt.relative_to(ROOT)),'result_sha256':sha(attempt/'result.json'),'prediction_sha256':sha(attempt/'prediction-before-query.json')}
    if len({r['id'] for r in rows})!=len(rows):raise RuntimeError('duplicate measurement across epochs')
    completed=current['status']=='COMPLETE' and len(current['runs'])==71 and na['status']=='PASS'
    status='COMPLETE_WITH_ORIGINAL_INFRA_MISSING' if completed else 'CONTINUATION_INCOMPLETE'
    write(view/'results.json',{'status':status,'runs':rows,'searches':seal['searches'],'execution_epochs':['original-v1','continuation-v1'],'acceptance':'NO_OVERALL_PASS','original_missing_id':'C-CZ15-g0.1-reference-P9-Z'})
    write(view/'source-attempt-map.json',sources)
    baseline=out/'frozen-generator-output';frozen_report(prep,view,baseline)
    s=json.loads((baseline/'results.json').read_text());s.update(execution_status=status,
        original_epoch={'started':102,'measured':101,'infra_missing':1,'whole_campaign_audit':'FAIL'},
        continuation_epoch={'started':len(current['runs']),'measured':sum(r.get('infrastructure_ok',False) for r in current['runs']),'raw_audit':na['status'],'freeze_commit':na['freeze_commit']},
        overall_acceptance='NO_OVERALL_PASS_ORIGINAL_INFRA_MISSING',no_model_refit=True,
        missing_reference_id='C-CZ15-g0.1-reference-P9-Z',D_sequence_clusters=9,execution_epochs_not_spliced_into_acceptance=True)
    for x in s['searches']:
        missing=12-x['reference_grid_n'];x['reference_missing_n']=missing
        x['reference_observed_unresolved_n']=x['reference_unresolved_n'];x['reference_unresolved_n']+=missing
        if missing:x['error_vs_unique_empirical_reference_s']=None
    oldcost=json.loads((ROOT/'data/p9-20261024-report-interrupted-v1/results.json').read_text())['cost']
    s['cost']['original_interrupted_start_to_cleanup_wall_s']=oldcost['interrupted_start_to_cleanup_wall_s']
    s['cost']['cost_note']='completed attempt elapsed excludes original unmeasured102, whose421.028s uncontrolled interval is separate; no net engineering-cost or population efficiency claim'
    write(out/'results.json',s)
    csvrows=list(csv.DictReader((baseline/'prediction-measurement-ledger.csv').open()))
    for r in csvrows:r['evidence_directory']=sources[r['id']]['attempt']
    with (out/'prediction-measurement-ledger.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
    events=[json.loads(x) for x in (prep/'attempts.jsonl').read_text().splitlines()]
    starts=[x for x in events if x['event']=='START_INTENT'];ends={x['id']:x for x in events if x['event']=='FINISH'}
    original_plan=json.loads((ROOT/'data/p9-20261024-freeze/plan.json').read_text());startids={x['id'] for x in starts};account=[]
    for r in original_plan['runs']+original_plan['search_slots']:
        state='FINISHED' if r['id'] in ends else ('ORIGINAL_INFRA_MISSING' if r['id'] in startids else ('UNUSED_SEARCH_STOP' if r['stage']=='C-search' else 'NOT_RUN'))
        account.append({'id':r['id'],'stage':r['stage'],'state':state})
    write(out/'budget-accounting.json',{'rows':account,'formal_started':sum(x['budget_class']=='formal' for x in starts),'development_started':sum(x['budget_class']=='development' for x in starts),'continuation_cap':173,'formal_original_cap':180,'unused_search_slots':7,'original_missing_not_retried':True,'no_overall_acceptance_pass':True})
    references=[]
    for r in original_plan['runs']:
        if r['stage']!='C-reference':continue
        measured=next((x for x in rows if x['id']==r['id']),None)
        references.append({'id':r['id'],'family':r['family'],'phase_s':r['phase_s'],'seed':r['sim_seed'],
            'observation':'ORIGINAL_INFRA_MISSING' if measured is None else ('FULL_WINDOW' if measured['p9']['complete_window'] else 'CENSORED'),
            'tilt_failure':None if measured is None else measured['p9']['tilt_ge_45_failure'],
            'observed_tilt_deg':None if measured is None else measured['p9']['max_tilt_deg']})
    write(out/'reference-grid.json',{'rows':references,'missing_is_never_safe':True,'definition':'independent single-seed noisy empirical grid, not probability truth'})
    inputs=[old/'results.json',old/'searches-sealed-before-reference.json',new/'results.json',new/'candidate-equivalence.json',audit/'audit.json',prep/'attempts.jsonl',ROOT/'data/p9-20261024-freeze/manifest.json',ROOT/'data/p9-20261024-continuation-v1-freeze/manifest.json',ROOT/'data/p9-20261024-audit-interrupted-v1/audit.json',ROOT/'data/p9-20261024-report-interrupted-v1/results.json',Path(__file__).resolve()]
    write(out/'input-manifest.json',{str(x.relative_to(ROOT)):sha(x) for x in inputs})
    (out/'README.md').write_text('两执行版本的描述性分析；原批完整性FAIL保留。没有把不同批次拼成一个验收PASS。\nanalysis-view只复制原事前预测记录供冻结统计器读取；source-attempt-map和根CSV指向真实源目录，原记录/模型均未改写。\n原始ULog仅Thor本地；参考缺失102保持null，不能用模型或邻格补齐。\n')
    write(out/'output-manifest.json',{str(x.relative_to(out)):sha(x) for x in sorted(out.rglob('*')) if x.is_file() and x!=out/'output-manifest.json'})
    print(status,'measured',len(rows),'starts',s['attempts']['formal'],'original missing1',flush=True)


if __name__=='__main__':main()
