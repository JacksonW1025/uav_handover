#!/usr/bin/env python3
"""Build/verify the P9 DRAFT. No flight, no implicit freeze, no old-file writes.

All scans move a middle interruption inside a fixed 2.6 s event span. Thus the
line, first/last event, pre/post cruise and observation horizon remain identical.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from p6_conditions import budget
from run_experiment import p5_profile
from p9_model import ROOT, write

VERSION = 'p9-plan-v2-draft'
SPEED = 1.8
SPAN = 2.6
GAPS = [.1,.25,.4,.55,.7]
CGRID = [round(.1+.05*i,2) for i in range(12)]
DOMAIN = {'speed_m_s':[1.5,2.0], 'heading_deg':[0.,90.], 'duration_s':[.2,.65],
          'restored_s':[.1,1.5], 'count':[1,4], 'span_max_s':2.6,
          'pre_gap_s':[1.,3.4], 'post_gap_s':[2.,4.4]}


def seed(name):
    return int.from_bytes(hashlib.sha256(('P9-v2-20261024|'+name).encode()).digest()[:4],'big') & 0x7fffffff


def windows(ds, gs):
    if len(gs)!=len(ds)-1:raise ValueError('interval count')
    t=0.;w=[]
    for i,d in enumerate(ds):
        w.append([round(t,8),round(t+d,8)])
        if i<len(gs):t=round(t+d+gs[i],8)
    return w


def scan_windows(d,g):
    return windows([d]*3,[g,SPAN-3*d-g])


def within_domain(case):
    """Validate EVERY dimension, independently of the runner safety budget."""
    def inside(x, key):
        lo,hi=DOMAIN[key];return math.isfinite(x) and lo-1e-9<=x<=hi+1e-9
    if set(case)-{'speed_m_s','heading_deg','windows_s','pre_gap_s','post_gap_s'}:return False
    w=case['windows_s']
    if not w:return False
    ds=[b-a for a,b in w];gs=[w[i+1][0]-w[i][1] for i in range(len(w)-1)]
    return bool(inside(case['speed_m_s'],'speed_m_s') and inside(case['heading_deg'],'heading_deg')
                and DOMAIN['count'][0]<=len(w)<=DOMAIN['count'][1] and abs(w[0][0])<1e-9
                and w[-1][1]<=DOMAIN['span_max_s']+1e-9
                and all(inside(x,'duration_s') for x in ds) and all(inside(x,'restored_s') for x in gs)
                and inside(case.get('pre_gap_s',1.),'pre_gap_s') and inside(case.get('post_gap_s',2.),'post_gap_s'))


def case_spec(cfg,case):
    if not within_domain(case):raise ValueError('P9 generation domain violation: '+str(case))
    if abs(case.get('pre_gap_s',1.)-1.+case['windows_s'][-1][1]+case.get('post_gap_s',2.)-(SPAN+2.))>1e-8:
        raise ValueError('P9 fixed deceleration phase / observation horizon mismatch')
    h=math.radians(case['heading_deg'])
    spec={'speed_m_s':case['speed_m_s'],'motion_axis_ned':[round(math.cos(h),9),round(math.sin(h),9),0.],
          'gaps':{'windows_s':case['windows_s']}, 'pre_gap_s':case.get('pre_gap_s',1.),
          'post_gap_s':case.get('post_gap_s',2.), 'flight_failures_are_results':True,
          'description':'P9-v1 fixed trajectory; explicit condition; no shrinking'}
    b=budget(cfg,cfg['p5'],spec)
    # A further .15 m numerical/hover margin, without changing any runner threshold.
    if not b['inside'] or b['radius_m']>b['limit_m']-.15:
        raise ValueError('P9 runner path budget violation: '+str(b))
    spec['safety_budget_m']=b
    return spec


def build():
    cfg=copy.deepcopy(json.loads((ROOT/'config/p7.json').read_text()))
    cfg['p5']['conditions']={}
    cfg['p5']['profile'].update(pre_gap_s=1.,post_gap_s=2.,end_hold_s=6.,post_stream_s=5.)
    cfg['p5']['profile_overrides']=sorted(set(cfg['p5']['profile_overrides']+['pre_gap_s','post_gap_s','end_hold_s']))
    cfg['p9']={'status':'DRAFT_NOT_FLIGHT_AUTHORITY','version':VERSION, 'domain':DOMAIN,
               'budget':{'development_cap':12,'formal_cap':180,'B':48,'C_search':60,'C_reference':36,'D':36},
               'fixed_horizon_s':16.,'fixed_event_span_s':SPAN,'first_to_last_resumes':'fixed; only middle event phase varies',
               'height':'unmodelled: overall safety always ABSTAIN',
               'formal_freeze':None}
    cfg['p4']['independence']['master_seed']=202610249
    base={'rini':4,'rtgt':0,'rtdec':2.,'rrec':0.,'description':'P9 original capture; one-step resume'}
    cfg['p5']['treatments']={'P9-Z':base,'P9-C':dict(base,rtgt=2,description='P9 capture-only, RTDEC 2'),
                           'P9-R':dict(base,rrec=2.,description='P9 recovery-only; rate chosen on development model before freeze'),
                           'P9-CR':dict(base,rtgt=2,rrec=2.,description='P9 combination; same rate as recovery-only')}
    rows=[];candidates=[]
    def add(stage,name,case,treatment,sim_seed=None,**extra):
        spec=case_spec(cfg,case);condition='p9-'+name
        if condition in cfg['p5']['conditions'] and cfg['p5']['conditions'][condition]!=spec:raise ValueError('condition collision')
        cfg['p5']['conditions'][condition]=spec
        row={'id':name+'-'+treatment,'stage':stage,'kind':'p5_gap','condition':condition,'case':case,'treatment':treatment,
             'sim_seed':seed(stage+'/'+name+'/'+treatment) if sim_seed is None else sim_seed,
             'initial_yaw_deg':0.,'status':'NOT_RUN','fixed_window_from_base_first_gap_s':[0.,16.],**extra}
        rows.append(row);return row
    for sut,d in [('P9-Z',.36),('P9-C',.58)]:
        for h in [15.,45.,75.]:
            for g in GAPS:
                case={'speed_m_s':SPEED,'heading_deg':h,'windows_s':scan_windows(d,g)}
                add('B',f'B-{sut}-h{h:g}-g{g:g}',case,sut,group='phase_scan',phase_s=g)
            case={'speed_m_s':SPEED,'heading_deg':h,'windows_s':scan_windows(d,.4)}
            add('B',f'B-{sut}-h{h:g}-g0.4-repeat',case,sut,group='seed_repeat',phase_s=.4)
            if h in [15.,75.]:
                for j,(a,b) in enumerate(case['windows_s']):
                    single={'speed_m_s':SPEED,'heading_deg':h,'windows_s':[[0.,round(b-a,8)]],
                            'pre_gap_s':1.+a,'post_gap_s':2.+SPAN-b}
                    add('B',f'B-{sut}-h{h:g}-single{j+1}',single,sut,group='single_event_control',
                        compared_to=f'B-{sut}-h{h:g}-g0.4-{sut}',event_index=j,base_first_gap_offset_s=-a)
    families=[('CZ15','P9-Z',15.,.40),('CZ60','P9-Z',60.,.36),('CC30','P9-C',30.,.61)]
    for fam,treatment,h,d in families:
        for g in CGRID:
            case={'speed_m_s':SPEED,'heading_deg':h,'windows_s':scan_windows(d,g)}
            spec=case_spec(cfg,case);name=f'C-{fam}-g{g:g}'
            cfg['p5']['conditions']['p9-'+name]=spec
            candidates.append({'family':fam,'phase_s':g,'condition':'p9-'+name,'case':case,'treatment':treatment})
            add('C-reference',name+'-reference',case,treatment,family=fam,phase_s=g,
                information_boundary='execute only after both searches sealed; no reference feedback to searches')
    # Ten slots per method/family, consumed only if a pre-registered stop rule does not stop earlier.
    slots=[]
    for fam,treatment,_,_ in families:
        for method in ['ledger','replay']:
            for k in range(10):
                name=f'C-{fam}-{method}-q{k+1:02d}'
                slots.append({'id':name,'stage':'C-search','family':fam,'method':method,'query':k+1,
                              'sim_seed':seed(name),'treatment':treatment,'status':'UNPROPOSED',
                              'information_boundary':'own history + frozen model/candidate data only'})
    heldout=[([.28,.48,.36],[.38,.90]),([.42,.32,.46],[.58,.62]),([.58,.24,.38],[.26,.94]),
             ([.36,.62,.28],[.54,.60]),([.24,.36,.42,.30],[.22,.26,.60]),
             ([.46,.26,.38,.32],[.18,.36,.44]),([.62,.52],[1.26]),
             ([.46,.64],[1.30]),([.30,.40,.32,.28],[.40,.24,.46])]
    for k,(ds,gs) in enumerate(heldout):
        gs=list(gs);gs[-1]=round(gs[-1]+.2,8)
        case={'speed_m_s':SPEED,'heading_deg':[20.,50.,80.][k%3],'windows_s':windows(ds,gs)}
        if abs(case['windows_s'][-1][1]-SPAN)>1e-8:raise ValueError('D span not fixed')
        for arm in cfg['p5']['treatments']:
            add('D',f'D-{k+1:02d}',case,arm,sim_seed=seed(f'D-paired-{k+1}'),cluster=f'D-{k+1:02d}',
                information_boundary='heldout sequences unavailable to repair selection; four factorial arms share seed')
    # Development 6 technical checks + 4 equivalence + 2 reserved infrastructure slots = cap12.
    dev=[]
    for i,arm in enumerate(['P9-Z','P9-C','P9-R','P9-CR']):
        c={'speed_m_s':SPEED,'heading_deg':[15.,45.,75.,45.][i],'windows_s':scan_windows(.36,.3)}
        spec=case_spec(cfg,c);n=f'p9-dev-arm-{i+1}';cfg['p5']['conditions'][n]=spec
        dev.append({'id':n,'condition':n,'treatment':arm,'kind':'p5_gap','sim_seed':seed(n),'status':'NOT_RUN'})
    for i in [0,1]:
        c={'speed_m_s':SPEED,'heading_deg':60.,'windows_s':scan_windows(.32,.4)}
        n=f'p9-dev-clock-{i+1}';cfg['p5']['conditions'][n]=case_spec(cfg,c)
        dev.append({'id':n,'condition':n,'treatment':'P9-Z','kind':'p5_gap','sim_seed':seed(n),'status':'NOT_RUN'})
    for i,(condition,treatment) in enumerate([('v2.0-D0.3-A0','T0'),('v2.0-D0.3-A0','T0'),
                                             ('v2.0-D0.5-A0','T1a3'),('v2.0-D0.5-A0','T1a3')]):
        dev.append({'id':f'p9-equivalence-{i+1}','condition':condition,'treatment':treatment,'kind':'p5_gap',
                    'config':'config/p6.json','sim_seed':seed(f'p9-equivalence-{i+1}'),'status':'NOT_RUN'})
    plan={'version':VERSION,'status':'DRAFT_PENDING_SITL_DEVELOPMENT_AND_EQUIVALENCE','budget':cfg['p9']['budget'],
          'runs':rows,'search_slots':slots,'search_candidates':candidates,'development':dev,'development_reserve_slots':2,
          'stop_precision_s':.05,'max_search_queries_per_method_family':10,
          'reference_definition':'12-point independent noisy empirical grid per family; not ground-truth probability boundary',
          'leakage_rule':'No B/D/reference result accessible to a search; no formal result used for refitting or repair choice'}
    counts={s:sum(r['stage']==s for r in rows) for s in ['B','C-reference','D']}
    if counts!={'B':48,'C-reference':36,'D':36} or len(slots)!=60:raise ValueError(counts)
    # All formal cases use the identical line: single controls just remove other interruptions in time.
    paths=[]
    for r in rows:
        p=p5_profile(cfg['p5'],cfg['p5']['conditions'][r['condition']]);paths.append(p['path_length_m'])
    if max(paths)-min(paths)>1e-8:raise ValueError('trajectory changes across controlled comparisons')
    plan['audit']={'counts':dict(counts,**{'C-search':len(slots)}),'formal_max':len(rows)+len(slots),
                   'domain_checked':len(cfg['p5']['conditions']),'path_length_range_m':[min(paths),max(paths)],
                   'pre_main_s':1.,'post_main_s':2.,'common_horizon_s':16.,'end_hold_s':6.,'shrink_allowed':False,
                   'D_independent_sequence_clusters':9,'D_runs':36}
    return cfg,plan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise SystemExit('output exists; preserve old draft')
    a.output.mkdir(parents=True);cfg,plan=build();write(a.output/'config.json',cfg);write(a.output/'plan.json',plan)
    print(json.dumps(plan['audit'],indent=2))


if __name__=='__main__':main()
