"""Post-flight descriptive supplement; new outputs only, never starts simulation."""
import argparse,csv,gzip,hashlib,json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from analyze import clean
from output_chain import read_trace


def main(run,out):
    out.mkdir(parents=True,exist_ok=False)
    u=ULog(str(run/'flight.ulg'));d={q.name:q.data for q in u.data_list if q.multi_id==0}
    m=json.loads((run/'cn-measurement.json').read_text());events=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()]
    sends=[json.loads(s) for s in (run/'cn-setpoints.jsonl').read_text().splitlines()]
    entry=m['native_timeline']['native_nav_entry_us'];p=d['research_p11'];active=p['active'].astype(bool);native=active&p['native_step'].astype(bool)
    t=p['timestamp'][native];rel=(t.astype(np.int64)-entry)/1e6
    pos=np.array([p[f'position[{i}]'][native] for i in range(3)]).T;target=np.array([p[f'network_target_position[{i}]'][native] for i in range(3)]).T
    vel=np.array([p[f'velocity[{i}]'][native] for i in range(3)]).T;vtarget=np.array([p[f'network_target_velocity[{i}]'][native] for i in range(3)]).T
    mot=d['actuator_motors'];mi=np.clip(np.searchsorted(mot['timestamp'],t,side='right')-1,0,len(mot['timestamp'])-1)
    motors=np.array([mot[f'control[{i}]'][mi] for i in range(4)]).T
    att=d['vehicle_attitude'];ai=np.clip(np.searchsorted(att['timestamp'],t,side='right')-1,0,len(att['timestamp'])-1)
    tilt=np.degrees(np.arccos(np.clip(1-2*(att['q[1]'][ai]**2+att['q[2]'][ai]**2),-1,1)))
    first=int(np.flatnonzero(active)[0]);firstread=int(np.flatnonzero(active&p['external_valid'].astype(bool))[0])
    event=next(x for x in events if x['event']=='cn_first_external_publish')
    modeevent=next(x for x in events if x['event']=='mode_confirmed' and x['mode']==m['raptor_mode_id'])
    send0=sends[0]
    signature_ok=all(np.float32(send0['position'][j])==p[f'external_position[{j}]'][firstread] for j in range(3)) and all(np.float32(send0['velocity'][j])==p[f'external_velocity[{j}]'][firstread] for j in range(3))
    switches=np.flatnonzero(np.diff(p['stale'].astype(np.int64))!=0)+1
    edges=[{'native_us':int(p['timestamp'][i]),'stale':bool(p['stale'][i]),'last_valid_read_us':int(p['last_valid_read_us'][i])} for i in switches if active[i] or active[i-1]]
    gapstart=next(i for i in switches if active[i] and p['stale'][i] and p['timestamp'][i]>entry+1e6)
    gapend=next(i for i in switches if i>gapstart and active[i] and not p['stale'][i])
    send_last=max((s for s in sends if s['profile_s']<7),key=lambda s:s['profile_s']);send_next=min((s for s in sends if s['profile_s']>=7.32),key=lambda s:s['profile_s'])
    r=d['research_timing'];rn=r['active'].astype(bool)&r['native_step'].astype(bool);dur=r['inference_duration_us'][rn]
    motor_first={}
    for f in sorted((run/'gz-motor').glob('motor-*.bin')):
        k,a,partial=read_trace(f);idx=np.flatnonzero(a['applied_sample_us']==m['native_timeline']['first_neural_publication_us'])
        motor_first[str(k)]=dict(sim_us=int(a['sim_us'][idx[0]]),sample_us=int(a['applied_sample_us'][idx[0]]),partial_tail_bytes=partial)
    s={'source_run':str(run.relative_to(ROOT)),'flown_commit':json.loads((run/'metadata.json').read_text())['project_commit'],'ulog_sha256':hashlib.sha256((run/'flight.ulg').read_bytes()).hexdigest(),
       'native_timeline':m['native_timeline'],'first_motor_application':motor_first,
       'activation_reference_delay':{'mode_to_external_read_ms':(int(p['timestamp'][firstread])-entry)/1000,
        'mode_cycle_to_runner_confirmation_host_ms':(modeevent['monotonic_ns']-int(p['run_wall_ns'][first]))/1e6,
        'first_publish_end_to_valid_read_host_ms':(int(p['read_wall_ns'][firstread])-event['after_ns'])/1e6,
        'first_sent_position_velocity_exact_float32_match':signature_ok,'note':'same-host CLOCK_MONOTONIC fields; no DDS UTC conversion used'},
       'stale_edges':edges,'gap':{'send_interval_ms':(send_next['before_ns']-send_last['before_ns'])/1e6,
       'last_valid_native_us':int(p['last_valid_read_us'][gapstart]),'stale_capture_native_us':int(p['timestamp'][gapstart]),'resume_native_us':int(p['timestamp'][gapend]),
       'consumed_interval_ms':(int(p['timestamp'][gapend])-int(p['last_valid_read_us'][gapstart]))/1000,'stale_duration_ms':(int(p['timestamp'][gapend])-int(p['timestamp'][gapstart]))/1000},
       'native_executor':{'samples':int(rn.sum()),'period_us_unique':np.unique(np.diff(t)).astype(int).tolist(),'mean_duration_us':float(dur.mean()),'p99_duration_us':float(np.percentile(dur,99)),'max_duration_us':int(dur.max()),'scope':'executor observe+control; not isolated neural-network forward benchmark'},
       'metrics':m['flight_metrics'],'tracking':m['active_target_position_error_m'],'primary':m['frozen_primary_outcome'],'task':m['task_outcome'],'completion':m['completion'],
       'phases':{},'interpretation_limits':['single case and seed, no causal ablation or reliability inference','LP is estimator state; Gazebo trace establishes command consumption, not real flight','pre-reference delay includes coarse runner acknowledgment/state polling; not all DDS transport latency','existing uninitialized relaxed-position arming requirements retained, not fixed for this run']}
    for label,a,b in [('entry_before_external',0,.276),('first_second',0,1),('post_entry_before_gap',1,7.272),('gap_and_resume',7.272,8.5),('final_hold',14.276,18.312)]:
        mask=(rel>=a)&(rel<b);err=np.linalg.norm(pos[mask]-target[mask],axis=1)
        s['phases'][label]={'start_s':a,'end_s':b,'samples':int(mask.sum()),'max_tilt_deg':float(tilt[mask].max()),'min_altitude_m':float(-pos[mask,2].max()),'max_target_error_m':float(err.max()),'target_error_rmse_m':float(np.sqrt(np.mean(err**2)))}
    s['phase_definition_note']='Post-hoc descriptive windows, not pre-registered outcome criteria; P11 native125Hz sampling for phase summaries differs from full-attitude250Hz global peak.'
    ar=d['arming_check_reply'];i=int(np.searchsorted(ar['timestamp'],entry,side='right')-1)
    s['arming_reply_before_entry']={k:clean(ar[k][i]) for k in ['timestamp','registration_id','can_arm_and_run','num_events','health_component_index','mode_req_local_position_relaxed','mode_req_global_position_relaxed']}
    hr=d['health_report'];i=int(np.searchsorted(hr['timestamp'],entry,side='right')-1)
    s['health_report_before_entry']={k:clean(v[i]) for k,v in hr.items() if not k.startswith('_padding')}
    vs=d['vehicle_status'];mask=(vs['timestamp']>=entry)&(vs['timestamp']<=entry+18.312e6)
    s['failsafe_any_neural']=bool(np.any(vs['failsafe'][mask]))
    with (out/'summary.json').open('x') as f:json.dump(clean(s),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    header=['native_us','since_entry_s','n','e','d','target_n','target_e','target_d','vn','ve','vd','target_vn','target_ve','target_vd','tilt_deg','stale','motor0','motor1','motor2','motor3']
    table=np.column_stack([t,rel,pos,target,vel,vtarget,tilt,p['stale'][native],motors])
    with gzip.open(out/'subject-trace.csv.gz','wt') as f:
        writer=csv.writer(f);writer.writerow(header);writer.writerows(table)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.25})
    fig,ax=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    l=d['vehicle_local_position'];whole=(l['timestamp']>=50e6)&(l['timestamp']<84760000)
    ax[0,0].plot(l['y'][whole],l['x'][whole],c='.65',label='Classic Mission + neural path')
    ax[0,0].plot(pos[:,1],pos[:,0],label='Vehicle (neural)');ax[0,0].plot(target[:,1],target[:,0],'--',label='Consumed target');ax[0,0].scatter(pos[0,1],pos[0,0],c='red',label='C to N');ax[0,0].set(xlabel='East (m)',ylabel='North (m)',title='Actual path');ax[0,0].axis('equal');ax[0,0].legend(fontsize=8)
    ax[0,1].plot(rel,-pos[:,2],label='Vehicle altitude');ax[0,1].plot(rel,-target[:,2],'--',label='Consumed target');ax[0,1].set(xlabel='Time from native entry (s)',ylabel='Altitude (m)',title='Altitude and target');ax[0,1].legend()
    ax[1,0].plot(rel,tilt);ax[1,0].axhline(45,c='r',ls='--',label='Task limit');ax[1,0].set(xlabel='Time from native entry (s)',ylabel='Tilt (deg)',title='Takeover transient dominates');ax[1,0].legend()
    ax[1,1].plot(rel,np.linalg.norm(pos-target,axis=1));ax[1,1].set(xlabel='Time from native entry (s)',ylabel='Position error (m)',title='Exact consumed-target error')
    for a in [ax[0,1],ax[1,0],ax[1,1]]:a.axvspan(7.272,7.6,color='orange',alpha=.2);a.axvline(.276,c='purple',ls=':',alpha=.8)
    fig.suptitle('One Mission-to-RAPTOR case | seed20261109 | measured SITL');fig.savefig(out/'overview.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(3,1,figsize=(12,9),sharex=True,constrained_layout=True);mask=(mot['timestamp']>=entry-200000)&(mot['timestamp']<=entry+1200000);mt=(mot['timestamp'][mask].astype(np.int64)-entry)/1e6
    for j in range(4):ax[0].step(mt,mot[f'control[{j}]'][mask],where='post',label=f'Motor{j}')
    ax[0].set(ylabel='Normalized command',title='Ownership changes before the external reference arrives');ax[0].legend(ncol=4)
    mask=rel<=1.2;ax[1].plot(rel[mask],vel[mask,0],label='Vehicle Vn');ax[1].plot(rel[mask],vtarget[mask,0],'--',label='Consumed target Vn');ax[1].set(ylabel='North velocity (m/s)');ax[1].legend()
    ax[2].plot(rel[mask],tilt[mask],label='Tilt');ax[2].set(xlabel='Time from native RAPTOR entry (s)',ylabel='Tilt (deg)')
    for a in ax:
        for x,c,label in [(0,'black','mode/activation'),(.012,'red','neural publication'),(.016,'orange','physical application'),(.276,'purple','first external read')]:a.axvline(x,c=c,ls=':',alpha=.7)
    ax[2].text(.28,30,'First external read +276ms',color='purple');fig.savefig(out/'entry-zoom.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(3,1,figsize=(12,8),sharex=True,constrained_layout=True);mask=(rel>=6.9)&(rel<=8.6)
    ax[0].plot(rel[mask],pos[mask,0],label='Vehicle N');ax[0].plot(rel[mask],target[mask,0],'--',label='Consumed target N');ax[0].set(ylabel='North position (m)',title='Intentional target-stream gap: 328ms between valid reads');ax[0].legend()
    ax[1].plot(rel[mask],vel[mask,0],label='Vehicle Vn');ax[1].plot(rel[mask],vtarget[mask,0],'--',label='Consumed target Vn');ax[1].set(ylabel='North velocity (m/s)');ax[1].legend()
    ax[2].plot(rel[mask],tilt[mask]);ax[2].set(xlabel='Time from native entry (s)',ylabel='Tilt (deg)')
    for a in ax:a.axvspan(7.272,7.6,color='orange',alpha=.15);a.axvspan(7.476,7.6,color='red',alpha=.15);a.axvline(7.476,c='red',ls=':');a.axvline(7.6,c='green',ls=':')
    fig.savefig(out/'gap-zoom.png',dpi=180);plt.close(fig)
    manifest={q.name:{'bytes':q.stat().st_size,'sha256':hashlib.sha256(q.read_bytes()).hexdigest()} for q in out.iterdir() if q.is_file()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('run',type=Path);a.add_argument('output',type=Path);v=a.parse_args();main(v.run.resolve(),v.output.resolve())
