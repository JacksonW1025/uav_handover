#!/usr/bin/env python3
"""Post-hoc supplement for P5 gap runs that the runner aborted while the setpoint stream was still interrupted.

The frozen p5_metrics measures closed gaps only (a reception after the gap); a run aborted inside a gap keeps its
correct flight outcome (FAILURE, runner safety abort) but no capture or tilt numbers for that gap. This tool, written
after the batches, measures the trailing open gap from raw run evidence (last setpoint arrival before the abort, the
in-flight capture, tilt and altitude up to the abort or log end) and writes <batch>/open-gap-supplement.json. It never
modifies run directories or their stored metrics.

  p5_open_gap.py data/<batch> [data/<batch> ...]
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_metrics import clean,asof,tilt_deg
from p5_metrics import receptions,clipping_axes,vec
ROOT=Path(__file__).resolve().parents[1]

def open_gap(run):
    cfg=json.loads((run/'config.json').read_text());events=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()]
    fail=next((e for e in events if e['event']=='failure'),None);started=next((e for e in events if e['event']=='p1_profile_started'),None)
    if fail is None or started is None:return None
    u=ULog(str(run/'flight.ulg'),['raptor_status','trajectory_setpoint','research_target','research_memory','vehicle_local_position','vehicle_attitude','vehicle_status'])
    t={d.name:d.data for d in u.data_list if d.multi_id==0};vs=t['vehicle_status'];vt=np.asarray(vs['timestamp'],np.int64)
    t0=int(started['px4_bound_us']);disarm=vt[(vt>t0)&(np.asarray(vs['arming_state'])!=2)];t_end=int(min([u.last_timestamp]+([int(disarm[0])] if len(disarm) else [])))
    # RAPTOR ownership end: the abort hands over to the classic land/failsafe; use the last RAPTOR-active status row.
    st=t['raptor_status'];stt=np.asarray(st['timestamp'],np.int64);act=stt[(np.asarray(st['active'])==1)&(stt>=t0)];t_own=int(act[-1]) if len(act) else t_end
    rec=receptions(st,t['trajectory_setpoint']);rec=rec[(rec>=t0)&(rec<=t_own)];last=int(rec[-1])
    if t_own-last<=100000:return {'open_gap':False,'note':'stream not interrupted at the end of RAPTOR ownership'}
    tg=t['research_target'];tt=np.asarray(tg['timestamp'],np.int64);caps=np.flatnonzero((np.asarray(tg['kind'])==1)&(np.asarray(tg['activation'])==0)&(tt>last)&(tt<=t_own))
    out={'open_gap':True,'last_arrival_px4_us':last,'raptor_last_active_px4_us':t_own,'silence_until_raptor_end_s':(t_own-last)/1e6,'in_flight_captures':int(len(caps)),
         'planned_D_s':cfg['p2_profile']['gaps']['duration_s'],'gap_index':int(sum(1 for e in events if e['event']=='p5_gap_started'))-1,'failure_reason':fail['reason']}
    att=t['vehicle_attitude'];at=np.asarray(att['timestamp'],np.int64);aw=(at>=last)&(at<=t_end);tilt=tilt_deg(np.stack([att[f'q[{i}]'] for i in range(4)],1).astype(float)[aw])
    lp=t['vehicle_local_position'];lts=np.asarray(lp['timestamp_sample'],np.int64);z=np.asarray(lp['z'],float);lw=(lts>=last)&(lts<=t_own)
    out['max_tilt_deg_until_log_end']=float(np.max(tilt));out['max_tilt_deg_until_raptor_end']=float(np.max(tilt[at[aw]<=t_own]))
    out['max_altitude_loss_m_until_raptor_end']=max(0.,float(np.max(z[lw])-z[asof(lts,last)]))
    if len(caps):
        c=int(caps[0]);tc=int(tt[c]);v=vec(tg,'vehicle_velocity',c)
        out['capture']={'px4_us':tc,'after_last_arrival_s':(tc-last)/1e6,'mode':int(tg['mode'][c]),'target_velocity_ned_m_s':vec(tg,'velocity',c),'captured_speed_m_s':math.hypot(v[0],v[1])}
        over=at[aw][tilt>=cfg['safety_tilt_deg']];out['capture_to_45deg_s']=float((over[0]-tc)/1e6) if len(over) else None
        out['capture_to_raptor_end_s']=(t_own-tc)/1e6
        out['clipping_capture_to_raptor_end']=clipping_axes(cfg,t['research_memory'],tc,t_own)
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batches',nargs='+',type=Path);a=p.parse_args()
    for b in a.batches:
        b=b.resolve();res=json.loads((b/'results.json').read_text());rows={}
        for r in res['runs']:
            if r['kind']!='p5_gap' or not r.get('flight_failure'):continue
            rows[r['id']]=open_gap(ROOT/r['directory'])
        out={'batch':str(b.relative_to(ROOT)),'note':__doc__.split('\n\n')[1].replace('\n',' '),'runs':rows}
        (b/'open-gap-supplement.json').write_text(json.dumps(clean(out),indent=1,ensure_ascii=False,allow_nan=False)+'\n')
        for k,v in rows.items():print(b.name,k,json.dumps({x:v.get(x) for x in ['open_gap','silence_until_raptor_end_s','max_tilt_deg_until_raptor_end','capture_to_45deg_s','max_altitude_loss_m_until_raptor_end']} if v else None),(v or {}).get('capture'))
if __name__=='__main__':main()
