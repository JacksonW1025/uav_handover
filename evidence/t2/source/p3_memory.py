#!/usr/bin/env python3
"""RAPTOR GRU memory length in SITL from logged evidence; writes only p3-memory.json.

The frozen policy (Dense 22->16 ReLU, GRU 16, Dense 16->4; policy.tar of this run's build, hash-checked against
metadata) is replayed on the logged native-step inputs: raptor_input observation (position and velocity error, rotation
matrix of the relative orientation, angular velocity) and the previous action the rl_tools executor actually feeds
(action_history[0] = mean of the previous_action of all control calls since the last native step, research_memory).
Every replayed native step is first validated against the logged committed GRU (one step from the logged state).

Memory length on the same logged inputs: the GRU replayed from a different initial memory is compared with the GRU that
had the complete history (the logged one); reported is the number of native steps (and seconds) after which the
distance stays below the threshold for the rest of the horizon. Open-loop by construction (inputs fixed), so it measures
how long the memory itself persists, not the closed-loop consequence of a different memory.
"""
import argparse,hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_metrics import clean
ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/'uav_lab/.local/checkouts/px4-raptor/src/modules/mc_raptor/blob/policy.tar'
KIND_STEP,KIND_ENTRY,KIND_EXIT=1,2,3
HORIZON_STEPS=250

def load_policy(path=POLICY):
    data=path.read_bytes();tar=tarfile.open(fileobj=io.BytesIO(data))
    def t(name,shape):return np.frombuffer(tar.extractfile(f'actor/layers/{name}/parameters/data').read(),np.float32).reshape(shape).astype(np.float64)
    return {'sha256':hashlib.sha256(data).hexdigest(),'W0':t('0/weights',(16,22)),'b0':t('0/biases',(16,)),'Wi':t('1/weights_input',(48,16)),'bi':t('1/biases_input',(48,)),
            'Wh':t('1/weights_hidden',(48,16)),'bh':t('1/biases_hidden',(48,)),'W2':t('2/weights',(4,16)),'b2':t('2/biases',(4,)),
            'example':(np.frombuffer(tar.extractfile('example/input/data').read(),np.float32).reshape(500,2,22),np.frombuffer(tar.extractfile('example/output/data').read(),np.float32).reshape(500,2,4))}

def gru_step(P,h,x):
    """One native step; h (..,16), x (..,22). rl_tools GRU gate order r, z, n."""
    e=np.maximum(0,x@P['W0'].T+P['b0']);gi=e@P['Wi'].T+P['bi'];gh=h@P['Wh'].T+P['bh']
    sig=lambda v:1/(1+np.exp(-v))
    r=sig(gi[...,:16]+gh[...,:16]);z=sig(gi[...,16:32]+gh[...,16:32]);n=np.tanh(gi[...,32:]+r*gh[...,32:])
    return (1-z)*n+z*h

def example_check(P):
    X,Y=P['example'];h=np.zeros((2,16));err=0.
    for t in range(len(X)):h=gru_step(P,h,X[t].astype(np.float64));err=max(err,float(np.abs(h@P['W2'].T+P['b2']-Y[t]).max()))
    return err

def rotation(q):
    w,x,y,z=q
    return np.array([1-2*y*y-2*z*z,2*x*y-2*w*z,2*x*z+2*w*y,2*x*y+2*w*z,1-2*x*x-2*z*z,2*y*z-2*w*x,2*x*z-2*w*y,2*y*z+2*w*x,1-2*x*x-2*y*y])

def native_sequence(memory,inputs):
    """Native steps in log order: time, sample, active, teacher_forced, logged GRU, 22-dim policy input, and the memory
    written by a mode entry that happened since the previous native step (None otherwise)."""
    ri=inputs['timestamp_sample'].astype(np.int64);where={int(v):i for i,v in enumerate(ri)}
    mt=memory['timestamp'].astype(np.int64);kind=memory['kind'];acc=[];entry=None;out=[]
    for i in range(len(mt)):
        if kind[i]==KIND_ENTRY:acc=[];entry=np.array([memory[f'gru[{k}]'][i] for k in range(16)],float);continue
        if kind[i]!=KIND_STEP:continue
        acc.append([memory[f'previous_action[{k}]'][i] for k in range(4)])
        if not memory['native_step'][i]:continue
        j=where.get(int(memory['timestamp_sample'][i]))
        x=None;source=None
        if 'policy_input[0]' in memory:
            # Exact executor input logged with the inference (complete; raptor_input is latest-value and can miss rows).
            x=np.array([memory[f'policy_input[{k}]'][i] for k in range(22)],float);source='research_memory.policy_input'
            if np.max(np.abs(x[18:]-np.mean(acc,0)))>1e-6:source='research_memory.policy_input (action history differs from the previous-action mean)'
        elif j is not None:
            source='raptor_input'
            q=[inputs[f'orientation[{k}]'][j] for k in range(4)]
            x=np.r_[[inputs[f'position[{k}]'][j] for k in range(3)],rotation(q),[inputs[f'linear_velocity[{k}]'][j] for k in range(3)],
                    [inputs[f'angular_velocity[{k}]'][j] for k in range(3)],np.mean(acc,0)].astype(np.float32).astype(np.float64)
        out.append({'t':int(mt[i]),'active':bool(memory['active'][i]),'teacher_forced':bool(memory['teacher_forced'][i]),'source':source,
                    'gru':np.array([memory[f'gru[{k}]'][i] for k in range(16)],float),'x':x,'entry':entry,'calls':len(acc)})
        acc=[];entry=None
    return out

def validate(P,seq):
    errs=[];bad=0
    for a,b in zip(seq,seq[1:]):
        if b['x'] is None:bad+=1;continue
        h=b['entry'] if b['entry'] is not None else a['gru'];e=float(np.abs(gru_step(P,h,b['x'])-b['gru']).max());errs.append(e);b['valid']=e<1e-5
        bad+=e>=1e-5
    return {'native_steps':len(seq),'checked':len(errs),'max_abs_error':max(errs) if errs else None,'median_abs_error':float(np.median(errs)) if errs else None,
            'steps_over_1e-5':bad,'calls_per_native_step':sorted({s['calls'] for s in seq}),'input_sources':sorted({str(s['source']) for s in seq})}

def persistence(P,seq,i0,h0,threshold,horizon=HORIZON_STEPS,stop=None):
    """Replay from h0 at native index i0 on logged inputs; distance to the logged GRU per step; first step from which it
    stays below threshold until the horizon (or the segment end `stop`)."""
    end=min(len(seq),i0+horizon,stop if stop is not None else len(seq));h=np.array(h0,float);d=[]
    for k in range(i0,end):
        s=seq[k]
        if s['x'] is None or s['entry'] is not None and k>i0:break
        h=gru_step(P,h,s['x']);d.append(float(np.linalg.norm(h-s['gru'])))
    d=np.array(d);above=np.flatnonzero(d>=threshold)
    steps=None if not len(d) or (len(above) and above[-1]==len(d)-1) else (int(above[-1])+1 if len(above) else 0)
    return {'steps_compared':len(d),'initial_distance':float(np.linalg.norm(np.array(h0)-seq[i0-1]['gru'])) if i0>0 else None,
            'steps_to_stay_below':steps,'distance_curve':d[:60]}

def index_at(seq,t):return next((k for k,s in enumerate(seq) if s['t']>=t),None)

def analyze(run,P=None):
    run=Path(run).resolve();meta=json.loads((run/'metadata.json').read_text());cfg=json.loads((run/'config.json').read_text())
    P=P or load_policy();thr=cfg['p3']['memory_length']['threshold'];m3=json.loads((run/'p3-metrics.json').read_text())
    out={'run':str(run),'kind':meta['experiment_type'],'condition':cfg.get('p3_condition'),'treatment':cfg.get('p3_treatment'),'threshold':thr,
         'policy_sha256':P['sha256'],'policy_matches_run':P['sha256']==meta.get('policy_sha256'),'example_max_abs_error':example_check(P),'problems':[]}
    if not out['policy_matches_run']:out['problems'].append('policy differs from the run')
    if m3.get('p3_status')!='MEASURED':out['problems'].append('p3-metrics not MEASURED');return clean(out)
    u=ULog(str(run/'flight.ulg'),['research_memory','raptor_input']);t={d.name:d.data for d in u.data_list if d.multi_id==0}
    vs=next(d.data for d in ULog(str(run/'flight.ulg'),['vehicle_status']).data_list if d.name=='vehicle_status')
    armed=vs['timestamp'][vs['arming_state']==2].astype(np.int64)
    # Pre-arm state-contract operations (hold/inject/reset) write the memory outside inference: validate armed flight only.
    seq=[s for s in native_sequence(t['research_memory'],t['raptor_input']) if armed[0]<=s['t']<=armed[-1]];out['validation']=validate(P,seq)
    if out['validation']['steps_over_1e-5']:out['problems'].append('replay does not reproduce every logged native step')
    dt=np.median(np.diff([s['t'] for s in seq]))/1e6;out['native_period_s']=float(dt)
    ev=m3['events'];segments=[]
    def add(name,t_start,t_stop,inits,offsets):
        stop=index_at(seq,t_stop)
        for off in offsets:
            i0=index_at(seq,t_start+off*1e6)
            if i0 is None or stop is None or stop-i0<60:continue
            for label,h0 in inits(i0).items():
                r=persistence(P,seq,i0,h0,thr,stop=stop);r.update({'segment':name,'start_offset_s':off,'initial':label,
                    'seconds_to_stay_below':r['steps_to_stay_below']*dt if r['steps_to_stay_below'] is not None else None});segments.append(r)
    zero=lambda i0:{'zero (reset)':np.zeros(16)}
    # RAPTOR's own hover after the first entry (stationary external stream), open-loop replay of its inputs.
    t_c1=ev['first_C_to_N']['change_px4_us'];t_r2=(ev.get('N_to_C') or ev.get('baseline_recapture'))['trigger_px4_us']
    add('raptor_hover',t_c1,t_r2,zero,[1.5,2.5,3.5])
    if 'N_to_C' in ev:
        t_c2=ev['N_to_C']['change_px4_us'];t_c3=ev['second_C_to_N']['change_px4_us']
        exit_g=np.array(m3['exit']['gru'],float)
        name='teacher_forced_deactivation' if cfg['p3_treatment']=='N2' else 'shadow_deactivation'
        # From the N->C (logged GRU starts at the exit memory) and later restarts from zero.
        add(name,t_c2,t_c3,zero,[0.0]+([2.0,4.0,6.0] if cfg['p3_condition_spec']['deactivation_s']>=5 else []))
        # Second entry: counterfactual initial memories on the logged post-entry inputs (open loop).
        e2=m3['second_entry'];before=np.array(e2['gru_before'],float)
        inits=lambda i0:{'zero (N0)':np.zeros(16),'exit memory (N3)':exit_g,'shadow memory at entry (N2s/N2 GRU)':before}
        # First native step after the second entry (the entry row precedes the actuator owner change).
        i0=next((k for k,x in enumerate(seq) if x['entry'] is not None and x['t']>=t_c3-50000),None)
        if i0 is not None:
            for label,h0 in inits(i0).items():
                r=persistence(P,seq,i0,h0,thr,stop=index_at(seq,ev['second_C_to_N']['window_end_px4_us']));r.update({'segment':'second_entry_counterfactual','start_offset_s':0.0,'initial':label,
                    'logged_initial':e2['gru_written'],'seconds_to_stay_below':r['steps_to_stay_below']*dt if r['steps_to_stay_below'] is not None else None});segments.append(r)
    out['segments']=segments
    out['status']='MEASURED' if not out['problems'] else 'INCOMPLETE'
    return clean(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    r=analyze(a.run);(a.run/'p3-memory.json').write_text(json.dumps(r,indent=1,ensure_ascii=False,allow_nan=False)+'\n')
    print(r['status'],r['problems'],r.get('validation'));raise SystemExit(0 if r['status']=='MEASURED' else 1)
