#!/usr/bin/env python3
"""Summarize post-fix preparation batches against the three open P0 items; never edits runs."""
import json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PREP=ROOT/'data/preparation-20261011'
# Lockstep fix is in batch-03 onward; output-chain trace in batch-04 onward.
BATCHES=['batch-03','batch-04','batch-05']
GATE={'p99_us':4000,'max_us':12000,'longest_over_target_steps':2,'overwritten_fraction':0.001,
      'basis':'Recorded engineering acceptance agreement: 4 ms physics step, 12 ms maximum. The 12.5 ms rotor time constant is context, not proof of policy delay tolerance or stability.'}
def load(p):return json.loads(p.read_text())
def upper95(n):return 3/n if n else None  # rule of three, zero events in n trials
def measurement_errors(measurement):
    errors=[]
    if measurement.get('status')!='MEASURED':errors.append('measurement status')
    if set(measurement.get('motors',{}))!={'0','1','2','3'}:errors.append('four motors required')
    tails=measurement.get('partial_tail_bytes',{})
    if set(tails)!={'0','1','2','3'} or any(tails.values()):errors.append('missing or partial trace')
    overwritten=measurement.get('px4_overwritten_publications',{}).get('neural_bracketed')
    if overwritten is None or overwritten<0:errors.append('missing overwrite counter')
    for motor,value in measurement.get('motors',{}).items():
        neural=value.get('neural',{});age=neural.get('applied_age_us') or {}
        if not neural.get('steps') or age.get('count')!=neural.get('steps'):errors.append(motor+': incomplete applied samples')
        if neural.get('negative_age_steps')!=0:errors.append(motor+': negative or missing age count')
        if not all(isinstance(age.get(key),(int,float)) and math.isfinite(age[key]) for key in ['p99','max']):errors.append(motor+': invalid age statistics')
    return errors

def startup_ok(audit):
    startup=audit['startups']
    return startup['passed'] and startup['count']>0 and startup['count']==len(startup['runs']) and all(run['passed'] for run in startup['runs'])

def main():
    flights=starts=raptor=0;crashes=[];chain=[];errors=[];audits={};motor_chain={str(motor):[] for motor in range(4)};input_hashes={}
    for b in BATCHES:
        a=load(PREP/b/'batch-audit.json')
        audits[b]=a
        input_hashes[str((PREP/b/'batch-audit.json').relative_to(ROOT))]=hashlib.sha256((PREP/b/'batch-audit.json').read_bytes()).hexdigest()
        if not startup_ok(a):errors.append(b+': startup audit failed')
        for r in a['startups']['runs']:
            starts+=1
            if r['px4_exit_codes']!=[0] or r['crash_markers']:crashes.append(r['directory'])
        for r in a['flights']['runs']:
            flights+=1;raptor+=r['kind']!='classic_hover'
            if r['px4_exit_codes']!=[0] or r['crash_markers']:crashes.append(r['directory'])
            if b in ['batch-04','batch-05'] and r['kind']!='classic_hover':
                path=ROOT/r['directory']/'output-chain.json'
                if not path.exists():errors.append(r['directory']+': missing output measurement');continue
                oc=load(path)
                input_hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
                failures=measurement_errors(oc)
                if failures:errors.append(r['directory']+': '+', '.join(failures));continue
                for motor in motor_chain:
                    motor_chain[motor].append(oc['motors'][motor]['neural'])
                m=oc['motors']['0']['neural']
                chain.append({'run':r['directory'],'p99':m['applied_age_us']['p99'],'max':m['applied_age_us']['max'],
                    'longest':m['longest_over_target_steps'],'steps':m['steps'],
                    'overwritten':m['commands_overwritten_in_gazebo']+(oc['px4_overwritten_publications']['neural_bracketed'] or 0)})
    steps=sum(c['steps'] for c in chain);over=sum(c['overwritten'] for c in chain)
    gate_ok=bool(chain) and all(c['p99']<=GATE['p99_us'] and c['max']<=GATE['max_us'] and c['longest']<=GATE['longest_over_target_steps'] for c in chain) and over/steps<GATE['overwritten_fraction']
    motor_summary={}
    for motor,rows in motor_chain.items():
        motor_steps=sum(row['steps'] for row in rows)
        motor_over=sum(row['commands_overwritten_in_gazebo'] for row in rows)+sum(entry['overwritten'] for entry in chain)-sum(row['commands_overwritten_in_gazebo'] for row in motor_chain['0'])
        passed=bool(rows) and all(row['applied_age_us']['p99']<=GATE['p99_us'] and row['applied_age_us']['max']<=GATE['max_us'] and row['longest_over_target_steps']<=GATE['longest_over_target_steps'] for row in rows) and motor_over/motor_steps<GATE['overwritten_fraction']
        motor_summary[motor]={'runs':len(rows),'steps':motor_steps,'overwritten_total':motor_over,'gate_met':passed,
            'worst_p99_us':max((row['applied_age_us']['p99'] for row in rows),default=None),'worst_max_us':max((row['applied_age_us']['max'] for row in rows),default=None)}
    gate_ok=gate_ok and all(value['gate_met'] for value in motor_summary.values()) and not errors
    startup_total=starts+flights  # every flight is also a cold start
    out={'scope':'P0 closure assessment from frozen post-fix preparation batches; historical p0-20261010 acceptance.json unchanged.',
      'batches':BATCHES,
      'item1_crash':{'post_fix_flights':flights,'post_fix_raptor_flights':raptor,'startup_only_runs':starts,'crashes':crashes,
         'pre_fix_raptor_crash_rate':'4/24 (p0-20261010 normal runs + batch-02)',
         'p_zero_if_unfixed_at_pre_fix_rate':(1-4/24)**raptor,'residual_rate_upper95_per_flight':upper95(flights),
         'root_cause':'LockstepScheduler caller-mutex lifetime race (batch-02 core, tests/lockstep_lifetime_test.cpp reproduces, fixed in research/platform/lockstep_scheduler.cpp)',
         'not_proven':'The p0 raptor-hover-01 SIGSEGV has no stack; a dangling caller stack mutex is consistent with it but not proven.'},
      'item2_startup':{'consecutive_startups_without_sensor_failure':startup_total,'residual_rate_upper95':upper95(startup_total),
         'change':'GZ_IP=127.0.0.1 and strict readiness gate','not_proven':'Multi-NIC endpoint selection remains a hypothesis, not a demonstrated root cause.'},
      'item3_output_chain':{'gate':GATE,'runs':len(chain),'neural_steps':steps,'overwritten_total':over,'overwritten_fraction':over/steps if steps else None,
         'worst_run_max_us':max((c['max'] for c in chain),default=None),'worst_run_p99_us':max((c['p99'] for c in chain),default=None),
         'worst_longest_over_target_steps':max((c['longest'] for c in chain),default=None),'gate_met':gate_ok,'per_motor':motor_summary,
         'condition':'Tail latency depends on host load (batch mean CPU 22.5% vs 14.1%); evaluated across both instrumented batches.'}}
    final_results=load(PREP/'batch-05/results.json')
    out['validation_errors']=errors
    out['input_sha256']=input_hashes
    out['closure_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out['startup_audits_passed']=all(startup_ok(audit) for audit in audits.values())
    out['p0_complete']=not crashes and gate_ok and out['startup_audits_passed'] and all(audits[batch]['flights']['passed'] or batch=='batch-04' for batch in BATCHES) and final_results['status']=='PASS' and final_results['complete'] and final_results['candidate_unchanged'] and final_results['failed']==0 and final_results['not_run']==0
    out['p0_complete_note']='batch-04 stopped on the fixed-reference recovery criterion (since replaced, user-confirmed); its flights still count for crash, startup and output-chain evidence. Final verdict uses batch-05 as the complete frozen batch.'
    (ROOT/'data/p0-closure-20261012/acceptance.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:out[k] for k in ['p0_complete','validation_errors']},ensure_ascii=False));return 0 if out['p0_complete'] else 1
if __name__=='__main__':raise SystemExit(main())
