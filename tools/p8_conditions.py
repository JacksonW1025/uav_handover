#!/usr/bin/env python3
"""P8 conditions (pure functions of config/p8.json; used by the runner for configs with a p8 section, by the batch tool
and by the tests). P6 / P7 condition code is imported, never changed.

A (identification, kind p6_ident, config p8.json p6.ident): RAPTOR follows a runner-published profile through its
external setpoint input; the stream never pauses.
  jump-v<v>-L<L>-<A0|A45>    hover -> 1 s linear ramp to v -> cruise pre_jump_s (1.0 s) -> the setpoint steps L ahead
                             along the motion axis (the same time-parameterized line shifted by L) -> cruise post_jump_s
                             -> deceleration at decel_m_s2 (2 m/s^2) to rest -> end hold (6 s)
  chase-x<x0>-V<V>-<A0|A45>  P6 chase family (p6_conditions, unchanged): the target appears x0 ahead and moves at V; once
                             the vehicle has caught up (runner DDS position, along-axis lag <= 0.2 m) or max_chase_s after
                             it appeared it decelerates at 1 m/s^2 to rest -> end hold (6 s)
Safety budget (P6 ident rule, p6_conditions.ident_budget unchanged in form): max(|start|,|end|) of the planned path centred
on RAPTOR's hover capture + 1.0 m braking allowance + 0.1 m hover-offset allowance <= 10 m - 2 m. If it does not fit,
jump: post_jump_s 3.0 -> 1.0 s in 0.1 s steps; chase: max_chase_s 4.0 -> 2.5 s in 0.1 s steps; otherwise the condition is
cancelled (never flown). v, L, x0 and V never change.
"""
import json,re
from pathlib import Path
import p6_conditions
from p6_conditions import AXES,fmt

ROOT=Path(__file__).resolve().parents[1]
JUMP=re.compile(r'^jump-v(?P<v>\d+(?:\.\d+)?)-L(?P<L>\d+(?:\.\d+)?)-(?P<axis>A0|A45)$')
CHASE=re.compile(r'^chase-x(?P<x>\d+(?:\.\d+)?)-V(?P<V>\d+(?:\.\d+)?)-(?P<axis>A0|A45)$')

def jump_name(v,L,axis):return f'jump-v{fmt(v)}-L{fmt(L)}-{axis}'
def chase_name(x0,V,axis):return f'chase-x{fmt(x0)}-V{fmt(V)}-{axis}'

# ---- identification profiles (same interface as p6_conditions.ident_*) -------------------------------------------
def ident_cfg(cfg,name):
    """Merged profile configuration of an identification condition (copy of p6_conditions.ident_cfg with the jump family)."""
    p6=cfg['p6']['ident'];spec=p6['conditions'][name];f=spec['family'];fam=p6['families'][f]
    p={**p6['profile'],**{k:v for k,v in fam.items() if k!='description'},**{k:v for k,v in spec.items() if k not in ['description','safety_budget_m','shrunk','cancelled','cancel_reason']}}
    p['motion_axis_ned']=AXES[spec['axis']]
    p['path_length_m']=ident_length(p);p['start_offset_m']=-round(p['path_length_m']/2,6)
    return p

def jump_time(p):
    """Family time of the setpoint jump (end of the ramp and of the pre-jump cruise)."""
    return float(p['accel_s'])+float(p['pre_jump_s'])

def ident_length(p):
    if p['family']!='jump':return p6_conditions.ident_length(p)
    v,L=float(p['speed_m_s']),float(p['jump_m'])
    return .5*v*float(p['accel_s'])+v*(float(p['pre_jump_s'])+float(p['post_jump_s']))+L+v*v/(2*float(p['decel_m_s2']))

def ident_motion(p,tau,switch=None):
    """(s from the start offset, v, a) along the axis at family time tau."""
    if p['family']!='jump':return p6_conditions.ident_motion(p,tau,switch)
    if tau<0:return 0.,0.,0.
    v,L,acc,pre,post,b=(float(p[k]) for k in ['speed_m_s','jump_m','accel_s','pre_jump_s','post_jump_s','decel_m_s2'])
    if tau<acc:return .5*v*tau*tau/acc,v*tau/acc,v/acc
    if tau<acc+pre:return .5*v*acc+v*(tau-acc),v,0.
    if tau<acc+pre+post:return .5*v*acc+v*(tau-acc)+L,v,0.
    r=min(tau-acc-pre-post,v/b);return .5*v*acc+v*(pre+post)+L+v*r-.5*b*r*r,v-b*r,(-b if tau-acc-pre-post<v/b else 0.)

def ident_motion_duration(p,switch=None):
    if p['family']!='jump':return p6_conditions.ident_motion_duration(p,switch)
    return float(p['accel_s'])+float(p['pre_jump_s'])+float(p['post_jump_s'])+float(p['speed_m_s'])/float(p['decel_m_s2'])

def ident_gap(p):
    return None if p['family']=='jump' else p6_conditions.ident_gap(p)

def ident_budget(cfg,name):
    """P6 ident budget rule (copy of p6_conditions.ident_budget using this module's ident_cfg)."""
    p=ident_cfg(cfg,name);c=cfg['p6']['ident']['planned_path_check'];L=p['path_length_m']
    half=max(abs(p['start_offset_m']),abs(p['start_offset_m']+L))
    radius=half+float(c['braking_allowance_m']);limit=cfg['safety_radius_m']-float(c['radius_margin_m'])
    allow=float(c['hover_offset_allowance_m'])
    return {'path_m':round(L,6),'radius_at_spawn_m':round(radius,6),'hover_offset_allowance_m':allow,'radius_m':round(radius+allow,6),'limit_m':limit,'inside':radius+allow<=limit+1e-9}

# ---- pre-registration of A ------------------------------------------------------------------------------------------
def a_base(name):
    m=JUMP.match(name)
    if m:return {'family':'jump','axis':m['axis'],'speed_m_s':float(m['v']),'jump_m':float(m['L'])}
    m=CHASE.match(name)
    if m:return {'family':'chase','axis':m['axis'],'x0_m':float(m['x']),'speed_m_s':float(m['V'])}
    raise ValueError(name)

def fit_a(cfg,name):
    """Spec of an A condition fitted into the safety budget by the P8 shrink rule (p8.a.budget_rule), or cancelled."""
    r=cfg['p8']['a']['budget_rule'];base=a_base(name);f=base['family'];key,start,low,step=(r[f]['key'],float(r[f]['start_s']),float(r[f]['min_s']),float(r['step_s']))
    n=int(round((start-low)/step))
    for k in range(n+1):
        val=round(start-k*step,6);spec={**base,key:val}
        probe={**cfg,'p6':{**cfg['p6'],'ident':{**cfg['p6']['ident'],'conditions':{name:spec}}}}
        b=ident_budget(probe,name)
        if b['inside']:return {**spec,'safety_budget_m':b,'shrunk':val!=start,'cancelled':None,'description':describe(spec)}
    spec={**base,key:low};probe={**cfg,'p6':{**cfg['p6'],'ident':{**cfg['p6']['ident'],'conditions':{name:spec}}}}
    return {**spec,'cancelled':True,'cancel_reason':f'does not fit the safety budget with {key} {low} s','safety_budget_m':ident_budget(probe,name),'description':describe(spec)}

def describe(s):
    if s['family']=='jump':
        return f"P8-A jump: 1 s ramp to {fmt(s['speed_m_s'])} m/s, 1 s cruise, setpoint steps {fmt(s['jump_m'])} m ahead, cruise {fmt(s['post_jump_s'])} s, 2 m/s^2 to rest, hold 6 s, {s['axis']}"
    return f"P8-A chase: target appears {fmt(s['x0_m'])} m ahead at {fmt(s['speed_m_s'])} m/s, decelerates at 1 m/s^2 after catch-up (<= 0.2 m) or {fmt(s['max_chase_s'])} s, hold 6 s, {s['axis']}"

def a_conditions(cfg):
    return {n:fit_a(cfg,n) for n in cfg['p8']['a']['names']}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='config/p8.json');p.add_argument('--write',action='store_true',help='write the fitted A specs into the config p6.ident.conditions (refuses to change existing specs)')
    a=p.parse_args();path=ROOT/a.config;cfg=json.loads(path.read_text());got=a_conditions(cfg)
    for n,s in got.items():print(n,'CANCELLED' if s.get('cancelled') else 'ok',{k:s.get(k) for k in ['post_jump_s','max_chase_s']},s['safety_budget_m']['radius_m'])
    if a.write:
        old=cfg['p6']['ident'].get('conditions') or {}
        if old and old!=got:raise SystemExit('config already holds different A specs; refusing to overwrite')
        cfg['p6']['ident']['conditions']=got;path.write_text(json.dumps(cfg,indent=1,ensure_ascii=False)+'\n')
if __name__=='__main__':main()

# ---- B: p5_gap cases of the frozen P8 test space (tools/p8/p8_space.py) ---------------------------------------------
# Runner condition name = p8_space.name(case, sut) without ':<sut>': v<v>-H<heading>-W<a>-<b>_<a>-<b>... (windows in s after
# the first interruption start). The spec is generated like p6_conditions.gap_spec (same base keys, same fit = P6
# condition_rule shrink order and budget) with motion axis [cos h, sin h, 0] (rounded to 9 decimals, h = 0 -> [1, 0, 0]).
# A single window (equivalence only) uses the P6 single-interruption form {'count': 1, 'duration_s': D, 'recover_s': 0}.
import math,sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'p8'))
import p8_space
CASE=re.compile(r'^v(?P<v>\d+(?:\.\d+)?)-H(?P<h>\d+(?:\.\d+)?)-W(?P<w>\d+(?:\.\d+)?-\d+(?:\.\d+)?(?:_\d+(?:\.\d+)?-\d+(?:\.\d+)?)*)$')

def axis_of(h):
    r=math.radians(float(h));return [round(math.cos(r),9)+0.,round(math.sin(r),9)+0.,0.0]

def case_condition(case,sut):
    n=p8_space.name(case,sut);return n[:-(len(sut)+1)]

def parse_case(name):
    m=CASE.match(name)
    if not m:return None
    w=[[float(a),float(b)] for a,b in (x.split('-') for x in m['w'].split('_'))]
    return float(m['v']),float(m['h']),w

def case_spec(cfg,name):
    """Generated p5_gap spec of a P8 case name (fitted by the P6 rule, possibly cancelled), or None."""
    p=parse_case(name)
    if p is None:return None
    v,h,w=p
    gaps={'count':1,'duration_s':w[0][1],'recover_s':0.0} if len(w)==1 and w[0][0]==0. else {'windows_s':w}
    base={'speed_m_s':v,'motion_axis_ned':axis_of(h),'gaps':gaps,'flight_failures_are_results':True,
          'description':f'P8-B case {name}: {len(w)} interruption(s) at {fmt(v)} m/s, heading {fmt(h)} deg (generated by p5.condition_rule)'}
    return p6_conditions.fit(cfg,cfg['p5'],base)

def budget_check(cfg,case,sut):
    """The task rule: p8_space.budget(case) must equal the gap_spec fit of the same case (pre_gap_s, post_gap_s or both
    None) and the windows must be the case's windows."""
    name=case_condition(case,sut);spec=case_spec(cfg,name);b=p8_space.budget(case)
    mine=None if spec.get('cancelled') else (spec['pre_gap_s'],spec['post_gap_s'])
    win=spec['gaps'].get('windows_s') or [[0.0,spec['gaps']['duration_s']]]
    ok=(mine==(None if b is None else tuple(b))) and win==p8_space.windows(case)
    return {'condition':name,'gap_spec':mine,'p8_space_budget':None if b is None else list(b),'windows_s':win,'equal':bool(ok),
            'safety_budget_m':spec.get('safety_budget_m')}
