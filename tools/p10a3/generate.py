#!/usr/bin/env python3
"""Source-driven P10-A3 input and finite-prefix certificate attempt. Offline."""
import argparse
import gzip
import io
import json
import math
from pathlib import Path
import struct

import numpy as np
from source import ROOT, CFG, Oracle, runner, snapshot, sha, startup_observation, lift_attitude

SCALE=10**12
H=.004
EPOCH=100000000


def f32(x):return struct.unpack('!f',struct.pack('!f',x))[0]


class Adapter:
    """Independent proof-side guard/reset adapter for the selected RTGT0/RREC0.

    References come ONLY from actual runner messages, never an analytic copy.
    """
    def __init__(self):
        self.last_read=0;self.read_set=False;self.stale=False;self.previous_active=False
        self.armed=False;self.target=[0.,0.,0.,0.];self.last_sample=0
    def tick(self,row):
        us,sample,read,active,mode,rate,*data=row
        if mode!=0 or rate!=0:raise ValueError('adapter only covers actual selected RTGT0/RREC0')
        old=self.stale;cap=0
        if read and all(math.isfinite(x) for x in data[4:]):
            self.target=[f32(x) for x in data[4:8]];self.last_read=us;self.read_set=True
        self.stale=not self.read_set or us-self.last_read>200000
        activation=not self.previous_active and active
        if self.stale and (not old or activation):
            self.target=[f32(data[0]),0.,f32(data[2]),0.];cap=1
        if not active:self.armed=False
        elif self.stale:
            if activation:self.armed=False
            elif not old:self.armed=True
        elif old and self.armed:self.armed=False
        skipped=2 if not sample or sample<self.last_sample else (1 if sample==self.last_sample else 0)
        if not skipped:self.last_sample=sample
        self.previous_active=bool(active)
        return [int(self.stale),cap,0,skipped,self.last_read,int(self.armed),0]+self.target


def dump(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')


def generate(output, actual=False):
    output.mkdir(parents=True,exist_ok=False)
    startup=startup_observation() if actual else None
    if startup:dump(output/'startup-observation.json',startup)
    snap=snapshot();r,clock=runner(startup);cfg=r.cfg;params=cfg['p2_treatment_parameters']
    assert params['rtgt']==0 and params['rrec']==0 and cfg['p1_speed_m_s']==1.8
    dump(output/'source-snapshot.json',snap)
    dump(output/'source-config.json',{'path':str(CFG.relative_to(ROOT)),'sha256':sha(CFG),
         'speed':cfg['p1_speed_m_s'],'profile':r.pcfg,'parameters':params})
    model=json.loads((ROOT/'data/p9-20261024-freeze/model.json').read_text())
    kp=np.array(model['kp']);kv=np.array(model['kv']);rho=math.exp(-H/model['tau_s'])
    # Physical coordinates are fixed target-yaw FLU: f=x, l=-y at yaw0.
    axis=1 if actual else 0
    p=np.array(startup['relative_position_flu']) if actual else np.zeros(2)
    v=np.array(startup['velocity_flu']) if actual else np.zeros(2)
    q=np.array(startup['q_flu']) if actual else np.zeros(2)
    yaw=startup['origin_event']['yaw_rad'] if actual else 0.
    c,s=math.cos(yaw),math.sin(yaw)
    origin=np.array(startup['origin_event']['origin_ned_m'][:2]) if actual else np.zeros(2)
    def rotate(x):return np.array([c*x[0]+s*x[1],s*x[0]-c*x[1]])
    def body_ned(x):return origin+rotate(x)
    if actual:
        import importlib.util
        from scipy.linalg import solve_discrete_lyapunov
        spec=importlib.util.spec_from_file_location('retained_matrix_constructor',ROOT/'tools/p10r2/construct.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        a=m.matrix(kp[axis],kv[axis],rho)
        candidate=solve_discrete_lyapunov(a.T,np.eye(47));candidate=(candidate+candidate.T)/2
        dump(output/'matrix-candidate.json',{'P_integer':np.rint(candidate*10**10).astype(np.int64).tolist(),'axis':axis,
             'purpose':'candidate for actual-start lateral prefix after input/startup fixed; solver status is not proof'})
    g=np.zeros((47,2));g[0,0]=.01;g[2,1]=.1;g[3::2,0]=.01
    # No invented prehistory: empty buffer uses first available current e/d.
    hist=[];mismatch=[];g_hist=[]
    oracle=Oracle(snap,startup);adapter=Adapter();rows=[];mismatches=[];events=[]
    pre=[EPOCH-5000000,EPOCH-5000000,False,True,0,0.,origin[0],0.,origin[1],0.,0.,0.,0.,0.]
    if actual:pre+=startup['quaternion']
    activation_output=oracle.tick(pre);assert activation_output[:11]==adapter.tick(pre)
    pn=body_ned(p);vn=rotate(v)
    pre2=[EPOCH-4000,EPOCH-4000,False,True,0,0.,pn[0],vn[0],pn[1],vn[1],0.,0.,0.,0.]
    if actual:pre2+=startup['quaternion']
    native=oracle.tick(pre2);assert native[:11]==adapter.tick(pre2)
    dump(output/'prestream.json',{'activation':{'input':pre,'output':activation_output},
         'before_start_stream':{'input':pre2,'output':native},
         'scope':'module prelude from source activation; physical hover evolution before stream is an initial-state condition, not proxy history',
         'unknown_controller_states':'GRU/previous_action/motor/height/estimator influences not zeroed; must satisfy separate model error interface'})
    duration=r.profile_duration()+r.pcfg['end_hold_s'];stop=((round(duration*1e6)+3999)//4000)*4000
    end=stop+round(r.pcfg['post_stream_s']*1e6)
    windows=r.p5_gap_windows();first_gap=windows[0][0]
    # Prior activation captured the fixed origin, independent of the current
    # stream-start body uncertainty. Its carried target generator is zero.
    cap_g=np.zeros(2);latest_pub=None;old_stale=True
    for k,us in enumerate(range(0,end+1,4000)):
        clock.us=us;before=len(r.trajpub.messages)
        # One final callback belongs to native_bound_streaming before stop_stream.
        if us<=stop:r.stream()
        read=len(r.trajpub.messages)>before
        if read:
            msg=r.trajpub.messages[-1];latest_pub=us
            sp=[f32(msg.position[0]),f32(msg.velocity[0]),f32(msg.position[1]),f32(msg.velocity[1])]
        else:sp=[0.,0.,0.,0.]
        active=us<end
        pn=body_ned(p);vn=rotate(v)
        inp=[EPOCH+us,EPOCH+us,read,active,0,0.,pn[0],vn[0],pn[1],vn[1],*sp]
        if actual:inp+=startup['quaternion'] if k==0 else lift_attitude(q,yaw)
        native=oracle.tick(inp);pred=adapter.tick(inp)
        if native[:11]!=pred:mismatches.append({'us':us,'oracle':native,'adapter':pred})
        stale,cap,_,skipped,last,armed,tp,*target=native[:11]
        assert not skipped
        targetp=rotate(np.array([target[0],target[2]])-origin);targetv=rotate([target[1],target[3]])
        if cap or old_stale and not stale:
            events.append({'profile_us':us,'relative_gap_s':us/1e6-first_gap,
                'kind':'CAPTURE' if cap else 'RESUME','velocity':v.tolist(),'last_read':last-EPOCH})
        if cap:cap_g=g[0].copy()
        tg=cap_g.copy() if stale else np.zeros(2)
        if tg is None:tg=np.zeros(2)
        ge=g[0]-tg;gd=g[1].copy()
        ep=p-targetp;dv=v-targetv
        if k==0:
            # Earliest sample carries actual nonzero initial errors; no invented past.
            initial_e=float(ep[axis]);initial_d=float(dv[axis])
        rows.append({'profile_us':us,'input':inp,'oracle':native,'adapter':pred,'last_publish_us':latest_pub,
            'read_age_us':EPOCH+us-last,'p':p.tolist(),'v':v.tolist(),'q':q.tolist(),
            'target_flu':[*targetp,*targetv],'forward_generators':np.rint(g*SCALE).astype(np.int64).tolist(),
            'forward_error_generators':np.rint(np.stack([ge,gd])*SCALE).astype(np.int64).tolist(),
            'forward_error':[float(ep[axis]),float(dv[axis])],'certified_axis':axis,
            'native_target_yaw':native[11] if actual else 0.,
            'native_order':'read,guard,capture,target-step,recovery-transition,sample-accept',
            'queue_length_before':len(hist),'active':active})
        old_stale=bool(stale)
        if us==end:break
        hist.append(np.clip(ep,-.5,.5));mismatch.append(np.clip(dv,-1,1))
        g_hist.append(np.stack([ge,gd]))
        delayed=max(0,k-22)
        command=-kp*hist[delayed]-kv*mismatch[delayed]
        qn=rho*q+(1-rho)*command;vn=v+H/2*(q+qn);pn=p+H/2*(v+vn)
        # Full nominal always uses clip. Generators beyond first clipping are
        # retained as an invalid candidate, never accepted as a region proof.
        qg=rho*g[2]-(1-rho)*(kp[axis]*g_hist[delayed][0]+kv[axis]*g_hist[delayed][1])
        vg=g[1]+H/2*(g[2]+qg);pg=g[0]+H/2*(g[1]+vg)
        g=np.vstack([pg,vg,qg,np.stack([ge,gd]),g[3:-2]])
        g=np.rint(g*SCALE)/SCALE
        p=np.rint(pn*SCALE)/SCALE;v=np.rint(vn*SCALE)/SCALE;q=np.rint(qn*SCALE)/SCALE
    oracle.close()
    stream=io.BytesIO()
    with gzip.GzipFile(fileobj=stream,mode='wb',mtime=0) as f:
        for row in rows:f.write((json.dumps(row,separators=(',',':'),allow_nan=False)+'\n').encode())
    (output/'trace.jsonl.gz').write_bytes(stream.getvalue())
    (output/'native-oracle.cpp').write_text(oracle.source)
    # The old -5.002 s counterexample is evaluated through the same source method.
    tr=r.reposition(0.)[3];s,sv,_=r.p1_profile(tr-.002)
    dump(output/'source-ledger.json',{'schema':'p10-a3-source-driven-1','input_cfg_sha256':sha(CFG),
         'interval_profile_us':[0,end],'stream_stop_profile_us':stop,'planned_stream_duration_s':duration,
         'first_gap_profile_s':first_gap,'gap_windows_profile_s':windows,'events':events,
         'rows':len(rows),'oracle_adapter_mismatches':mismatches,'publisher_call_us':4000,
         'publisher_minimum_period_s':r.pcfg['setpoint_period_s'],
         'timing_scope':'source-allowed callback/read/gyro schedule; not every actual runner execution',
         'old_counterexample_probe':{'source_profile_time_s':tr-.002,'position_minus_endpoint':s-r.pcfg['start_offset_m'],'velocity':sv},
         'new_flights':0,'B_C_D_started':False})
    if actual:
        ledger=json.loads((output/'source-ledger.json').read_text())
        ledger['actual_start_binding']='startup-observation.json';ledger['certified_axis']=axis
        # This file is created once below via a distinct supplemental record.
        dump(output/'actual-binding.json',{'startup':'startup-observation.json','axis':axis,
             'first_delayed_error':[initial_e,initial_d],'constant_external_yaw':yaw,
             'source_values_not_translated_or_zeroed':True})
    init_spec={
        'source_start':'immediately before real start_stream after RAPTOR activation and neural hover; origin is earlier internal capture, not current body position',
        'source_initial_fields':{'active':True,'stale':True,'previous_active':True,'read_set':False,
            'recovery_active':False,'recovery_armed':False,'capture_mode':0,'internal_target':[0,0,-3]},
        'source_current_set':'p_f=.01*zp, v_f=0, q_f=.1*zq; |zp|,|zq|<=1; lateral state=0; finite source sensor inputs with yaw0',
        'nonempty_source_image':'center and nonzero representable position/small pure-pitch attitude values pass the actual source guard/reset code; native controller memory unconstrained by this syntax argument',
        'proxy_initial_buffer':'empty. At k<22 delayed index max(0,k-22) repeats the earliest acquired sample. Equivalent 47-state lift fills slots from FIRST actual e/d, not fictional body history',
        'lift_first_sample':'current p offset .01*zp and first actual source r=0 give every initial delayed position slot .01*zp; velocity slots0; q=.1*zq',
        'initial_residual_P_radius':'0; source quantized states within this set, no fictitious earlier tracking claim',
        'model_error_condition':'all unresolved GRU/action/motor/estimator/height effects enter current p,v,q residual; NOT assumed zero. A2 w_P<=1e-7 is tested against old data separately',
        'prestream_physical_reachability':'not a proof of actual controller producing all set members; a source-allowed declared sensor/module set and conditional proxy initialization',
    }
    if actual:
        init_spec['source_initial_fields']['internal_target']=startup['origin_event']['origin_ned_m']
        init_spec['source_current_set']='actual startup-observation center; lateral position offset +/- .01m and lateral q offset +/- .1; all other coordinates at recorded center; source-quantized members included'
        init_spec['nonempty_source_image']='actual recorded center from named local-position/attitude samples is a nonempty source observation; nearby finite lateral perturbations are source-allowed inputs, with future dynamics conditional on residual interface'
        init_spec['lift_first_sample']='all delay slots filled from first actual generated reference and declared body state, same two lateral generators; no fictional history'
        init_spec['initial_residual_P_radius']='1e-9 for exact initial frame/subtraction representation; independently checked'
        init_spec['prestream_physical_reachability']='recorded center exists; no assertion that every perturbed member is produced by the closed-loop controller or satisfies w<=1e-7'
    dump(output/'initialization.json',init_spec)
    dump(output/'manifest.json',{'files':{p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()},
         'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [CFG,ROOT/'tools/run_experiment.py',ROOT/'research/state/TargetProfile.hpp',ROOT/'research/state/RecoveryTarget.hpp',ROOT/'research/state/SampleClock.hpp']},'new_flights':0})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--actual',action='store_true')
    args=p.parse_args();generate(args.output,args.actual)
