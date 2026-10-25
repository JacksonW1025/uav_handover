#!/usr/bin/env python3
"""A4 finite study summary; no new fit, flight, or change to historical gates."""
import argparse,json,math
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from data import ROOT,write,sha
from experiment import load_inputs


def main(base,out):
    out.mkdir(parents=True,exist_ok=False)
    inputs=json.loads((base/'inputs-interface/manifest.json').read_text());comparison=json.loads((base/'model-comparison/comparison.json').read_text())
    model_summary=[]
    for name in sorted(set(r['model'] for r in comparison['results'])):
        check=[r for r in comparison['results'] if r['model']==name and r['role']=='retrospective_check']
        windows=[w for r in check for w in r['rolling'] if w['horizon_s']==2 and w['stage'] in ['capture','resume']]
        model_summary.append({'model':name,'check_flights':len(check),'check_condition_groups':len(set(r['group'] for r in check)),
            'event_2s_windows_descriptive_not_independent':len(windows),
            'mean_abs_peak_proxy_tilt_error_deg':float(np.mean([abs(w['peak_tilt_error_deg']) for w in windows])),
            'max_abs_peak_proxy_tilt_error_deg':max(abs(w['peak_tilt_error_deg']) for w in windows),
            'observed_over45_windows':sum(w['observed_peak_proxy_tilt_deg']>45 for w in windows),
            'observed_peak_range_deg':[min(w['observed_peak_proxy_tilt_deg'] for w in windows),max(w['observed_peak_proxy_tilt_deg'] for w in windows)],
            'false_low_windows':sum(w['misses_observed_45deg'] for w in windows),
            'mean_full_roll_rmse_NED_p_v_q':np.mean([r['full_logged_target_rollout_rmse'] for r in check],axis=0).tolist(),
            'mean_measured_one_step_seconds':float(np.mean([r['one_step_seconds_per_row'] for r in check]))})
    stages={}
    for row in inputs['runs']:
        for name,count in row['phase_counts'].items():
            entry=stages.setdefault(name,{'flights':[],'rows':0});entry['flights'].append(row['run']);entry['rows']+=count
    stage_exclusions=[]
    for row,a in load_inputs(base/'inputs-interface'):
        stage_exclusions.append({'run':row['run'],'raw_rows':len(a['t']),'pre_profile_bound_rows':int((a['t']<row['profile_start_bound_us']).sum()),
            'invalid_mapped_rows':int((~a['valid']).sum()),'capture_aux_unknown_rows':int((~a['cap_valid']).sum()),
            'native_non4ms_edges':int((np.diff(a['t'])!=4000).sum()),'aborted':row['aborted'],
            'repeat_event_data':row['closed_gaps']>1,'format':row['metrics_format']})
    audits={name:json.loads((base/f'audits-final/{name}/audit.json').read_text()) for name in ['T0','C04','CR06']}
    for a in audits.values():assert a['status']=='VERIFIED_CONDITIONAL_PROXY_SEQUENCE' and a['full_rows']==7350
    scans=json.loads((base/'theory-final/tolerance-candidates.json').read_text());direct=json.loads((base/'theory-final/direct-replay.json').read_text())
    table=[]
    for d in direct['cases']:
        name=d['case']['id'];verified=audits.get(name)
        table.append({'candidate':d['case'],'point_full_rows':d['rows'],'point_proxy_tilt_deg':math.degrees(math.atan(d['max_q_upper']/9.80665)),
            'point_passes_declared_limits':d['candidate_admit'],'point_max_lag':d['max_lag_upper'],'point_max_lead':d['max_lead_upper'],
            'point_cumulative_abs_lag':d['nominal_integrated_absolute_lag_m_s'],
            'exact_certificate_epsilon':None if verified is None else verified['epsilon_P'],
            'exact_q_upper':None if verified is None else verified['max_q_upper_display'],
            'other_grid_points':'numerical candidates only; UNKNOWN is a certificate result, not predicted flight failure'})
    metric=json.loads((base/'metric-audit/audit.json').read_text());counter=json.loads((base/'contract-counterexample/counterexample.json').read_text())
    lower=max(r['P_norm_lower_display'] for r in metric['checks']);assert lower>3 and F(counter['exact_P_norm_squared'])<9
    relation={'actual_records_require_uniform_epsilon_at_least_display':lower,
        'largest_exactly_audited_conditional_epsilon':.001,'ratio_to_that_checked_epsilon':lower/.001,
        'no_claim_of_global_tolerance_maximum':True,
        'full_uniform_ball_epsilon_ge3':'EXACT_COUNTEREXAMPLE in unchanged first88ms; not merely current covariance construction failure',
        'important_scope':'ball discards observed hold/clock/error-correlation constraints and may contain unrealizable residuals. This is NOT impossibility for a clock-constrained/structured ball intersection or for all Lyapunov methods'}
    # A computable family condition for the first velocity target reset only.
    reset=audits['C04']['first_capture_parameter_constraint']
    reset={**reset,'alpha_sufficient_lower_display':float(F(reset['alpha_sufficient_lower']))}
    write(out/'study-summary.json',{'route':'B','route_scope':'retain M0 as retrospective known-target local-response/engineering-comparison model; current unstructured-step-ball safety interface not viable for mapped data',
        'theory_gate':'NOT_PASSED_FOR_ACTUAL_SYSTEM','conditional_proxy_certificates':list(audits),
        'new_A4_models':2,'model_comparison':model_summary,'effective_old_logs':8,'semantic_condition_groups':len(set(r['group'] for r in inputs['runs'])),
        'phase_coverage':stages,'exclusions':stage_exclusions,'all_data_already_seen':True,'not_prospective_validation':True,
        'repair_comparison':table,'compatibility_relation':relation,
        'first_capture_parameter_condition':reset,
        'decision_change':'at epsilon .001 direct point replay accepts T0 and C04; full covariance candidate for T0 is UNKNOWN, C04 has exact full-set certificate. This is conditional model admission, not permission to skip real safety tests',
        'evaluation_budget':{'same_candidates':7,'point_replays':7,'storage_candidates_per_epsilon':7,'epsilon_grid_points':6,'exact_full_audits':3,
            'preprocessing_and_proof_costs_additional':True,'fewer_evaluations_demonstrated':False},
        'measurement_metric_timing':'flow innovation before next constrained capture jump plus separately checked reset defect. J propagates physical-flow error into captured state; it is not independent zero post-jump state error',
        'disturbance_support':'98-state metric, but arbitrary per-step model-error injection ONLY in current p/v/q (6 physical coordinates). Queue shifts are deterministic, capture resets constrained with separate cast budgets. This is NOT a certificate for arbitrary98-dimensional disturbance balls',
        'M1_M2_metric_scope':'common output/baseline-interface P projection for comparison only; different observer/q-history/acceleration states need their own full certificate. No M0 tolerance is asserted for those models',
        'next':'stop expanding the current unstructured per-step ball construction. If separately authorized, first derive a source-clock observation/storage interface and defensible colored/mode-dependent error constraints; do not autonomously start A5/B/C/D',
        'new_SITL_starts':0,'diagnostic_budget_used':0,'diagnostic_budget_cap':12,'new_real_flights':0,'B_C_D_started':False,'A5_started':False})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.base,a.output)
