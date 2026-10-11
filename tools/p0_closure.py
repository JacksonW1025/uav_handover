#!/usr/bin/env python3
"""Summarize post-fix preparation batches against the three open P0 items; never edits runs."""
import json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PREP=ROOT/'data/preparation-20261011'
# Lockstep fix is in batch-03 onward; output-chain trace in batch-04 onward.
BATCHES=['batch-03','batch-04','batch-05']
GATE={'p99_us':4000,'max_us':12000,'longest_over_target_steps':2,'overwritten_fraction':0.001,
      'basis':'Claude-proposed (user delegated): one physics step is the lockstep floor; 12 ms is below the 12.5 ms rotor rise time constant in the x500 SDF.'}
def load(p):return json.loads(p.read_text())
def upper95(n):return 3/n if n else None  # rule of three, zero events in n trials
def main():
    flights=starts=raptor=0;crashes=[];chain=[]
    for b in BATCHES:
        a=load(PREP/b/'batch-audit.json')
        for r in a['startups']['runs']:
            starts+=1
            if r['px4_exit_codes']!=[0] or r['crash_markers']:crashes.append(r['directory'])
        for r in a['flights']['runs']:
            flights+=1;raptor+=r['kind']!='classic_hover'
            if r['px4_exit_codes']!=[0] or r['crash_markers']:crashes.append(r['directory'])
            if 'output_chain' in r:
                oc=load(ROOT/r['directory']/'output-chain.json');m=oc['motors']['0']['neural']
                chain.append({'run':r['directory'],'p99':m['applied_age_us']['p99'],'max':m['applied_age_us']['max'],
                    'longest':m['longest_over_target_steps'],'steps':m['steps'],
                    'overwritten':m['commands_overwritten_in_gazebo']+(oc['px4_overwritten_publications']['neural_bracketed'] or 0)})
    steps=sum(c['steps'] for c in chain);over=sum(c['overwritten'] for c in chain)
    gate_ok=bool(chain) and all(c['p99']<=GATE['p99_us'] and c['max']<=GATE['max_us'] and c['longest']<=GATE['longest_over_target_steps'] for c in chain) and over/steps<GATE['overwritten_fraction']
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
         'worst_run_max_us':max(c['max'] for c in chain),'worst_run_p99_us':max(c['p99'] for c in chain),
         'worst_longest_over_target_steps':max(c['longest'] for c in chain),'gate_met':gate_ok,
         'condition':'Tail latency depends on host load (batch mean CPU 22.5% vs 14.1%); evaluated across both instrumented batches.'}}
    out['p0_complete']=not crashes and gate_ok and all(load(PREP/b/'batch-audit.json')['flights']['passed'] or b=='batch-04' for b in BATCHES) and load(PREP/'batch-05/results.json')['status']=='PASS'
    out['p0_complete_note']='batch-04 stopped on the fixed-reference recovery criterion (since replaced, user-confirmed); its flights still count for crash, startup and output-chain evidence. Final verdict uses batch-05 as the complete frozen batch.'
    (ROOT/'data/p0-closure-20261012/acceptance.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:out[k] for k in ['p0_complete']},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
