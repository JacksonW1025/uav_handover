from analysis_paths_v1 import analysis_dir
"""Canonical capture-inclusive XYZ hold mechanism summaries, no outcome selection."""
import json,sys
from pathlib import Path
from collections import Counter
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p9_model import write,sha
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);agg=R/'data/p13-20261026-results-v3';cs=json.load(open(agg/'cases.json'))['rows'];assert len(cs)==66 and all(r['status']=='FINISH' for r in cs);rows=[]
for r in cs:
 for h in json.load(open(agg/'holds'/r['id']/'hold-axes.json'))['rows']:
  x={'id':r['id'],'family':r['family'],'block':r['block'],'arm':r['arm'],'branch':r['branch'],'event':h['event'],'status':h['status']}
  if 'rows' in h:
   v=np.array(h['velocity_raw_max_axis_m_s']);p=np.array(h['position_raw_max_axis_m']);cap=np.array(h['capture']['velocity_error_NED_m_s']);x.update(capture_call_included=h['capture_call_included'],rows=h['rows'],capture_horizontal_velocity_error_m_s=float(np.linalg.norm(cap[:2])),capture_vertical_velocity_error_m_s=float(cap[2]),hold_velocity_max_axis_m_s=v.tolist(),hold_position_max_axis_m=p.tolist(),hold_horizontal_velocity_axes_exceed1=int(np.sum(v[:2]>1)),hold_vertical_velocity_exceeds1=bool(v[2]>1),velocity_clip_rows_any=h['velocity_clip_rows_all3'],position_clip_rows_any=h['position_clip_rows_all3'])
  rows.append(x)
groups=[]
for fam in ['F2','F4']:
 for branch in ['A','B','AB','REPAIR']:
  for ev in ['A','B']:
   rr=[r for r in rows if r['family']==fam and r['branch']==branch and r['event']==ev];obs=[r for r in rr if 'rows' in r]
   if not obs:continue
   groups.append({'family':fam,'branch':branch,'event':ev,'assigned_event_slots':len(rr),'observed_hold_segments':len(obs),'full_holds':sum(r['status']=='FULL_HOLD' for r in obs),'censored_prefixes':sum(r['status']=='CENSORED_HOLD_PREFIX' for r in obs),'capture_horizontal_error_max_m_s':max(r['capture_horizontal_velocity_error_m_s'] for r in obs),'capture_abs_vertical_error_max_m_s':max(abs(r['capture_vertical_velocity_error_m_s']) for r in obs),'number_horizontal_axes_clipped_segment_counts':dict(Counter(str(r['hold_horizontal_velocity_axes_exceed1']) for r in obs)),'vertical_clipped_segment_count':sum(r['hold_vertical_velocity_exceeds1'] for r in obs),'velocity_clipped_call_count':sum(r['velocity_clip_rows_any'] for r in obs),'position_clipped_call_count':sum(r['position_clip_rows_any'] for r in obs),'all_calls_capture_inclusive':all(r['capture_call_included'] for r in obs)})
write(out/'summary.json',{'schema':'p13-full-hold-mechanism-1','rows':rows,'groups':groups,'source_semantics':'position/velocity per-axis clipping in current target-yaw frame incl vertical. Capture speed-match is horizontal only; vertical error retained. Number of clipped axes in a segment is not itself causal proof of flight outcome. All assigned slots and censored prefixes kept.','new_SITL':0,'source_sha256':sha(Path(__file__))});print('HOLD_SUMMARY',len(rows),len(groups))
