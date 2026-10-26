#!/usr/bin/env python3
"""Primary-source component first witnesses; no cache/full-topic conflation."""
import sys,json
from pathlib import Path
import numpy as np
from pyulog import ULog
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p11.models import tilt
P=R/'data/p12c-20261026-preparation'
def witness(t,x,limit,complete):
 hit=np.flatnonzero(x>limit)
 if not len(hit):return {'state':'SUCCESS' if complete else 'UNKNOWN','source_time_bracket_us':None}
 k=int(hit[0]);return {'state':'FAILURE','source_time_bracket_us':[None if k==0 else int(t[k-1]),int(t[k])],'meaning':'sampled value bracket, not exact continuous physical crossing'}

def main(out):
 if out.exists():raise FileExistsError(out)
 rows=[]
 for row in json.load(open(P/'protocol.json'))['rows']:
  parent=R/'data/p12c-20261026-development'/row['id'];a=parent/'analysis'
  if not (parent/'result.json').exists():continue
  m=json.load(open(a/'measured/measurement.json'));T={x.name:x.data for x in ULog(str(parent/'run/flight.ulg'),['vehicle_attitude','vehicle_local_position']).data_list if x.multi_id==0};lo,hi=m['window_native_us'];q=T['vehicle_attitude'];qt=q['timestamp'];qs=(qt>=lo)&(qt<hi);angles=np.array([tilt(z) for z in np.column_stack([q[f'q[{i}]'] for i in range(4)])]);p=T['vehicle_local_position'];pt=p['timestamp_sample'];i0=max(0,int(np.searchsorted(pt,lo,side='right')-1));sel=(pt>=lo)&(pt<hi);height=np.asarray(p['z'][sel])-p['z'][i0];rows.append({'id':row['id'],'tilt':witness(qt[qs],angles[qs],45,not m['censored']),'height':witness(pt[sel],height,1,not m['censored']),'LP_height_reference_z_m':float(p['z'][i0]),'frozen_measurement':m['whole'],'source_clocks':{'tilt':'vehicle_attitude.timestamp native publication clock','height':'vehicle_local_position.timestamp_sample IMU/sample clock; exact original asof reference at measurement start'},'profile_mapping':'compare source native/sample bracket with original per-call native/sample/host intervals; no exact zero-uncertainty wall hit or physical crossing asserted'})
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'schema':'p12c-primary-component-first-crossings-1','rows':rows,'original_scorev2_unchanged':True,'controller_cache_prefix_diagnostics_separate':True},indent=2)+'\n');print('FULLTOPIC_CROSSINGS',len(rows))
if __name__=='__main__':main(Path(sys.argv[1]))
