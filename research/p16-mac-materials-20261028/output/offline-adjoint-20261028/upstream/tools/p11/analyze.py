#!/usr/bin/env python3
"""P11 grouped contrasts and prediction assessment. Analysis only, never starts SITL."""
import argparse
import csv
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from p1_metrics import clean
from p9_model import sha,write
from p11.score import so3,summary,score
from p11.isolated import predict
from p11.observe import multiply


def at(d,t,key):
    j=np.searchsorted(d['profile_s'],t,side='right')-1
    if np.any(j<0):raise RuntimeError('missing comparison prehistory')
    return d[key][j]


def contrast(data,branches,plan):
    base=data['NORMAL'];start=plan['common_first_gap_profile_s'];pre=np.arange(start-.5,start,.004)
    limits={'p':.1,'v':.15,'SO3':2.5,'action':.1,'h':.5};prestate={};valid=True
    for branch in branches:
        if branch=='NORMAL':continue
        d=data[branch]
        m={'p':float(np.linalg.norm(at(d,pre,'position')-at(base,pre,'position'),axis=1).max()),
           'v':float(np.linalg.norm(at(d,pre,'velocity')-at(base,pre,'velocity'),axis=1).max()),
           'SO3':float(so3(at(d,pre,'attitude'),at(base,pre,'attitude')).max()),
           'action':float(np.abs(at(d,pre,'action')-at(base,pre,'action')).max()),
           'h':float(np.linalg.norm(at(d,pre,'h_after')-at(base,pre,'h_after'),axis=1).max())}
        m['matched']=bool(all(m[k]<=limits[k] for k in limits));valid=valid and m['matched'];prestate[branch]=m
    end=min(plan['horizon_profile_s'],*[float(d['profile_s'][-1]) for d in data.values()])
    grid=np.arange(start,end,.004);responses={};delta={}
    for branch in branches:
        if branch=='NORMAL':continue
        d=data[branch];delta[branch]={}
        for field,label,threshold in [('position','p',.05),('velocity','v',.1),('action','action',.05),('h_after','h',.1)]:
            diff=at(d,grid,field)-at(base,grid,field);delta[branch][label]=diff;norm=np.linalg.norm(diff,axis=1)
            hit=np.flatnonzero(norm>threshold)
            responses.setdefault(branch,{})[label]={'peak_norm':float(norm.max()),'first_deviation_profile_s':float(grid[hit[0]]) if len(hit) else None,
                'threshold':threshold,'last_common_profile_s':float(grid[-1]),'not_recovered_at_end':bool(norm[-1]>threshold)}
        angle=so3(at(d,grid,'attitude'),at(base,grid,'attitude'));hit=np.flatnonzero(angle>2.)
        responses[branch]['SO3']={'peak_deg':float(angle.max()),'first_deviation_profile_s':float(grid[hit[0]]) if len(hit) else None,'threshold_deg':2.}
    nonadd={}
    for label in ['p','v','action','h']:
        value=delta['AB'][label]-delta['A'][label]-delta['B'][label]
        nonadd[label]={'peak_norm':float(np.linalg.norm(value,axis=1).max()),'RMS_norm':float(np.sqrt(np.mean(np.sum(value*value,axis=1)))),
            'scope':'common observed prefix; no superposition or causal-contribution claim'}
    qn=at(base,grid,'attitude');relative={}
    for branch in ['A','B','AB']:
        qb=at(data[branch],grid,'attitude')
        relative[branch]=np.array([multiply(a*np.array([1,-1,-1,-1]),b) for a,b in zip(qn,qb)])
    ordered=np.array([multiply(a,b) for a,b in zip(relative['A'],relative['B'])])
    nonadd['SO3_ordered_A_then_B']={'geodesic_deg':summary(so3(ordered,relative['AB'])),
        'scope':'relative rotation product diagnostic, no Euler subtraction; not an assertion that rotations commute or effects are causally additive'}
    truth_responses={}
    if all('truth_pv' in d and 'truth_q' in d for d in data.values()):
        for branch in branches:
            if branch=='NORMAL':continue
            dx=at(data[branch],grid,'truth_pv')-at(base,grid,'truth_pv')
            truth_responses[branch]={'position_norm_m':summary(np.linalg.norm(dx[:,:3],axis=1)),
                'velocity_norm_m_s':summary(np.linalg.norm(dx[:,3:6],axis=1)),
                'SO3_deg':summary(so3(at(data[branch],grid,'truth_q'),at(base,grid,'truth_q'))),
                'scope':'held Gazebo pose callback truth, approximately20ms cadence; callback/acquisition uncertainty retained, not instantaneous250Hz truth'}
    return {'matched_prestate':valid,'prestate':prestate,'normal_contrasts_valid':sum(m['matched'] for m in prestate.values()),
        'pairing':'approximate warmup/task/seed matching, no simulator/EKF/clock snapshot',
        'responses':responses,'truth_responses':truth_responses,'nonadditivity_AB_minus_A_minus_B':nonadd,
        'common_observed_end_profile_s':end,'full_common_window':bool(end>=plan['nominal_horizon_profile_s']-.01)}


def hold_diagnostic(d):
    sample=d['sample_us'].astype(np.int64);lp=d['lp_sample'].astype(np.int64)
    dt=np.diff(sample)/1e6;naive=d['position'][1:]-d['position'][:-1]-d['velocity'][:-1]*dt[:,None]
    h=np.diff(lp)/1e6;held=d['position'][1:]-d['position'][:-1]-d['velocity'][:-1]*h[:,None]
    return {'naive_position_residual_m':summary(np.linalg.norm(naive,axis=1)),
        'explicit_LP_hold_position_residual_m':summary(np.linalg.norm(held,axis=1)),
        'hold_edges':int(np.sum(h==0)),'advance_us':sorted(map(int,np.unique(np.diff(lp)))),
        'interpretation':'fixed-velocity one-step diagnostic, same inputs/parameters; reduction identifies observation-clock contribution, not a causal variance fraction of all physical model error'}


def analyze(formal,out,predict_missing=False):
    out.mkdir(parents=True,exist_ok=False);p=json.loads((ROOT/'config/p11.json').read_text());results={};measurements={};datasets={};scores={};hold={};missing=[]
    models=formal/'models'
    if models.exists() and (models/'seal.json').exists():
        seal=json.loads((models/'seal.json').read_text())
        for file,key in [('models.json','model_sha256'),('policy.npz','policy_arrays_sha256'),('fit.json','fit_sha256')]:
            if sha(models/file)!=seal[key]:raise RuntimeError('sealed model drift')
    for row in p['rows']:
        case=formal/row['id'];path=case/'result.json'
        if not path.exists():missing.append(row['id']);continue
        r=json.loads(path.read_text());results[row['id']]=r
        if not r.get('p11_valid_scientific_result'):continue
        measured=json.loads((case/'measured/measurement.json').read_text());measurements[row['id']]=measured
        d=dict(np.load(case/'packed/measurement.npz'));datasets[row['id']]=d;hold[row['id']]=hold_diagnostic(d)
        pred=case/'prediction'
        if not pred.exists() and predict_missing:
            if not (models/'seal.json').exists():raise RuntimeError('no sealed model for heldout prediction')
            pred=out/row['id']/'prediction';pred.parent.mkdir(parents=True,exist_ok=True);predict(case/'packed',models,pred)
        if pred.exists():
            dest=out/row['id']/'score';dest.parent.mkdir(parents=True,exist_ok=True)
            scores[row['id']]=score(pred,case/'packed',case/'measured/measurement.json',dest)
    pairs=[]
    for family in [f'F{i}' for i in range(1,7)]:
        for rep in [1,2]:
            rows=[r for r in p['rows'] if r['family']==family and r['rep']==rep];branches={r['branch']:r['id'] for r in rows}
            if not all(i in datasets for i in branches.values()):
                pairs.append({'family':family,'rep':rep,'status':'PARTIAL_OR_PENDING','missing':[i for i in branches.values() if i not in datasets]});continue
            doc=json.loads((formal/branches['NORMAL']/'packed/prediction-input.json').read_text())
            c=contrast({b:datasets[i] for b,i in branches.items()},branches,doc['plan'])
            primary={b:measurements[i]['frozen_flight_outcome']['outcome'] for b,i in branches.items()}
            task={b:measurements[i]['task_outcome'] for b,i in branches.items()}
            ab_plan=json.loads((formal/branches['AB']/'packed/prediction-input.json').read_text())['plan']
            ab_events=[json.loads(x) for x in (formal/branches['AB']/'run/events.jsonl').read_text().splitlines()]
            B=ab_plan['windows_profile_s'][1]
            reached=any(e['event']=='p5_gap_started' and np.max(np.abs(np.array(e['planned_profile_s'])-B))<1e-7 for e in ab_events)
            c.update({'family':family,'rep':rep,'split':rows[0]['split'],'status':'COMPLETE_CLUSTER','primary':primary,'task':task,
                'censored':{b:measurements[i]['censored'] for b,i in branches.items()},
                'combined_B_started':reached,
                'task_single_safe_combined_fail':bool(c['matched_prestate'] and reached and task['A']==task['B']=='SUCCESS' and task['AB']=='FAILURE'),
                'repair_task_failure_to_success':bool(task['AB']=='FAILURE' and task['REPAIR']=='SUCCESS')})
            pairs.append(c)
    phases=[]
    for row in p['rows']:
        if row['stage']!='phase' or row['id'] not in measurements:continue
        s=json.loads((formal/row['id']/'synchronization/synchronization.json').read_text())
        doc=json.loads((formal/row['id']/'packed/prediction-input.json').read_text())
        cutoff=json.loads((formal/row['id']/'packed/manifest.json').read_text())['initial_cutoff_host_ns'];achieved=[]
        for event in s['event_transitions']:
            lo,hi=event['native_query_host_interval_ns']
            if lo is None:continue
            bounds=[(lo-cutoff)/1e9,(hi-cutoff)/1e9]
            for i,(a,b) in enumerate(doc['plan']['windows_profile_s']):
                area=[a-.008,b+.016] if event['kind']=='CAPTURE_OR_STALE' else [b-.016,b+.032]
                if bounds[1]>=area[0] and bounds[0]<=area[1]:achieved.append({**event,'planned_event_index':i,
                    'profile_query_interval_s':bounds,'LP_phase_mod_8000_us':event['LP_age_us']%8000})
        phases.append({'id':row['id'],'intent_s':row['event_shift_s'],'rep':row['rep'],'event_transitions':s['event_transitions'],
            'achieved_planned_event_phases':achieved,'read_phase_bins':s['phase_bins_sample_minus_LP_us']})
    phase_sets={}
    for x in phases:
        group=phase_sets.setdefault(str(x['intent_s']),{})
        for e in x['achieved_planned_event_phases']:group.setdefault(str(e['planned_event_index'])+'-'+e['kind'],set()).add(e['LP_phase_mod_8000_us'])
    phase_overlap=any(phase_sets[a][key]&phase_sets[b][key] for a in phase_sets for b in phase_sets if a!=b for key in set(phase_sets[a])&set(phase_sets[b]))
    model_summary={}
    for split in ['development','heldout']:
        ids=[r['id'] for r in p['rows'] if r['split']==split and r['id'] in scores]
        model_summary[split]={}
        for model in ['M0','M1','M2']:
            rs=[scores[i]['models'][model] for i in ids];known_peak=[r['peak_abs_error_deg'] for r in rs if r['peak_abs_error_deg'] is not None]
            model_summary[split][model]={'runs':len(rs),'complete_peak_error_n':len(known_peak),'complete_peak_error_mean_deg':float(np.mean(known_peak)) if known_peak else None,
                'complete_peak_error_max_deg':max(known_peak) if known_peak else None,
                'danger_misses':sum(r['risk_comparison']=='DANGER_MISS' for r in rs),'false_alarms':sum(r['risk_comparison']=='FALSE_ALARM' for r in rs),
                'task_danger_misses':sum(r['task_risk_comparison']=='DANGER_MISS' for r in rs),'task_false_alarms':sum(r['task_risk_comparison']=='FALSE_ALARM' for r in rs),
                'unknown':sum('UNKNOWN' in r['risk_comparison'] or 'UNKNOWN' in str(r['task_risk_comparison']) for r in rs),
                'mean_position_rmse_m':float(np.mean([r['position_norm_m']['rmse'] for r in rs])) if rs else None,
                'mean_velocity_rmse_m_s':float(np.mean([r['velocity_norm_m_s']['rmse'] for r in rs])) if rs else None,
                'compute_s':sum(r['compute_s'] for r in rs),'note':'censored cases retained for prefix/risk; never treated as complete peak truth; frames are not independent trials'}
    result={'schema':'p11-analysis-1','status':'COMPLETE' if len(results)==72 and len(measurements)==72 and len(scores)==72 else 'PARTIAL',
        'formal_results':len(results),'valid_measurements':len(measurements),'predicted_scored':len(scores),'missing':missing,
        'primary_failures':sum(m['frozen_flight_outcome']['outcome']=='FAILURE' for m in measurements.values()),
        'task_failures':sum(m['task_outcome']=='FAILURE' for m in measurements.values()),'censored':sum(m['censored'] for m in measurements.values()),
        'complete_five_arm_clusters':sum(x['status']=='COMPLETE_CLUSTER' for x in pairs),
        'prestate_matched_clusters':sum(x.get('matched_prestate',False) for x in pairs),
        'valid_normal_contrasts':sum(x.get('normal_contrasts_valid',0) for x in pairs),
        'full_common_window_clusters':sum(x.get('full_common_window',False) for x in pairs),
        'pairs':pairs,'hold_diagnostics':hold,'model_summary':model_summary,'phase_details':phases,
        'phase_achieved_bins':{k:{e:sorted(values) for e,values in v.items()} for k,v in phase_sets.items()},
        'phase_identifiability':'NOT_IDENTIFIABLE' if phase_overlap else ('LIMITED_OBSERVED_SEPARATION_ONLY' if len(phases)==6 else 'INCOMPLETE'),
        'theory_status':'NOT_ESTABLISHED; no deterministic event-composition or full repair admission certificate',
        'no_extra_SITL':True,'no_post_heldout_model_refit':True,'all_outcomes_retained':True}
    write(out/'analysis.json',clean(result))
    with (out/'outcomes.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['id','split','family','rep','branch','primary','task','censored','max_tilt_deg','altitude_loss_m']);writer.writeheader()
        for r in p['rows']:
            m=measurements.get(r['id']);writer.writerow({k:r[k] for k in ['id','split','family','rep','branch']}|({'primary':m['frozen_flight_outcome']['outcome'],'task':m['task_outcome'],'censored':m['censored'],
                'max_tilt_deg':m['whole']['max_tilt_deg'],'altitude_loss_m':m['whole']['max_altitude_loss_m']} if m else {'primary':'NOT_MEASURED'}))
    print(json.dumps({k:result[k] for k in ['status','formal_results','valid_measurements','primary_failures','task_failures','censored','prestate_matched_clusters','valid_normal_contrasts','phase_identifiability']}))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--formal',type=Path,default=ROOT/'data/p11-20261025-formal')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--predict-missing',action='store_true');a=p.parse_args();analyze(a.formal,a.output,a.predict_missing)
