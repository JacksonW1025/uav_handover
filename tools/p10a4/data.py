#!/usr/bin/env python3
"""A4 read-only extraction of already-seen P9 development logs. No flight API."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
from pyulog import ULog

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import p6_export,p7_export


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,j):
    with Path(p).open('x') as f:json.dump(j,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def save(p,arrays):
    with zipfile.ZipFile(p,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for k,v in sorted(arrays.items()):
            b=io.BytesIO();np.lib.format.write_array(b,np.asarray(v),allow_pickle=False)
            info=zipfile.ZipInfo(k+'.npy',(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,b.getvalue())


def extract(out):
    out.mkdir(parents=True,exist_ok=False);manifest=[]
    for num in range(1,9):
        run=ROOT/f'data/p9-20261024-dev-{num:02}/run'
        metrics_path=run/('p7-metrics.json' if (run/'p7-metrics.json').exists() else 'p6-metrics.json')
        cfg=json.loads((run/'config.json').read_text());metrics=json.loads(metrics_path.read_text())
        ev=[json.loads(l) for l in (run/'events.jsonl').read_text().splitlines()]
        origin=next(e for e in ev if e['event']=='p1_reference_origin')
        start=next(e['px4_bound_us'] for e in ev if e['event']=='p1_profile_started')
        end=next((e['end_bound_px4_us'] for e in ev if e['event']=='p5_stream_ended'),None)
        u=ULog(str(run/'flight.ulg'),p7_export.TOPICS);tables={d.name:d.data for d in u.data_list if d.multi_id==0}
        old=p6_export.reconstruct(tables);r=p7_export.reconstruct(tables);t=r['s'];n=len(t)
        tm=tables['research_timing'];ix=np.flatnonzero(np.asarray(tm['executor_called']).astype(bool));ts=np.asarray(tm['timestamp_sample'],np.int64)[ix]
        i=np.minimum(np.searchsorted(ts,t),len(ts)-1);valid=(ts[i]==t)&r['ok']
        at=tables['vehicle_attitude'];att_t=np.asarray(at['timestamp_sample'],np.int64)
        named=np.asarray(tm['attitude_sample'],np.int64)[ix[i]];ai=np.minimum(np.searchsorted(att_t,named),len(att_t)-1);valid&=att_t[ai]==named
        qw,qx,qy,qz=[np.asarray(at[f'q[{j}]'],float)[ai] for j in range(4)]
        bz=np.c_[2*(qx*qz+qw*qy),2*(qy*qz-qw*qx),1-2*(qx*qx+qy*qy)]
        valid&=bz[:,2]>.1;q=-9.80665*bz[:,:2]/bz[:,2,None]
        component_error=np.maximum(np.max(np.abs(np.clip(r['pf'][:,:2],-.5,.5)-r['pin'][:,:2]),axis=1),
            np.max(np.abs(np.clip(r['vf'][:,:2],-1,1)-r['pin'][:,12:14]),axis=1))
        valid&=component_error<1e-4
        tg=tables['research_target'];ci=np.flatnonzero(np.asarray(tg['kind'])==1)
        ct=np.asarray(tg['timestamp_sample'],np.int64)[ci];jj=np.searchsorted(ct,t,side='right')-1
        cap_valid=jj>=0;jj=np.maximum(jj,0)
        cap_p=np.c_[np.asarray(tg['vehicle_position[0]'],float)[ci[jj]],np.asarray(tg['vehicle_position[1]'],float)[ci[jj]]]
        cap_v=np.c_[np.asarray(tg['vehicle_velocity[0]'],float)[ci[jj]],np.asarray(tg['vehicle_velocity[1]'],float)[ci[jj]]]
        cap_p[~cap_valid]=np.nan;cap_v[~cap_valid]=np.nan
        # Retain invalid rows with masks; never invent a missing state/target.
        phase=np.full(n,'normal',dtype='U24');repeat=np.zeros(n,bool);event_index=np.full(n,-1,int)
        gaps=metrics.get('gaps') or []
        for j,g in enumerate(gaps):
            cap=(g.get('capture') or {}).get('px4_us');resume=g.get('first_reception_px4_us');last=g.get('last_reception_px4_us')
            if cap is not None and last is not None:phase[(t>last)&(t<cap)]='silence_before_timeout'
            if cap is not None:
                phase[(t>=cap)&((t<resume) if resume else True)]='captured_hold'
                phase[(t>=cap)&(t<cap+80000)]='capture'
            if resume is not None:phase[(t>=resume)&(t<resume+200000)]='resume'
            a=last if last else cap
            b=g.get('segment_end_px4_us')
            if a is not None:
                w=(t>=a)&((t<b) if b else True);repeat[w]=j>0;event_index[w]=j
        if end is not None:phase[t>=end]='end_segment'
        phase[t<start]='pre_stream'
        rc=tables.get('research_recovery');extra=[]
        if rc is not None:
            first=(gaps[0].get('last_reception_px4_us') if gaps else start) or start
            extra=np.asarray(rc['timestamp_sample'],np.int64)[(np.asarray(rc['kind'])==1)&(np.asarray(rc['timestamp_sample'])<first)].tolist()
        sem={'speed':cfg['p1_speed_m_s'],'profile':cfg['p2_profile'],'params':{k:v for k,v in cfg['p2_treatment_parameters'].items() if k!='description'}}
        group=hashlib.sha256(json.dumps(sem,sort_keys=True).encode()).hexdigest()[:16]
        arrays={'t':t,'p':r['pos'][:,:2],'v':r['vel'][:,:2],'q':q,'a':r['acc'][:,:2],
            'rp':r['P'][:,:2],'rv':r['V'][:,:2],'yaw':r['yaw'],'frame_yaw0':np.full(n,float(origin['yaw_rad'])),
            'ep':r['pf'][:,:2],'dv':r['vf'][:,:2],
            'valid':valid,'phase':phase,'repeat':repeat,'event_index':event_index,'vt':r['vt'],
            'cap_p':cap_p,'cap_v':cap_v,'cap_valid':cap_valid,'cap_sample':np.where(cap_valid,ct[jj],-1),
            'lp_age_us':t-np.asarray(tm['local_position_sample'],np.int64)[ix[i]],'att_age_us':t-named}
        filename=f'dev-{num:02}.npz';save(out/filename,arrays)
        manifest.append({'run':num,'file':filename,'sha256':sha(out/filename),'group':group,'role':'fit' if num in [1,3,5,6] else 'retrospective_check',
            'kind':'already_seen_development_NOT_prospective','condition':cfg['p1_condition'],'treatment':cfg['p2_treatment'],
            'profile_start_bound_us':start,'stream_end_bound_us':end,'rows':n,'invalid_rows':int((~valid).sum()),
            'rows_in_profile':int((t>=start).sum()),'aborted':metrics.get('aborted'),'closed_gaps':len(gaps),'extra_pre_event_recovery_start_samples':extra,
            'network_target_component_mismatch_rows':int((component_error>=1e-4).sum()),
            'missing_capture_state_rows':int((~cap_valid).sum()),'missing_recovery_topic':rc is None,
            'p6_reconstruction':old['resid'],'p7_corrected_reconstruction':r['resid'],
            'phase_counts':{x:int((phase==x).sum()) for x in np.unique(phase)},
            'metrics_format':metrics_path.name,
            'source_files':{str(p.relative_to(ROOT)):sha(p) for p in [run/'flight.ulg',run/'config.json',run/'events.jsonl',metrics_path]}})
    roles={}
    for r in manifest:
        if r['group'] in roles and roles[r['group']]!=r['role']:raise ValueError('semantic condition group split leakage')
        roles[r['group']]=r['role']
    write(out/'manifest.json',{'schema':'p10-a4-seen-development-inputs-1','runs':manifest,
        'state':'same gyro-indexed controller observations: p/v named local-position, q named attitude; p7 actual network target including recovery; fixed NED common comparison coordinates',
        'history':'derived from mapped p/v and actual targets, not native FIFO; no queue residual if this deterministic reconstruction is the interface',
        'selection':'all eight existing P9 dev01..08, including failures/censored rows; not formal P9 held-out evidence',
        'split':'whole semantic condition group; fit01,03,05,06; check02,04,07,08; all previously seen, retrospective only',
        'missing_policy':'mask and enumerate, no missing field set to zero','new_SITL_starts':0})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);extract(p.parse_args().output)
