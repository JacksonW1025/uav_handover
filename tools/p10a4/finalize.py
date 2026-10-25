#!/usr/bin/env python3
"""Bind canonical A4 evidence, costs and narrow conclusions; no flight access."""
from fractions import Fraction as F
import json
from pathlib import Path
import re
from data import ROOT,sha,write

BASE=ROOT/'data/p10-20261025-a4'

def main():
    summary=json.loads((BASE/'summary-final/study-summary.json').read_text())
    counter=json.loads((BASE/'contract-counterexample-final/counterexample.json').read_text())
    repro=json.loads((BASE/'reproduction/reproduction.json').read_text())
    assert summary['compatibility_relation']['actual_records_require_uniform_epsilon_at_least_display']>3
    assert F(counter['exact_P_norm_squared'])<9 and F(counter['q_forward_lower'])>F('9.80665')
    alpha=summary['first_capture_parameter_condition'];L=F(alpha['velocity_norm_upper']);E=F(alpha['capture_velocity_vector_error_upper']);a=F(alpha['alpha_sufficient_lower'])
    assert (1-a)*L+a*E==1 and .45471<float(a)<.45472
    audits={name:json.loads((BASE/f'audits-final/{name}/audit.json').read_text()) for name in ['T0','C04','CR06']}
    assert all(v['full_rows']==7350 and v['failure'] is None for v in audits.values())
    write(BASE/'conclusion.json',{'schema':'p10-a4-final-1','route':'B','overall_gate':'NOT_PASSED',
        'source_reference_and_initialization':'A3 source-08 bindings preserved; fixed allowed clock subclass, not all native timing',
        'model_internal_full_set_proofs':{k:{'epsilon':v['epsilon_P'],'rows':v['full_rows'],'audit':f'audits-final/{k}/audit.json','sha256':sha(BASE/f'audits-final/{k}/audit.json')} for k,v in audits.items()},
        'actual_error_interface':'REFUTED_FOR_COMPLETE_UNSTRUCTURED_PHYSICAL_STEP_BALL',
        'basis':{'record_lower':summary['compatibility_relation']['actual_records_require_uniform_epsilon_at_least_display'],
            'unsafe_ball_radius':counter['epsilon_ball_containing_this_input'],'largest_exactly_audited_epsilon':.001,
            'not_maximum_tolerance':True,'counterexample_scope':counter['scope']},
        'disturbance_support':summary['disturbance_support'],
        'actual_test_or_repair_admission':'NONE; proxy conditional decisions retained, no permission to skip real safety tests',
        'conditional_decision':summary['decision_change'],'first_capture_instant_only_alpha':alpha,
        'data_scope':'all8 old dev logs;4 retrospective check flights/3 groups/16 event windows; no observed>45deg window; false_low0 not a miss-rate validation',
        'M1_M2_scope':'future actual target and observation clocks used; retrospective output-P projection only, not complete M1/M2 certificates',
        'no_query_saving_claim':True,'no_global_method_impossibility_claim':True,'height_and_actual_intersample_output':'NOT_COVERED',
        'next':summary['next'],'new_SITL_starts':0,'new_development_or_formal_flights':0,'new_real_flights':0,
        'diagnostic_budget_used':0,'diagnostic_budget_cap':12,'B_C_D_started':False,'A5_started':False,
        'historical_files_preserved':repro['tracked_historical_files_compared'],
        'canonical_summary':'summary-final/study-summary.json','report':'../../docs/THOR_P10_A4_REPORT.md',
        'tests':'tests-final.log:77 passed; reproduction/reproduction.json:input/refit/exact cores/history checked',
        'publication':'publication.json records remote and CI separately; tests != theory gate != CI'})
    ledger=[
        {'artifacts':['inputs','inputs-complete'],'event':'offline parser stopped on dev07 p6 metrics format after six outputs; partial directories retained; no flight/protocol anomaly or retry of a flight','resolution':'fallback to existing p6 format for07/08; all8 final in inputs-interface'},
        {'artifacts':['inputs-final','inputs-interface','diagnosis','diagnosis-fixed'],'event':'fixed-origin comparison frame separated from current-yaw diagnostic; retained raw RREC p6 mismatch and corrected p7 actual network-target reconstruction','resolution':'canonical inputs-interface and fixed-frame common P; diagnosis-fixed metadata wording current target frame was stale, actual residual code uses frame_yaw0; final report states fixed frame'},
        {'artifacts':['theory-candidates','theory-final'],'event':'held target lag initially measured against captured target','resolution':'canonical theory-final lag uses advancing original runner p1_profile intent; no time shift/event deletion; original version retained'},
        {'artifacts':['audit-T0','audit-C04','audit-CR06','audits-final','independent-audit-initial.py'],'event':'three exact certificates run twice; final verifier adds first-capture dual-axis condition','resolution':'reproduction compares all initial audit core fields except timing/verifier hash exactly'},
        {'artifacts':['summary','summary-final'],'event':'old .4473718 component alpha condition not rotation-invariant dual-axis velocity condition','resolution':'final exact L=1.833891957049,E=1e-6 gives alpha>=.4547118539647824, first reset only; no full parameter-family claim'},
        {'artifacts':['contract-counterexample','contract-counterexample-final'],'event':'expanded interface scope text','resolution':'same rational counterexample; final states physical p/v/q support, may not satisfy observed clock-hold constraints'},
        {'artifacts':['tests.log','tests-final.log'],'event':'initial1 failed/13 passed: toy test compared FLU command to NED second-axis output','resolution':'correct test rotation, retain both logs; final77 regression passed; model not changed to force pass'},
        {'artifacts':['summary-final','conclusion.json'],'event':'parent independent summary feedback','resolution':'98D metric vs6D arbitrary input, future-clock hindsight, no >45deg examples and full preprocessing/evaluation/audit costs explicitly separated; not a claim parent ran private verifier'}]
    write(BASE/'ledger.json',{'schema':'p10-a4-difference-ledger-1','entries':ledger,'historical_files_overwritten':0,'new_flights':0})
    resources=[]
    for p in sorted(BASE.glob('*resource.txt')):
        text=p.read_text();entry={'file':p.name,'sha256':sha(p)}
        for key,pat in [('user_cpu_s',r'User time \(seconds\): ([\d.]+)'),('system_cpu_s',r'System time \(seconds\): ([\d.]+)'),('peak_rss_kib',r'Maximum resident set size \(kbytes\): (\d+)'),('exit_status',r'Exit status: (\d+)')]:
            match=re.search(pat,text);entry[key]=None if match is None else float(match[1])
        match=re.search(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (.+)',text);entry['wall_time_display']=None if match is None else match[1]
        resources.append(entry)
    write(BASE/'cost.json',{'schema':'p10-a4-cost-1','final_comparison':{'candidates':7,'point_replays':7,'storage_epsilon_levels':6,'storage_candidates':42,'distinct_exact_certificates':3,'exact_audit_executions':6},
        'retained_prior_work':'first floating version also evaluated42 candidates and selected trace; final version adds7 direct replays; proof-input generation retraces3; preprocessing/fit12trials/reproduction/tests/audit costs additional',
        'no_query_saving_demonstrated':True,'measured_resources':resources,'sum_recorded_cpu_seconds':sum((r['user_cpu_s'] or 0)+(r['system_cpu_s'] or 0) for r in resources),
        'coverage':'recorded commands only, not total human time or complete earlier exploratory preprocessing CPU; unmeasured work is not claimed free'})
    write(BASE/'evidence-manifest.json',{'schema':'p10-a4-evidence-manifest-1','files':{str(p.relative_to(ROOT)):sha(p) for p in sorted([*BASE.rglob('*'),* (ROOT/'tools/p10a4').glob('*.py'),ROOT/'config/p10_a4.json',ROOT/'tests/test_p10_a4.py',ROOT/'docs/THOR_P10_A4_REPORT.md',ROOT/'docs/THOR_P10_A4_PROOF.md']) if p.is_file() and '__pycache__' not in str(p) and p.name not in ['evidence-manifest.json','publication.json']},
        'excluded_self_and_publication_receipt':True,'raw_ULog':'not copied; original paths and hashes in inputs-interface/manifest.json'})

if __name__=='__main__':main()
