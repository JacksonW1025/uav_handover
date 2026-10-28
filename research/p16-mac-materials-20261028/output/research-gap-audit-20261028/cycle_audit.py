"""Probe the reference-reset drift hypothesis using measured P7 sequences only."""
from pathlib import Path
import json,csv,gzip
import numpy as np
ROOT=Path(__file__).resolve().parent
FIELDS=['ep_f_clip','ep_l_clip','ev_f_clip','ev_l_clip','ep_z','ev_z','tilt_deg','v_u','v_w','a_u','a_z']
SCALE=np.array([.5,.5,1,1,.5,1,45,2,2,9.80665,9.80665])

def main():
    rows=[]
    for root in sorted((ROOT/'upstream/export').glob('p7-20261020-a-q4-*')):
        s=json.load(open(root/'summary.json'));raw=list(csv.DictReader(gzip.open(root/'trace.csv.gz','rt')))
        t=np.array([float(r['t_s']) for r in raw]);x={k:np.array([float(r[k]) for r in raw]) for k in FIELDS+['alt_loss_m']}
        mode=np.array([r['target_mode'] for r in raw]);cs=[e for e in s['events'] if e['event']=='capture' and 0<=e['gap']<4];rs=[e for e in s['events'] if e['event']=='resume' and 0<=e['gap']<4]
        if len(cs)!=4 or len(rs)!=4:raise ValueError(root.name)
        captures=[];resumes=[];cycles=[]
        for e in cs:
            k=int(np.searchsorted(t,e['t_s']-1e-7));captures.append(dict(t=float(t[k]),height_loss=float(x['alt_loss_m'][k]),ep_z_before=float(x['ep_z'][k-1]),ep_z_after=float(x['ep_z'][k]),vz=float(x['ev_z'][k]),tilt=float(x['tilt_deg'][k])))
        for e in rs:
            k=int(np.searchsorted(t,e['t_s']-1e-7));resumes.append(dict(t=float(t[k]),height_loss=float(x['alt_loss_m'][k]),ep_z=float(x['ep_z'][k]),vz=float(x['ev_z'][k])))
        for i in range(3):
            a,b=cs[i]['t_s'],cs[i+1]['t_s'];grid=np.linspace(a,b,101,endpoint=False)
            # Clipped error channels are known exactly from source; other channels remain measured diagnostics.
            z=np.column_stack([np.interp(grid,t,np.clip(x[k],-.5,.5) if k=='ep_z' else np.clip(x[k],-1,1) if k=='ev_z' else x[k])/scale for k,scale in zip(FIELDS,SCALE)])
            ext=(t>=a)&(t<b)&(mode=='external');sat=np.abs(x['ep_z'][ext])>=.5
            cycles.append(dict(duration=b-a,loss=captures[i+1]['height_loss']-captures[i]['height_loss'],external_rows=int(ext.sum()),external_vertical_saturated_fraction=float(sat.mean()) if len(sat) else None,z=z))
        firstlast=np.sqrt(np.mean((cycles[1]['z']-cycles[0]['z'])**2,axis=0));secondlast=np.sqrt(np.mean((cycles[2]['z']-cycles[1]['z'])**2,axis=0))
        hs=np.array([r['height_loss'] for r in captures]);d=np.diff(hs)
        # Genuine prefix-only extrapolators of fourth capture, not a forecast of full-window maximum.
        predictions={'persist_capture3':hs[2],'repeat_first_increment':hs[0]+3*d[0],'repeat_second_increment':hs[2]+d[1],'average_first_two_increments':hs[2]+(d[0]+d[1])/2}
        for c in cycles:c.pop('z')
        rows.append(dict(id=root.name,condition=s['condition'],treatment=s['treatment'],max_height_loss=s['max_altitude_loss_m'],max_tilt=s['max_tilt_deg'],captures=captures,resumes=resumes,cycles=cycles,
            successive_cycle_normalized_rmse=dict(zip(FIELDS,zip(firstlast.tolist(),secondlast.tolist()))),observed_capture4=hs[3],prefix_only_predictions=predictions,
            limitations='Only 3 closed capture-to-capture cycles. Export omits full attitude/omega, GRU, actuator and clock caches. No exact recurrence or invariant region is established.'))
    allcaps=[c for r in rows for c in r['captures']]
    summary=dict(n=len(rows),capture_count=len(allcaps),max_abs_vertical_error_after_capture=max(abs(c['ep_z_after']) for c in allcaps),
        captures_with_loss_above_half_m=sum(c['height_loss']>.5 for c in allcaps),captures_with_loss_above_one_m=sum(c['height_loss']>1 for c in allcaps),
        height_task_failures=sum(r['max_height_loss']>1 for r in rows),height_only_failures=sum(r['max_height_loss']>1 and r['max_tilt']<45 for r in rows),
        positive_all_three_cycle_increments=sum(all(c['loss']>0 for c in r['cycles']) for r in rows),
        prefix_capture4_MAE={k:float(np.mean([abs(r['prefix_only_predictions'][k]-r['observed_capture4']) for r in rows])) for k in rows[0]['prefix_only_predictions']})
    out=dict(hypothesis='Repeated reference captures can erase task-relative loss from controller error. A drift-cycle hypothesis needs measured recurrence, a compatible clipping regime, and positive drift; accumulated loss alone is insufficient.',summary=summary,rows=rows,
        proposed_theory_target='Conditional reset/clipping symmetry with an additive task-loss coordinate; characterize repeatable drifting event motifs and their failure horizon. Relative periodic orbit theory itself is established prior art.',
        current_status='MECHANISM_PROBE_ONLY: no new method superiority, recurrence certificate, switching transfer or cross-platform result claimed.',new_flights=0,new_SITL=0,Thor_used=False)
    (ROOT/'cycle_audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(summary,indent=2))
    for r in rows:print(r['condition'],r['treatment'],'height',[round(c['height_loss'],3) for c in r['captures']],'delta',[round(c['loss'],3) for c in r['cycles']],'sat',[round(c['external_vertical_saturated_fraction'],2) for c in r['cycles']])

if __name__=='__main__':main()
