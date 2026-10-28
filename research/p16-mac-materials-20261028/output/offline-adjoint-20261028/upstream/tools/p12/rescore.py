#!/usr/bin/env python3
"""P12 v2 independent rescoring/denominators, no forecasts or SITL launches."""
import argparse,collections,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from p12.score import score


def counts():
    return {'total':0,'classifiable_label_n':0,'unknown_n':0,'not_reached_n':0,'agreement_n':0,
        'safe_agreement_n':0,'failure_witness_agreement_n':0,'false_alarm_n':0,'danger_miss_n':0,
        'both_complete_trajectory_n':0}


def add(counter,risk,component):
    counter['total']+=1;label=risk['comparisons'][component]
    known=risk['classification_eligible'][component]
    counter['classifiable_label_n']+=known;counter['unknown_n']+=label.startswith('UNKNOWN')
    counter['not_reached_n']+=label=='NOT_REACHED';counter['both_complete_trajectory_n']+=risk['full_trajectory_eligible'][component]
    counter['agreement_n']+=label=='AGREEMENT';counter['false_alarm_n']+=label=='FALSE_ALARM';counter['danger_miss_n']+=label=='DANGER_MISS'
    counter['safe_agreement_n']+=label=='AGREEMENT' and risk['predicted'][component]=='SUCCESS'
    counter['failure_witness_agreement_n']+=label=='AGREEMENT' and risk['predicted'][component]=='FAILURE'


def aggregate(reports):
    result={}
    for case,report in reports.items():
        for name,r in report['models'].items():
            model=result.setdefault(name,{'whole':{k:counts() for k in ['tilt','height','task']},
                'events':{k:counts() for k in ['tilt','height','task']},
                'error_denominators':{'common_prefix_rmse_n':0,'complete_trajectory_rmse_n':0,'complete_peak_error_n':0}})
            for c in ['tilt','height','task']:add(model['whole'][c],r['risk'],c)
            for event in r['event_windows']:
                for c in ['tilt','height','task']:add(model['events'][c],event['risk'],c)
            model['error_denominators']['common_prefix_rmse_n']+=r['position_norm_m'] is not None
            model['error_denominators']['complete_trajectory_rmse_n']+=r['position_norm_m'] is not None and r['risk']['full_trajectory_eligible']['tilt']
            model['error_denominators']['complete_peak_error_n']+=r['peak_abs_error_deg'] is not None
    return result


def run(analysis,out):
    out.mkdir(parents=True,exist_ok=False);paths=[ROOT/'tools/p11/score.py',ROOT/'data/p12-20261026-preparation/attempts.jsonl',
        ROOT/'data/p11-20261026-analysis/conclusion.json',ROOT/'data/p11-20261025-formal/diagnosis.json']
    predictions=sorted(analysis.glob('*-predictions/prediction.json'))
    for pred in predictions:
        case=pred.parent.name.removesuffix('-predictions')
        paths+=[analysis/(case+'-score/score.json'),pred,*pred.parent.glob('*.npz'),
            analysis/(case+'-packed/measurement.npz'),analysis/(case+'-measured/measurement.json')]
    before={str(p.relative_to(ROOT)):sha(p) for p in paths};write(out/'original-evidence-before.json',before)
    reports={};changes=[];old_labels={'tilt':collections.Counter(),'task':collections.Counter()};old_metrics_changed=[]
    for pred in predictions:
        case=pred.parent.name.removesuffix('-predictions');packed=analysis/(case+'-packed');measurement=analysis/(case+'-measured/measurement.json')
        new=score(pred.parent,packed,measurement,out/case);reports[case]=new
        old=json.loads((analysis/(case+'-score/score.json')).read_text())
        for name,r in new['models'].items():
            prior=old['models'][name];old_labels['tilt'][prior['risk_comparison']]+=1;old_labels['task'][prior['task_risk_comparison']]+=1
            for field in ['risk_comparison','task_risk_comparison']:
                if r[field]!=prior[field]:changes.append({'case':case,'model':name,'field':field,'old':prior[field],'new':r[field],
                    'predicted_tilt_peak_deg':r['tilt_peak_deg'],'prediction_complete':r['full_prediction']})
            for i,(was,now) in enumerate(zip(prior['event_windows'],r['event_windows'])):
                if was['censored']!=now['censored']:changes.append({'case':case,'model':name,'field':f'event[{i}].censored','old':was['censored'],'new':now['censored']})
            for key in ['position_norm_m','velocity_norm_m_s','tilt_error_deg','peak_abs_error_deg','common_prefix_peak_abs_error_deg','altitude_loss_m']:
                if prior[key]!=r[key]:old_metrics_changed.append({'case':case,'model':name,'metric':key,'old':prior[key],'new':r[key]})
    after={str(p.relative_to(ROOT)):sha(p) for p in paths};drift=[p for p in before if before[p]!=after[p]]
    if drift:raise RuntimeError('original evidence drift '+str(drift))
    totals=aggregate(reports);write(out/'denominators.json',totals)
    ledger=[json.loads(l) for l in (ROOT/'data/p12-20261026-preparation/attempts.jsonl').read_text().splitlines()]
    starts=[l for l in ledger if l['event']=='START_INTENT']
    result={'schema':'p12-scoring-correction-2','status':'PASS_INDEPENDENT_RESCORING','prior_commit':'d917f2d85855e869e47bdf9fa044d228b8514c25',
        'cases':len(reports),'predictions':sum(len(r['models']) for r in reports.values()),'scorer_sha256':sha(ROOT/'tools/p12/score.py'),
        'original_evidence_unchanged':not drift,'old_label_counts':{k:dict(v) for k,v in old_labels.items()},
        'changes':changes,'point_metric_changes':old_metrics_changed,'development_starts':len(starts),'formal_starts':sum(s['budget_class']=='formal' for s in starts),
        'point_metrics_checked':['position_norm_m','velocity_norm_m_s','tilt_error_deg','peak_abs_error_deg','common_prefix_peak_abs_error_deg','altitude_loss_m'],
        'height_metric_scope':'fixed task-start baseline; only predicted points in the observed task comparison window; unobserved continuation excluded',
        'new_SITL_starts':0,'predictions_regenerated':False,'models_refitted':False,
        'semantic_rule':'failure can be established by a valid prefix; safe incomplete prefixes remain UNKNOWN; full-trajectory metrics use complete pairs only',
        'P11':'all files/validity unchanged; independent P12 scorer only',
        'original_report_limit':'task AGREEMENT from v1 truncated uncorrelated_capture cannot support whole-task agreement'}
    write(out/'correction.json',result);print(json.dumps({k:result[k] for k in ['status','cases','predictions','original_evidence_unchanged','new_SITL_starts']}));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--analysis',type=Path,default=ROOT/'data/p12-20261026-analysis')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.analysis.resolve(),a.output.resolve())
