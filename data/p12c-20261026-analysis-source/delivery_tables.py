#!/usr/bin/env python3
"""All completed starts, no selected successful subset; no launch."""
import json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from event_geometry import process
P=R/'data/p12c-20261026-preparation';O=R/'data/p12c-20261026-delivery/event-tables'
def main():
 O.mkdir(exist_ok=False);rows=json.load(open(P/'protocol.json'))['rows'];manifest=[]
 for row in rows:
  parent=R/'data/p12c-20261026-development'/row['id']
  if not (parent/'result.json').exists():manifest.append({'id':row['id'],'status':'NOT_STARTED_ENGINEERING_STOP','event_table':None});continue
  out=O/row['id'];table=process(parent,out);geom=json.load(open(out/'event-COM-geometry.json'));g=next(x.data for x in ULog(str(parent/'run/flight.ulg'),['vehicle_local_position_groundtruth']).data_list if x.name=='vehicle_local_position_groundtruth');st=g['timestamp_sample'].astype(np.int64)
  for z in geom['rows']:
   event=next(e for e in table['rows'] if e['label']==z['label']);stamp=z['sample_us']-event['state']['world_callback_age_us'];j=int(np.searchsorted(st,stamp,side='right')-1);z['truth_pose_native_callback_interval_us']=[None if j==0 else int(st[j-1]),int(st[j])];z['truth_velocity_denominator_clamped_us']=None if j==0 else int(np.clip(st[j]-st[j-1],1000,100000));z['truth_physical_pose_time_interval']='UNKNOWN: Pose_V physical header not copied into groundtruth ULog; native callback stamps and differentiation interval retained, never declared a direct physical twist';z['pending_command_status']='latest bridge vs last completed motor state retained; transport/in-progress consumption cannot be fully reconstructed as a snapshot; do not equate latest published with execution'
  (out/'event-COM-geometry-and-W-provenance.json').write_text(json.dumps(geom,indent=2)+'\n');manifest.append({'id':row['id'],'ordinal':row['ordinal'],'class':row['class'],'observe':row['observe'],'sim_seed':row['sim_seed'],'status':'COMPLETED_PREPARATION_ONLY','formal':False,'censored':table['censored'],'flight_outcome':table['frozen_outcome'],'task_outcome':table['task_outcome'],'whole':table['full_task_measurement'],'events':table['events'],'event_table':str((out/'event-states.json').relative_to(R)),'geometry_W_provenance':str((out/'event-COM-geometry-and-W-provenance.json').relative_to(R))})
 (O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('EVENT_TABLES',sum(r['event_table'] is not None for r in manifest),'missing',sum(r['event_table'] is None for r in manifest))
if __name__=='__main__':main()
