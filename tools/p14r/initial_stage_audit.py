"""Independent initial-information audit; never changes sealed predictor inputs.

The pack is a multirate history state: cached control inputs at observe(),
post-call neural history, and producer/physical prefixes cut at Run begin.
All information must precede the first predicted call; not a synchronous snapshot.
"""
import sys,json
from pathlib import Path
import numpy as np
from pyulog import ULog
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
 b=R/'data/p14r-20261027'
 for name in ['d02','d03','d04','d05','d06']:
  target=next((b/'runs').glob('p14r-'+name+'-*'));run=target/'run';version='source-inputs-v4' if name in ['d05','d06'] else 'source-inputs-v3';path=b/version/name/'input.json';doc=json.load(open(path));i=doc['initial'];obs=i['observer'];d=dict(np.load(target/'analysis-v1/observation/synchronized.npz'));j=int(np.flatnonzero(d['sample_us']==i['sample_us'])[0]);u=ULog(str(run/'flight.ulg'),['research_timing']);t=u.data_list[0].data
  matches=np.flatnonzero(t['timestamp_sample']==i['sample_us']);idx=int(matches[np.argmin(abs(t['p11_cycle_wall_start_ns'][matches].astype(np.int64)-int(d['run_wall_ns'][j])))]);end=int(t['p11_cycle_wall_end_ns'][idx]);begin=int(d['run_wall_ns'][j]);nextbegin=int(d['run_wall_ns'][j+1]);assert begin<=end<nextbegin
  assert obs['max_past_wall_ns']<=begin and obs['cutoff_wall_ns']==begin
  rows.append({'id':name,'input_sha256':sha(path),'sample_us':i['sample_us'],'Run_begin_wall_ns':begin,'same_call_end_wall_ns':end,'first_predicted_call_begin_wall_ns':nextbegin,'call_duration_us':(end-begin)/1000,'end_to_next_begin_us':(nextbegin-end)/1000,'producer_cutoff_wall_ns':obs['cutoff_wall_ns'],'last_producer_record_wall_ns':obs['max_past_wall_ns'],'initial_OP_lag_us':i['observer_parameters']['OP_lag_us'],'all_initial_information_before_first_predicted_call':True,'snapshot_scope':'observe-time cached p/v/q/gyro + same-call post NN/history; physical/OP/gyro producer history cut at Run begin. No future-after-next-call information. Not a simultaneous post-call full EKF/OP snapshot.'})
 write(out/'result.json',{'rows':rows,'all_pass':all(r['all_initial_information_before_first_predicted_call'] for r in rows),'limitation':'Asynchronous producer work within the initial call is not injected. Nominal lag/producer model approximates its continuation; endpoint coverage is for this explicitly staged history representation, not exact complete simulator poststate. No sealed inputs or scores changed.','new_SITL':0})
if __name__=='__main__':main()
