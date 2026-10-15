import sys,json,math
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from run_experiment import Experiment
from p3_batch import parse_groups,build_plan
import p3_memory

CFG=json.loads((ROOT/'config/p3.json').read_text())

def test_p3_thresholds_equal_frozen_p1_p2():
    p1=json.loads((ROOT/'config/p1.json').read_text());p2=json.loads((ROOT/'config/p2.json').read_text())
    for k in ['joint_recovery','hover_max_error_m','hover_max_tilt_deg','safety_radius_m','safety_altitude_m','safety_tilt_deg','safety_angular_rate_rad_s','inference_p99_us','seed','altitude_m','hover_s']:
        assert CFG[k]==p1[k]==p2[k],k
    assert CFG['p3']['motor_saturation']==p2['p2']['motor_saturation'] and CFG['p3']['flight_failures']['criteria']==p2['p2']['exploration']['failure_criteria']
    assert CFG['short_stage_rule']['exempt_below_dwell'] and 'short_stage_rule' not in p1 and 'short_stage_rule' not in p2
    assert {n:t['rini'] for n,t in CFG['p3']['treatments'].items()}=={'N0':0,'N3':6,'N2s':1,'N2':4,'B':0}
    # Only D1 is shorter than the joint-recovery dwell.
    short=[c for c,s in CFG['p3']['conditions'].items() if s['deactivation_s']<CFG['joint_recovery']['dwell_s']]
    assert short==['D1'] and CFG['p3']['conditions']['D1']['deactivation_s']==0.3

def motion(cond):
    return SimpleNamespace(cfg={'p3_condition_spec':CFG['p3']['conditions'][cond]})

def test_d3_motion_translates_3m_and_turns_90deg_then_holds():
    e=motion('D3');f=lambda t:Experiment.p3_motion(e,t)
    assert f(0.5)==(0.,0.,0.,0.,0.)
    s,v,a,dy,rate=f(1.0+4.0+0.01);assert abs(s-3.0)<1e-9 and v==0 and abs(math.degrees(dy)-90)<1e-9 and rate==0
    s,v,a,dy,rate=f(3.0);assert abs(s-1.5)<1e-9 and abs(v-1.0)<1e-9 and abs(math.degrees(dy)-45)<1e-9
    ts=np.linspace(0,10,2001);path=[f(t) for t in ts]
    assert all(b[0]>=a[0]-1e-12 for a,b in zip(path,path[1:])) and max(p[1] for p in path)<=1.0+1e-12 and max(abs(p[2]) for p in path)<=1.0+1e-12
    end=Experiment.p3_motion_end(e,[0.1,-0.2,-3.0]);assert np.allclose(end,[0.1,2.8,-3.0])
    assert math.hypot(*end[:2])<CFG['safety_radius_m']-CFG['p3']['safety_check']['radius_margin_m']
    assert Experiment.p3_motion(motion('D2'),3.0)==(0.,0.,0.,0.,0.) and Experiment.p3_motion_end(motion('D1'),[1.,2.,3.])==[1.,2.,3.]

def test_plan_interleaves_conditions_treatments_and_baseline():
    g=parse_groups(','.join(f'p3_sequence:{c}:{t}:3' for c in ['D1','D2','D3'] for t in ['N0','N3','N2s','N2'])+',p3_baseline_raptor:R:B:3')
    plan=build_plan('p3-x',g,'config/p3.json')
    assert len(plan)==39 and len({r['directory'] for r in plan})==39
    assert [r['id'] for r in plan[:13]]==[f'{c}-{t}-1' for c in ['D1','D2','D3'] for t in ['N0','N3','N2s','N2']]+['R-B-1']
    assert plan[13]['id']=='D1-N0-2' and plan[-1]['id']=='R-B-3' and plan[-1]['kind']=='p3_baseline_raptor'

def test_policy_replica_reproduces_checkpoint_example():
    P=p3_memory.load_policy();assert p3_memory.example_check(P)<1e-5

def synthetic_memory(rows):
    keys=['timestamp','timestamp_sample','kind','native_step','active','teacher_forced']+[f'gru[{k}]' for k in range(16)]+[f'previous_action[{k}]' for k in range(4)]
    d={k:np.array([r.get(k.split('[')[0],0) if '[' not in k else r[k.split('[')[0]][int(k.split('[')[1][:-1])] for r in rows]) for k in keys}
    return d

def test_native_inputs_average_previous_actions_and_reset_at_entry():
    g=np.zeros(16);rows=[]
    def step(t,native,pa,kind=1):rows.append({'timestamp':t,'timestamp_sample':t,'kind':kind,'native_step':native,'active':1,'teacher_forced':0,'gru':g,'previous_action':pa})
    step(1,0,[0.,0.,0.,0.]);step(2,1,[1.,1.,1.,1.])           # native after two calls: mean 0.5
    step(3,0,[.2,.2,.2,.2],kind=2)                             # mode entry: executor history restarts
    step(4,1,[.3,.3,.3,.3])                                    # first native after entry: only its own call
    mem=synthetic_memory(rows);inputs={'timestamp_sample':np.array([1,2,4]),**{f'{n}[{k}]':np.zeros(3) for n,c in [('position',3),('linear_velocity',3),('angular_velocity',3)] for k in range(c)},
                                       **{f'orientation[{k}]':np.array([1.,1.,1.]) if k==0 else np.zeros(3) for k in range(4)}}
    seq=p3_memory.native_sequence(mem,inputs)
    assert [s['calls'] for s in seq]==[2,1] and np.allclose(seq[0]['x'][18:],.5) and np.allclose(seq[1]['x'][18:],.3) and seq[1]['entry'] is not None
    assert np.allclose(seq[0]['x'][3:12],[1,0,0,0,1,0,0,0,1])

def test_persistence_counts_steps_until_distance_stays_below():
    P=p3_memory.load_policy();rng=np.random.default_rng(0);xs=rng.normal(0,.3,(120,22));h=np.zeros(16);seq=[]
    for x in xs:h=p3_memory.gru_step(P,h,x);seq.append({'x':x,'gru':h.copy(),'entry':None})
    same=p3_memory.persistence(P,seq,10,seq[9]['gru'],0.05);assert same['steps_to_stay_below']==0
    far=p3_memory.persistence(P,seq,10,np.full(16,.9),0.05);assert far['steps_to_stay_below'] is not None and far['steps_to_stay_below']>0
    assert far['distance_curve'][0]>0.05 and far['distance_curve'][far['steps_to_stay_below']]<0.05
