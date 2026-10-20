#!/usr/bin/env python3
"""P7 conditions (pure functions of the rule in config/p7.json p7; used once to write the frozen condition specs into
config/p7.json p5.conditions, and by the tests to check that the frozen specs equal the rule).

All P7 runs are kind p5_gap (RAPTOR tracks a runner-published straight line through its external setpoint input; the
stream pauses and resumes on the same time-parameterized line), speed 2.0 m/s (C also 2.5), N2 memory.

Names:
  v<v>-D<D>-<A0|A45>             one interruption (A0 references; P6 B1 naming and the same generated profile)
  q4-D<D>-g<g>-<A0|A45>          A: 4 equal interruptions of D s with g s of setpoint stream between them
  r<NN>-A0                       B: random sequence NN of the pre-registered draw (p7.b)
  h-<one of the above>           C: the same interruption(s) with the long recovery hold (p7.c.hold_rule)
  h-M2-A45                       C4: P6 C2 pattern M2

Safety budget (P6 rule, unchanged): the runner's P5 path check (Experiment.p5_path_check: max(|start|,|end|) of the
line centred on RAPTOR's hover capture + 1.0 m braking allowance + interruption drift) at the spawn point plus the 0.1 m
hover-offset allowance <= 8 m. Shrink order A/B (P6): the cruise after the last resume (post_gap_s) 3.0 -> 2.0 s in
0.05 s steps, then the cruise before the first interruption (pre_gap_s) 1.0 -> 0.75 s; otherwise cancelled (never
flown). C: post_gap_s starts at 6.0 s (task: hold >= 6 s) and shrinks by the same rule; end_hold_s (stationary setpoints
at the line end) 6.0 s so the stream lasts >= 9 s after the last resume. Speeds and interruptions are never changed.
"""
import math,random,re
import p6_conditions
from p6_conditions import AXES,fmt,budget

SINGLE=re.compile(r'^v(?P<v>\d+(?:\.\d+)?)-D(?P<D>\d+(?:\.\d+)?)-(?P<axis>A0|A45)$')
SEQ4=re.compile(r'^q4-D(?P<D>\d+(?:\.\d+)?)-g(?P<g>\d+(?:\.\d+)?)-(?P<axis>A0|A45)$')

def single_name(v,D,axis):return f'v{fmt(v)}-D{fmt(D)}-{axis}'
def seq4_name(D,g,axis):return f'q4-D{fmt(D)}-g{fmt(g)}-{axis}'

def seq4_windows(D,g,n=4):
    """n equal interruptions [k(D+g), k(D+g)+D) in s after the first interruption start."""
    return [[round(k*(D+g),6),round(k*(D+g)+D,6)] for k in range(n)]

def fit(cfg,base,post0,pre0,post_min,pre_min,step):
    """P6 shrink order from (pre0, post0): post_gap_s down to post_min in `step` s steps, then pre_gap_s down to pre_min."""
    p5=cfg['p5']
    tries=[(pre0,round(post0-k*step,6)) for k in range(int(round((post0-post_min)/step))+1)]
    tries+=[(round(pre0-k*step,6),post_min) for k in range(1,int(round((pre0-pre_min)/step))+1)]
    for pre,post in tries:
        spec={**base,'pre_gap_s':pre,'post_gap_s':post};b=budget(cfg,p5,spec)
        if b['inside']:
            spec['safety_budget_m']=b;spec['shrunk']={'post_gap_s':post!=post0,'pre_gap_s':pre!=pre0};spec['cancelled']=None;return spec
    last={**base,'pre_gap_s':pre_min,'post_gap_s':post_min}
    return {**base,'cancelled':True,'cancel_reason':f'does not fit the safety budget with post_gap_s {post_min} s and pre_gap_s {pre_min} s','safety_budget_m':budget(cfg,p5,last)}

def base_spec(v,axis,gaps,description,hold=False,cfg=None):
    b={'speed_m_s':float(v),'motion_axis_ned':AXES[axis],'gaps':gaps,'flight_failures_are_results':True,'description':description}
    if hold:b['end_hold_s']=float(cfg['p7']['c']['hold_rule']['end_hold_s'])
    return b

def make(cfg,name):
    """Spec of a P7 condition name (fitted, possibly cancelled), or None."""
    r=cfg['p7']['budget_rule'];hold=name.startswith('h-');core=name[2:] if hold else name
    h=cfg['p7']['c']['hold_rule']
    post0=float(h['post_gap_start_s']) if hold else float(r['post_gap_start_s'])
    args=(post0,float(r['pre_gap_start_s']),float(r['post_gap_min_s']),float(r['pre_gap_min_s']),float(r['shrink_step_s']))
    m=SINGLE.match(core)
    if m:
        v,D,axis=float(m['v']),float(m['D']),m['axis']
        base=base_spec(v,axis,{'count':1,'duration_s':D,'recover_s':0.0},f"P7 single interruption D = {fmt(D)} s at {fmt(v)} m/s, {axis}"+(' (C hold rule)' if hold else ''),hold,cfg)
        return fit(cfg,base,*args)
    m=SEQ4.match(core)
    if m:
        D,g,axis=float(m['D']),float(m['g']),m['axis']
        base=base_spec(cfg['p7']['speed_m_s'],axis,{'windows_s':seq4_windows(D,g)},f"P7 4 x [interruption {fmt(D)} s, stream {fmt(g)} s], {axis}"+(' (C hold rule)' if hold else ''),hold,cfg)
        return fit(cfg,base,*args)
    pat,_,axis=core.rpartition('-')
    seqs=cfg['p7']['b'].get('sequences') or {}
    if pat in seqs and axis in AXES:
        s=seqs[pat];base=base_spec(cfg['p7']['speed_m_s'],axis,{'windows_s':[list(w) for w in s['windows_s']]},f"P7 B random sequence {pat}: {s['description']}, {axis}",hold,cfg)
        return fit(cfg,base,*args)
    pats=cfg['p7']['c'].get('patterns') or {}
    if pat in pats and axis in AXES:
        s=pats[pat];base=base_spec(cfg['p7']['speed_m_s'],axis,{'windows_s':[list(w) for w in s['windows_s']]},f"P7 C pattern {pat}: {s['description']}, {axis}"+(' (C hold rule)' if hold else ''),hold,cfg)
        return fit(cfg,base,*args)
    return None

# ---- B: random sequences --------------------------------------------------------------------------------------------
def draw_b(cfg):
    """Pre-registered draw (p7.b.draw): random.Random(seed); per sequence the count uniform in 2..5 (kept), then each
    interruption D uniform in [0.2, 0.6] s and each stream interval g uniform in [0.05, 4.6] s, rounded to 0.01 s; the
    lengths and intervals are redrawn when the fault budget is violated (last interruption must end <= 5.0 s after the first starts; total interruption <= 2.4 s;
    D in [0.2, 0.6], g >= 0.05 after rounding) or when the sequence does not fit the safety budget with the A/B shrink
    rule. Returns (sequences, counts of draws and rejections)."""
    d=cfg['p7']['b']['draw'];rng=random.Random(int(d['seed']));out={};stats={'draws':0,'rejected_fault_budget':0,'rejected_safety_budget':0}
    while len(out)<int(d['sequences']):
        n=rng.randint(int(d['count_min']),int(d['count_max']));name=f"r{len(out)+1:02d}"
        while True:
            stats['draws']+=1
            Ds=[round(rng.uniform(*d['duration_s']),2) for _ in range(n)];gs=[round(rng.uniform(*d['interval_s']),2) for _ in range(n-1)]
            w=[];t=0.
            for k in range(n):
                w.append([round(t,6),round(t+Ds[k],6)]);t=round(t+Ds[k]+(gs[k] if k<n-1 else 0.),6)
            ok=(all(d['duration_s'][0]-1e-9<=x<=d['duration_s'][1]+1e-9 for x in Ds) and all(x>=d['interval_s'][0]-1e-9 for x in gs)
                and sum(Ds)<=float(d['total_interruption_max_s'])+1e-9 and w[-1][1]<=float(d['window_s'])+1e-9)
            if not ok:stats['rejected_fault_budget']+=1;continue
            tmp={**cfg,'p7':{**cfg['p7'],'b':{**cfg['p7']['b'],'sequences':{name:{'windows_s':w,'description':''}}}}}
            if make(tmp,f'{name}-A0').get('cancelled'):stats['rejected_safety_budget']+=1;continue
            break
        out[name]={'windows_s':w,'durations_s':Ds,'intervals_s':gs,'count':n,'total_interruption_s':round(sum(Ds),6),'span_s':w[-1][1],
                   'description':f"{n} interruptions {'/'.join(fmt(x) for x in Ds)} s, stream {'/'.join(fmt(x) for x in gs)} s between",'draw_index':stats['draws']}
    return out,stats

# ---- condition lists ------------------------------------------------------------------------------------------------
def a_conditions(cfg):
    """(condition, treatment) of A: groups A1-A4 (q4 sequences) and the A0 single references."""
    a=cfg['p7']['a'];rows=[]
    for g in a['groups']:
        for D in g['durations_s']:
            for gap in a['intervals_s']:rows.append((seq4_name(D,gap,g['axis']),g['treatment'],g['name']))
    seen=set()
    for g in a['groups']:
        for D in g['durations_s']:
            k=(single_name(cfg['p7']['speed_m_s'],D,g['axis']),g['treatment'])
            if k not in seen:seen.add(k);rows.append((k[0],k[1],'A0'))
    return rows

def c_conditions(cfg):
    c=cfg['p7']['c'];rows=[]
    for g in c['groups']:
        for name in g['conditions']:rows.append((name,c['treatment'],g['name']))
    return rows

# ---- pre-registration: build config/p7.json ---------------------------------------------------------------------------
P7_RULES={
 'purpose':"P7 (task 2026-10-20): repeated interruptions, a random control under the same fault budget, and a rate-limited recovery in PX4. This harness implements, flies and exports only: no model fitting, no prediction, no classification (done by the project).",
 'speed_m_s':2.0,
 'memory':'N2 (MC_RAPTOR_RINI=4) in every run',
 'budget_rule':{'post_gap_start_s':3.0,'pre_gap_start_s':1.0,'post_gap_min_s':2.0,'pre_gap_min_s':0.75,'shrink_step_s':0.05,
   'rule':"P6 safety budget unchanged: the runner's P5 path check at the spawn point + 0.1 m hover-offset allowance <= 8 m (radius 10 m - 2 m margin); if it does not fit, post_gap_s (cruise after the last resume) shrinks 3.0 -> 2.0 s in 0.05 s steps, then pre_gap_s 1.0 -> 0.75 s; otherwise the condition is cancelled and never flown (speed, interruption lengths and intervals never change). Same profile as P6 B/C otherwise (hold 3 s, 1 s ramp, deceleration to rest at 2 m/s^2, end hold 3 s)."},
 'a':{'groups':[{'name':'A1','treatment':'T0','axis':'A0','durations_s':[0.3,0.38]},{'name':'A2','treatment':'T1a3','axis':'A0','durations_s':[0.45,0.6]},
                {'name':'A3','treatment':'T0','axis':'A45','durations_s':[0.3]},{'name':'A4','treatment':'T1a3','axis':'A45','durations_s':[0.45]}],
      'intervals_s':[0.05,0.1,0.15,0.25,0.5],'count':4,
      'references':"A0: each of the 6 (capture, axis, D) combinations once with a single interruption (same name and generated profile as P6 B1). A group is flown completely even when its single reference fails (task rule).",
      'order_seed':71020},
 'b':{'treatment':'T1a3','axis':'A0',
      'draw':{'seed':202610200,'sequences':12,'count_min':2,'count_max':5,'duration_s':[0.2,0.6],'interval_s':[0.05,4.6],'rounding_s':0.01,'total_interruption_max_s':2.4,'window_s':5.0,
              'rule':"random.Random(seed): per sequence first the count uniform in 2..5 (kept), then each interruption D uniform in [0.2, 0.6] s and each stream interval g between interruptions uniform in [0.05, 4.6] s (4.6 = the largest interval the 5 s window allows), rounded to 0.01 s; the lengths and intervals are redrawn (count kept) when the fault budget is violated after rounding (last interruption ends <= 5.0 s after the first one starts, total interruption <= 2.4 s, D in [0.2, 0.6], g >= 0.05) or when it does not fit the safety budget (budget_rule; the same rule would otherwise cancel it). Rejection sampling, so for each count the sequences are uniform over the fault-budget set intersected with the safety-budget set. The safety budget limits the span to about 3.1 s (8 m radius), so long-span sequences of the 5 s window cannot occur here; the rejection counts are recorded in draw_statistics. Written into this config and committed before any P7 flight; never changed afterwards."}},
 'c':{'treatment':'T1a3r2',
      'hold_rule':{'post_gap_start_s':6.0,'end_hold_s':6.0,
        'rule':"Task: the hold after the resume must allow the catch-up, at least 6 s; if the safety radius does not allow it, apply the P6 rule, else cancel. A 6 s cruise after the resume needs 12-15 m of line and fits no C condition, so post_gap_s starts at 6.0 s and shrinks by the P6 rule (0.05 s steps to 2.0 s, then pre_gap_s to 0.75 s), else cancelled. After the cruise the line decelerates to rest (2 m/s^2) and the stationary end hold is 6.0 s (instead of 3.0; no path change), so the setpoint stream lasts >= 9 s after the last resume (post_gap_s + v/2 + 6 s) and the 6 s lag window lies inside it. The rate-limited virtual target overshoots the line end by <= ~1 m in an offline kinematic check (vehicle assumed on its target), inside the 1.0 m braking allowance plus the 2 m margin to the 10 m envelope; recorded, not used for cancellation."},
      'patterns':{'M2':{'windows_s':[[0.0,0.4],[0.5,1.1],[1.3,1.8],[1.9,2.55]],'description':'P6 C2 M2: interruptions 0.4 / 0.6 / 0.5 / 0.65 s, restored 0.1 / 0.2 / 0.1 s between'}},
      'groups':[{'name':'C1','conditions':[f'h-v{fmt(v)}-D{fmt(D)}-A0' for v in [2.0,2.5] for D in [0.5,0.85,1.0,1.4,2.0]]},
                {'name':'C2','conditions':['h-v2.0-D0.85-A45','h-v2.0-D1.4-A45']},
                {'name':'C3','conditions':['h-q4-D0.6-g0.05-A0']},
                {'name':'C4','conditions':['h-q4-D0.45-g0.05-A45','h-M2-A45']}],
      'order_seed':81020},
 'recovery':{'parameter':'MC_RAPTOR_RREC','rate_m_s2':2.0,'omega_rad_s':1.5,'exit_position_m':0.02,'exit_velocity_m_s':0.02,'max_dt_s':0.05,
   'definition':"MC_RAPTOR_RREC (m/s^2, default 0 = original one-step jump back to the setpoint). With RREC > 0, in the RAPTOR cycle in which the external setpoint is fresh again after an in-flight setpoint-timeout capture while RAPTOR is active (not after the activation capture), a virtual target starts at the vehicle's horizontal position and velocity (the vehicle_local_position sample of that cycle, the state RAPTOR observes). Every RAPTOR cycle: acc = w^2 (sp_pos - vt_pos) + 2 w (sp_vel - vt_vel), w = 1.5, scaled to |acc| = RREC (horizontal norm) when larger; vt_vel += acc dt; vt_pos += vt_vel dt, dt from the gyro sample time of the cycle (<= 0.05 s); sp = the latest external setpoint RAPTOR read. The network observes the virtual target's horizontal position and velocity (vertical position/velocity and yaw from the setpoint). When the horizontal position and velocity differences are both < 0.02 after the update, the virtual target ends and the network observes the setpoint directly (same cycle). A new setpoint timeout during the recovery ends it; the original 200 ms timeout and capture rules (RTGT/RTDEC) apply. Equals R(a_r) of the project's l2f experiments (notes/target-interface/experiments/common.py, not present on this machine; implemented from the task text).",
   'implementation':"research/state/RecoveryTarget.hpp (unit test tests/recovery_target_test.cpp); tools/apply_research.py: research_recovery_transition() after the takeover-target step, the virtual target is swapped into _trajectory_setpoint only for the duration of observe() (RAII guard), evidence on uORB research_recovery (KIND_START / KIND_STEP every cycle / KIND_END with CONVERGED, STALE or INACTIVE). RREC = 0: no row, the observation code path is untouched."},
 'lag':{'window_s':6.0,'definition':"Per resume (first setpoint reception after an interruption): along-track lag = (original trajectory point - vehicle position) projected on the motion axis (positive = behind) and horizontal distance |trajectory - vehicle|, over [resume, resume + 6 s] (vehicle_local_position samples); maximum and the value at the window end. Original trajectory point at t = the latest logged trajectory_setpoint row at or before t advanced by its velocity (exact on the cruise and inside later interruptions; at rest after the stream end). A window cut by a later interruption is reported in full and marked; a window cut by the end of the record (abort) is truncated and marked."},
 'equivalence':{'groups':'p5_gap:v2.0-D0.4-A0:T0:2@config/p6.json,p5_gap:v2.0-D0.7-A0:T1a3:2@config/p6.json',
   'reference':{'v2.0-D0.4-A0:T0':'data/p6-20261019-b1-v2.0-D0.4-A0-T0-1','v2.0-D0.7-A0:T1a3':'data/p6-20261019-b1-v2.0-D0.7-A0-T1a3-1'},
   'max_tilt_tolerance_deg':2.5,
   'rule':"New candidate (MC_RAPTOR_RREC added, default 0): the P6 B1 cells T0 v2.0 D0.4 and T1a3 v2.0 D0.7, 2 runs each with config/p6.json and the frozen p6_metrics, new seeds. Equivalent when every run completes with sound infrastructure and evidence, its flight outcome equals the P6 B1 run (D0.4 T0 SUCCESS 40.1 deg, D0.7 T1a3 FAILURE 46.4 deg) and |max tilt - B1| <= 2.5 deg, and RREC = 0 is behaviourally identical to P6: no research_recovery row, MC_RAPTOR_RREC = 0 in the log, and every policy_input reconstructed with the P6 target rules (tools/p6_export.reconstruct) with 0 components > 1e-4. Otherwise NOT EQUIVALENT: write diagnosis.json. Pre-registered handling: P6 B3 showed that the T1a3 D0.7 cell flips between seeds (F 46.4, S 44.9, F 45.1); if the only differences are the outcome of that cell with its max tilt inside the P6 range +- 2.5 deg, the formal batches still run (the user is away) and the P7 results are conditional on the user accepting it; any other difference stops P7 for diagnosis."},
 'export':{'directory':'export','rule':"tools/p7_export.py: the P6 format (export/<run>/trace.csv.gz, summary.json; columns and reconstruction of tools/p6_export.py) plus trace columns vt_active, the target the network observed (tgt_p_u, tgt_p_w relative to the line centre, tgt_v_u, tgt_v_w), the original trajectory (traj_p_u, traj_v_u) and the vehicle position (p_u, p_w), and per run summary events capture / resume / recovery_end with times, catch-up duration, and per resume the maximum lag within 6 s and the lag at 6 s. During a recovery the reconstruction uses the research_recovery STEP row of the cycle (validated against policy_input like every other row)."},
 'host_rules':"As P6: jetson_clocks (verified from /sys), remote desktop disconnected (no ToDesk_Session), user-session processes on cores 0-3, PX4/Gazebo/Agent/runner pinned (p4.host.cpu_affinity), batches started through the session background mechanism, no commit while a batch runs.",
}

def build_config(p6):
    import copy
    cfg={k:copy.deepcopy(v) for k,v in p6.items() if k not in ['p6','p6_note','p5','p4']}
    cfg['p7_note']="P7 (2026-10-20): repeated interruptions (A), random sequences under the same fault budget (B), rate-limited recovery MC_RAPTOR_RREC (C). All runs kind p5_gap with explicit pre-registered conditions in p5.conditions (generated by tools/p7_conditions.py from p7.*); no model fitting or prediction here."
    p5=copy.deepcopy(p6['p5'])
    for k in ['condition_rule','c2_patterns','budget_table','equivalence']:p5.pop(k,None)
    p5['purpose']="P7 (kind p5_gap, P5 mechanism unchanged): RAPTOR tracks a runner-published straight line through its external trajectory_setpoint input; the runner stops publishing inside pre-registered windows and resumes on the same time-parameterized line. N2 memory (RINI=4). T0: zero-velocity in-flight timeout capture (RTGT=0); T1a3: speed-matched target at in-flight timeout captures (RTGT=2) with RTDEC 3.0; T1a3r2: T1a3 with the rate-limited recovery MC_RAPTOR_RREC = 2.0. Every P7 treatment sets MC_RAPTOR_RREC explicitly."
    p5['profile_overrides']=list(p5['profile_overrides'])+['end_hold_s']
    p5['treatments']={'T0':{'rini':4,'rtgt':0,'rtdec':2.0,'rrec':0.0,'description':'N2 memory; zero-velocity in-flight timeout capture (RTGT=0); no rate-limited recovery (RREC=0)'},
                      'T1a3':{'rini':4,'rtgt':2,'rtdec':3.0,'rrec':0.0,'description':'N2 memory; speed-matched target at in-flight timeout captures (RTGT=2), RTDEC 3.0; no rate-limited recovery (RREC=0)'},
                      'T1a3r2':{'rini':4,'rtgt':2,'rtdec':3.0,'rrec':2.0,'description':'as T1a3 with the rate-limited recovery MC_RAPTOR_RREC = 2.0 m/s^2'}}
    p5['planned_path_check']['rule']="P6 rule unchanged (P5 runner path check, drift term with 0.75 m/s^2) at the spawn point + 0.1 m hover-offset allowance <= 8 m; see p7.budget_rule."
    p5['conditions']={}
    cfg['p5']=p5;cfg['p7']=copy.deepcopy(P7_RULES)
    seqs,stats=draw_b(cfg);cfg['p7']['b']['sequences']=seqs;cfg['p7']['b']['draw_statistics']=stats
    rows=a_conditions(cfg)+[(f'{n}-A0',cfg['p7']['b']['treatment'],'B') for n in seqs]+c_conditions(cfg)
    budget_table={};cancelled=[];groups={}
    for cond,treat,grp in rows:
        spec=make(cfg,cond);budget_table[f'{cond}:{treat}']={'group':grp,'pre_gap_s':spec.get('pre_gap_s'),'post_gap_s':spec.get('post_gap_s'),'end_hold_s':spec.get('end_hold_s',p5['profile']['end_hold_s']),
            'cancelled':spec.get('cancelled'),'safety_budget_m':spec['safety_budget_m']}
        if spec.get('cancelled'):cancelled.append(f'{cond}:{treat}');continue
        p5['conditions'][cond]=spec;groups.setdefault(grp[0],[]).append(f'p5_gap:{cond}:{treat}:1')
    cfg['p7']['budget_table']=budget_table;cfg['p7']['cancelled']=cancelled
    p4=copy.deepcopy(p6['p4']);p4['purpose']='P7 batch bookkeeping (tools/p7_batch.py reuses the P4-P6 batch rules).'
    p4['independence']['master_seed']=20261020;p4['independence']['initial_yaw']['rule']='P7 draws no random heading: every run spawns at yaw 0 (PX4 heading 96.0 deg).'
    p4['independence']['default_settings']='Every P7 batch run (incl. the equivalence) gets its own Gazebo seed.'
    p4['dev_latency']={'rule':'Development batch on the candidate covering every new code path (A q4 sequence T0 A45 and T1a3 A0, a B random sequence, C single and multi-event with MC_RAPTOR_RREC 2, v2.5); every run with maximum applied-command age <= 8 ms under the frozen gate (P3-P6 rule). Development runs are never results.'}
    p4['groups']={'dev':'p5_gap:q4-D0.3-g0.05-A45:T0:1,p5_gap:q4-D0.6-g0.15-A0:T1a3:1,p5_gap:r01-A0:T1a3:1,p5_gap:h-v2.0-D1.0-A0:T1a3r2:1,p5_gap:h-M2-A45:T1a3r2:1,p5_gap:h-v2.5-D1.4-A0:T1a3r2:1',
                  'equivalence':cfg['p7']['equivalence']['groups'],'a':','.join(groups['A']),'b':','.join(groups['B']),'c':','.join(groups['C'])}
    cfg['p4']=p4
    return cfg

if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    ROOT=Path(__file__).resolve().parents[1]
    ap=argparse.ArgumentParser(description='Write config/p7.json (pre-registration) from config/p6.json and the P7 rules.');ap.add_argument('--write',action='store_true');a=ap.parse_args()
    cfg=build_config(json.loads((ROOT/'config/p6.json').read_text()))
    text=json.dumps(cfg,indent=1,ensure_ascii=False)+'\n'
    if a.write:
        out=ROOT/'config/p7.json'
        if out.exists():raise SystemExit('config/p7.json exists (frozen pre-registration); not overwritten')
        out.write_text(text)
    b=cfg['p7']['b'];print('B draw',b['draw_statistics'])
    for n,s in b['sequences'].items():print(n,s['description'],'span',s['span_s'],'post',cfg['p5']['conditions'][f'{n}-A0']['post_gap_s'],'pre',cfg['p5']['conditions'][f'{n}-A0']['pre_gap_s'])
    print('cancelled',cfg['p7']['cancelled'])
    for k in ['a','b','c']:print(k,len(cfg['p4']['groups'][k].split(',')))
    for c,s in cfg['p5']['conditions'].items():print(c,s['pre_gap_s'],s['post_gap_s'],s.get('end_hold_s'),s['safety_budget_m']['radius_m'],s['safety_budget_m']['interruption_drift_m'])
