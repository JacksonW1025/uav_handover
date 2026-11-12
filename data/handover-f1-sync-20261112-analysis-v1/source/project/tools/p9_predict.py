#!/usr/bin/env python3
"""P9 deterministic ex-ante event rollout, mismatch ledger and repair selection.

No learned vertical dynamics. Numerical tilt/cost forecasts for reset sequences
are extrapolations; ALL safety/skip decisions abstain until independently tested.
"""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from p9_model import G, ROOT, sha, write
from p9_plan import scan_windows

STEP=.008


def potential(e, kp):
    """Integral of kp*clip(e,+-.5), retaining unbounded position accumulation."""
    z=np.abs(e)
    return float(np.sum(kp*np.where(z<=.5,.5*z*z,.5*z-.125)))


def energy(e, dv, kp):
    return potential(e,kp)+float(.5*np.dot(dv,dv))


def capture_target(p0,v0,elapsed,rtgt,decel):
    if rtgt!=2:return p0.copy(),np.zeros(2)
    speed=float(np.linalg.norm(v0))
    if speed<1e-12:return p0.copy(),np.zeros(2)
    tau=min(max(elapsed,0.),speed/decel);direction=v0/speed
    return p0+direction*(speed*tau-.5*decel*tau*tau),direction*max(0.,speed-decel*tau)


def reference(t,v,decel_start):
    """Scalar ideal line, origin at the base first event. 3 s hold + 1 s ramp."""
    start=-1.5*v
    if t < -2:return start,0.
    if t < -1:return start+.5*v*(t+2)**2,v*(t+2)
    if t < decel_start:return v*t,v
    z=min(t-decel_start,v/2.)
    return v*decel_start+v*z-z*z,max(0.,v-2*z)


def forecast(model,case,params,keep_trace=False):
    dt=STEP;kp=np.array(model['kp']);kv=np.array(model['kv']);rho=math.exp(-dt/model['tau_s'])
    h=math.radians(case['heading_deg']);yaw=math.radians(96.)
    axis=np.array([math.cos(yaw)*math.cos(h)+math.sin(yaw)*math.sin(h),
                   math.sin(yaw)*math.cos(h)-math.cos(yaw)*math.sin(h)])
    speed=case['speed_m_s'];offset=case.get('pre_gap_s',1.)-1.
    win=[(a+offset,b+offset) for a,b in case['windows_s']]
    decel_start=offset+case['windows_s'][-1][1]+case.get('post_gap_s',2.)
    stream_end=decel_start+speed/2.+6.
    ts=np.round(np.arange(-5.,16.+dt/2,dt),9)
    p=axis*reference(-5.,speed,decel_start)[0];v=np.zeros(2);q=np.zeros(2)
    sp_p=p.copy();sp_v=v.copy();last_pub=-5.;pub_tick=-251;stale=False
    cap_p=p.copy();cap_v=v.copy();cap_t=-5.;vt_active=False;vtp=p.copy();vtv=v.copy()
    errors=[];mismatches=[];trace=[];events=[];jump_ledger=0.;vt_ends=[];delay=model['delay_s']/dt
    for k,t in enumerate(ts):
        tick=math.floor((t+1e-9)/.02)
        if tick>pub_tick:
            pub_tick=tick;pub_t=round(.02*tick,9)
            if pub_t<stream_end-1e-9 and not any(a-1e-9<=pub_t<b-1e-9 for a,b in win):
                s,sv=reference(pub_t,speed,decel_start);sp_p=axis*s;sp_v=axis*sv;last_pub=pub_t
        now_stale=t-last_pub>.2+1e-9
        event=None;old_target=None
        if now_stale and not stale:
            old_target=(sp_p.copy(),sp_v.copy());cap_p=p.copy();cap_v=v.copy();cap_t=t
            vt_active=False;event='capture'
        if not now_stale and stale:
            old_target=capture_target(cap_p,cap_v,t-cap_t,params['rtgt'],params['rtdec'])
            if params['rrec']>0:vt_active=True;vtp=p.copy();vtv=v.copy()
            event='resume'
        if now_stale:
            target,tv=capture_target(cap_p,cap_v,t-cap_t,params['rtgt'],params['rtdec'])
        elif vt_active:
            acc=2.25*(sp_p-vtp)+3.*(sp_v-vtv);n=float(np.linalg.norm(acc))
            if n>params['rrec']:acc*=params['rrec']/n
            step=0. if event=='resume' else dt
            vtv=vtv+acc*step;vtp=vtp+vtv*step
            if np.linalg.norm(sp_p-vtp)<.02 and np.linalg.norm(sp_v-vtv)<.02:
                vt_active=False;vt_ends.append(float(t));target,tv=sp_p,sp_v
            else:target,tv=vtp.copy(),vtv.copy()
        else:target,tv=sp_p,sp_v
        stale=now_stale;e=p-target;dv=v-tv;E=energy(e,dv,kp)
        if event:
            before=energy(p-old_target[0],v-old_target[1],kp)
            jump=E-before;jump_ledger+=max(0.,jump)
            events.append({'event':event,'t_s':float(t),'energy_before':before,'energy_after':E,'energy_jump':jump,
                           'position_error_m':float(np.linalg.norm(e)),'velocity_mismatch_m_s':float(np.linalg.norm(dv)),
                           'q_norm_m_s2':float(np.linalg.norm(q)),
                           'position_flu_m':p.tolist(),'velocity_flu_m_s':v.tolist(),'q_flu_m_s2':q.tolist(),
                           'target_position_flu_m':target.tolist(),'target_velocity_flu_m_s':tv.tolist(),
                           'delay_position_clipped_history_before_event':[x.tolist() for x in errors[-int(math.ceil(delay))-1:]],
                           'delay_velocity_clipped_history_before_event':[x.tolist() for x in mismatches[-int(math.ceil(delay))-1:]]})
        errors.append(np.clip(e,-.5,.5));mismatches.append(np.clip(dv,-1.,1.))
        j=max(0.,k-delay);lo=int(j);hi=min(k,lo+1);f=j-lo
        command=-kp*((1-f)*errors[lo]+f*errors[hi])-kv*((1-f)*mismatches[lo]+f*mismatches[hi])
        sr,vr=reference(t,speed,decel_start);rp=axis*sr;rv=axis*vr
        tilt=math.degrees(math.atan(float(np.linalg.norm(q))/G))
        # dE/dt identity: nominal dissipation + lag residual - dv dot target acceleration.
        nominal=-float(np.sum(kv*np.clip(dv,-1,1)*dv))
        residual=float(np.dot(dv,q+kp*np.clip(e,-.5,.5)+kv*np.clip(dv,-1,1)))
        trace.append([t,tilt,float(np.dot(rp-p,axis)),float(np.linalg.norm(rp-p)),float(np.linalg.norm(rv-v)),E,nominal,residual,
                      float(.5*model['tau_s']*np.dot(q,q))])
        q1=rho*q+(1-rho)*command;v1=v+.5*dt*(q+q1);p=p+.5*dt*(v+v1);v=v1;q=q1
    arr=np.array(trace);w=arr[:,0]>=0;pred=float(arr[w,1].max());band=model['error_rule']['empirical_peak_abs_band_deg']
    recover=[]
    for event in events:
        if event['event']!='resume' or event['t_s']<0:continue
        t=event['t_s'];a=arr[(arr[:,0]>=t)&(arr[:,0]<=t+6.+1e-9)]
        search=arr[(arr[:,0]>=t)&(arr[:,0]<=min(16.,t+10.)+1e-9)]
        settled=(search[:,3]<=.2)&(search[:,4]<=.1)
        dwell=int(math.ceil(.5/dt));caught=None
        for i in range(len(search)-dwell+1):
            if settled[i:i+dwell].all():caught=float(search[i,0]-t);break
        ends=[x for x in vt_ends if x>=t];next_capture=next((e['t_s'] for e in events if e['event']=='capture' and e['t_s']>t),16.)
        vt_end=next((x for x in ends if x<next_capture),None)
        recover.append({'resume_s':t,'max_lag_6s_m':float(a[:,2].max()),'lag_at_6s_m':float(a[-1,2]),
                        'window_6s_complete':bool(a[-1,0]>=t+6.-dt), 'vehicle_catch_up_10s_s':caught,
                        'vehicle_catch_up_censored':caught is None,'virtual_target_converged_s':None if vt_end is None else vt_end-t,
                        'next_event_s':next_capture-t})
    result={'model':model['name'],'point_tilt_deg':pred,'empirical_tilt_range_deg':[max(0.,pred-band),min(90.,pred+band)],
            'predicted_altitude_loss_m':None,'height_error_range_m':None,
            'tilt_only_screen_skip':False,'tilt_decision':'ABSTAIN_RESET_SEQUENCE_UNVALIDATED',
            'overall_skip':False,'overall_decision':'ABSTAIN_HEIGHT_UNMODELLED',
            'classification_for_sampling_only':'expected_low' if pred<35 else ('expected_critical' if pred<45 else 'expected_high'),
            'max_lag_m':float(arr[w,2].max()),'integrated_abs_lag_m_s':float(np.abs(arr[w,2]).sum()*dt),
            'max_energy':float(arr[w,5].max()),'positive_event_injection':jump_ledger,
            'nominal_plus_delay_proxy_positive_rows':int(((arr[w,6]+arr[w,7])>1e-6).sum()),
            'energy_derivative_limit':'proxy counter excludes target acceleration and sampled-position transport residual; not the full dE/dt or a Lyapunov certificate',
            'recoveries':recover,'events':events,'observation_window_s':[0.,16.],
            'clock':'8 ms controller, 20 ms publisher, strict >200 ms since last publication; no measured future state',
            'initial':'3 s rest hold, 1 s ramp, 1 s cruise; state and delay history propagated before first event',
            'assumptions':['yaw=96 degrees','no wind','vdot=q attitude-proxy; unmodelled thrust/drag/height',
                           'zero delivery jitter: actual reset/read times may differ; no validated timing envelope']}
    if keep_trace:result['trace']=arr.tolist()
    return result


def select_repair(model):
    """Only synthetic DEVELOPMENT probes: no B/C/D or reference argument exists."""
    probes=[{'speed_m_s':1.8,'heading_deg':h,'windows_s':scan_windows(d,.3)} for d in [.28,.48,.64] for h in [0.,45.]]
    comparisons=[]
    for rate in [1.,2.,3.]:
        preds=[forecast(model,c,{'rtgt':2,'rtdec':2.,'rrec':rate}) for c in probes]
        peak=max(x['point_tilt_deg'] for x in preds);lag=max(x['max_lag_m'] for x in preds)
        final=[x['recoveries'][-1] for x in preds];uncaught=sum(x['vehicle_catch_up_censored'] for x in final)
        within=sum(x['vehicle_catch_up_10s_s'] is None or x['vehicle_catch_up_10s_s']>10 or
                   not x['window_6s_complete'] or abs(x['lag_at_6s_m'])>.5 for x in final)
        comparisons.append({'rrec':rate,'max_point_tilt_deg':peak,'max_lag_m':lag,'unrecovered_probes':uncaught,
                            'task_cost_feasible':lag<=4.5 and within==0,
                            'rank':[int(lag>4.5)+within,peak,lag,rate]})
    best=min(comparisons,key=lambda x:x['rank'])
    return {'selected_rrec':best['rrec'],'comparisons':comparisons,'probes':probes,
            'rule':'min (cost violations + unrecovered count, maximum point tilt, maximum lag, rate); fixed candidates 1/2/3',
            'selection_claim':'comparative engineering candidate only; no height/overall-safety certification',
            'heldout_data_used':False,'all_cost_infeasible':not any(x['task_cost_feasible'] for x in comparisons)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('preparation',type=Path);p.add_argument('--design',default='design-v1')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    model=json.loads((a.preparation/'model.json').read_text());design=a.preparation/a.design
    cfg=json.loads((design/'config.json').read_text());plan=json.loads((design/'plan.json').read_text())
    selection=select_repair(model);rate=selection['selected_rrec']
    cfg['p5']['treatments']['P9-R']['rrec']=rate;cfg['p5']['treatments']['P9-CR']['rrec']=rate
    write(a.output/'repair-selection.json',selection)
    preds=[]
    for row in plan['runs']+plan['search_candidates']:
        params=cfg['p5']['treatments'][row['treatment']]
        preds.append({'id':row.get('id',row['condition']),'stage':row.get('stage','C-candidate'),
                      'family':row.get('family'),'phase_s':row.get('phase_s'),
                      'case':row['case'],'treatment':row['treatment'],'model_sha256':sha(a.preparation/'model.json'),
                      **forecast(model,row['case'],params)})
    write(a.output/'predictions.json',{'status':'DRAFT_PRE_FLIGHT','predictions':preds})
    write(a.output/'config-with-selected-repair.json',cfg)
    print('predictions',len(preds),'repair_rate',rate,'all safety decisions abstain')


if __name__=='__main__':main()
