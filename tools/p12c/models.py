#!/usr/bin/env python3
"""M3 declared-schedule closed-loop candidate. Real future records are not inputs.

Physical model is empirical P11 M2; clock/history/initial-filter interfaces are
explicit. Scenario envelopes are not certified coverage or a safety certificate.
"""
import numpy as np
from p11.models import assert_input,plant,tilt,speeds,reference
from p12.state import Controller
from p12.execution import step as motor_step


def forecast(doc,model,P,ablation=None):
    assert_input(doc)
    initial=doc['initial'];plan=doc['plan'];dt=.004
    for k in ['rotor_filter','call_index','force_sync','external_seen']:
        if k not in initial:raise ValueError('missing direct initial interface '+k)
    rot=np.array(initial['rotor_filter']);pending=np.array(initial['pending_command'])
    if rot.shape!=(4,) or not np.all(np.isfinite(rot)):raise ValueError('invalid filter state')
    p=np.array(initial['position']);v=np.array(initial['velocity']);q=np.array(initial['attitude']);omega=np.array(initial['omega'])
    lp=p.copy();lv=v.copy();att=q.copy();ctl=Controller(initial,plan['p12_repair'],plan['p12_phase'])
    t0=initial['profile_s'];sample=initial['sample_us'];native=initial['native_us'];last_send=-1e30
    n=int(np.ceil((plan['horizon_profile_s']-t0)/dt))+1
    schedule=plan['declared_schedule'];offsets={int(k):int(v) for k,v in schedule['native_offsets_us'].items()}
    current_offset=0;previous_native=native;table=np.asarray(plan['profile']['table'])
    rows=[];stop=None;native_trace=[]
    frozen_capture=np.array(initial['position']);frozen_velocity=np.array(initial['velocity'])
    for k in range(n):
        t=t0+k*dt;st=sample+4000*k
        current_offset=offsets.get(k,current_offset);now=native+4000*k+current_offset
        if ablation=='single_clock':now=st
        if now<previous_native:raise ValueError('declared native regression, not plateau')
        previous_native=now;native_trace.append(now)
        if k:
            effective=pending if ablation=='no_filter' else rot
            oldq=q.copy();p,v,q,omega,_=plant(p,v,q,omega,effective,model)
            rot=motor_step(rot,pending,dt)
            if (st-initial['lp_phase_us'])%8000==0:lp=p.copy();lv=v.copy()
            att=oldq
            inside=any(a<=t<b for a,b in plan['windows_profile_s'])
            msg=None
            if 0<=t<plan['stream_end_profile_s'] and not inside and t-last_send>=plan['publish_period_s']-1e-10:
                msg=reference(t,plan['profile'],table);last_send=t
            # Ablation deliberately replaces correlation at every capture, not a realizable intervention.
            cp,cv=(frozen_capture,frozen_velocity) if ablation=='uncorrelated_capture' else (lp,lv)
            if ablation=='uncorrelated_capture':
                original=ctl.target.step
                def changed(now,sample,p,v,q,message=None,activation=False):
                    return original(now,sample,cp,cv,q,message,activation)
                ctl.target.step=changed
            ctl.target.repair=plan['p12_repair'] and st>=plan.get('repair_not_before_sample_us',0)
            action,info=ctl.step(now,st,lp,lv,att,omega,msg,P,ablation)
            if ablation=='uncorrelated_capture':ctl.target.step=original
            if action is not None:pending=speeds(action)
        action=ctl.previous
        rows.append(np.r_[t,p,v,tilt(q),action,ctl.h,ctl.target.r,ctl.target.s,ctl.target.stale,q,omega,lp,lv,att])
        if not np.isfinite(rows[-1]).all():stop={'profile_s':t,'reason':'NUMERICAL_UNCERTAIN'};break
        if tilt(q)>45 or np.max(abs(omega))>8 or np.linalg.norm(p[:2])>10 or -p[2]>8:
            stop={'profile_s':t,'reason':'PREDICTED_ENVELOPE'};break
    return {'trace':np.array(rows),'native_us':np.array(native_trace),'stop':stop,
        'target_events':ctl.target.events,'kind':'M4','ablation':ablation,
        'status':'EMPIRICAL_DECLARED_SCHEDULE_CANDIDATE','certified_actual_coverage':False}
