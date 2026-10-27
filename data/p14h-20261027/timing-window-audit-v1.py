"""Read-only audit of actual source cache-copy intervals and initialization causality.
Run start is a lower bound, never silently treated as the cache-copy instant.
"""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from pyulog import ULog
from p14h.common import *
from p12c.features import load
from p14r.observer import read,CORE,FUSION

def main():
 out=register(sys.argv[1],'all16 source time windows: gyro/LP/att copied between Runstart and external-readend; h_after available by cycleend. Correct diagnostic point-time interpretation, no model/score alteration',source_positions={'Runstart':'mc_raptor.cpp:648','LP_copy':746,'att_copy':755,'external_read_end':881,'h_after_and_cycleend':[1303,1315,1342]},future_data_scope='audit/scoring only, never selector/autonomous inputs');rows=[]
 for target in sorted((B/'runs').iterdir()):
  if not (target/'information.json').exists():continue
  n=target.name.split('-')[1];info=json.load(open(target/('information-v2.json' if (target/'information-v2.json').exists() else 'information.json')));analysis=R/info['source_analysis'] if info.get('source_analysis') else target/'analysis-v1';obs=load(target/'run',analysis)
  if n.startswith('d'):doc=json.load(open(B/f'cadence-recovery-v2/{n}/input.json'))
  else:doc=json.load(open(B/f'evaluation-{n}-v1/past-packet/input.json'))
  i=doc['initial'];core,_=read(target/'run/gz-motor/observer-core.bin',CORE,b'P14RCORE',True);post=core[core['kind']==2];fusion,_=read(target/'run/gz-motor/observer-fusion.bin',FUSION,b'P14RFUS1',True);fp=fusion['core'][fusion['core']['kind']==4];pidx={int(x['sample_us']):int(x['wall_ns']) for x in post};fidx={int(x['ids'][0]):int(x['wall_ns']) for x in fp};lo=obs['run_wall_ns'].astype(np.int64);hi=obs['read_wall_ns'].astype(np.int64);lower=np.searchsorted(post['wall_ns'],lo,side='right')-1;upper=np.searchsorted(post['wall_ns'],hi,side='right')-1;valid=(lower>=0)&(upper>=0)&(obs['sample_us']>i['sample_us']);ix=np.flatnonzero(valid);lt=post['sample_us'][lower[ix]].astype(np.int64);ut=post['sample_us'][upper[ix]].astype(np.int64);control=obs['sample_us'][ix].astype(np.int64);inside=(lt!=ut);attstamp=obs['att_sample'][ix].astype(np.int64);lpstamp=obs['lp_sample'][ix].astype(np.int64);att_inside=[];att_unavailable=[];lp_inside=[]
  for k,j in enumerate(ix):
   aw=pidx.get(int(attstamp[k]));fw=fidx.get(int(lpstamp[k]))
   if aw is not None and lo[j]<aw<=hi[j]:att_inside.append(int(j))
   if aw is None or aw>hi[j]:att_unavailable.append(int(j))
   if fw is not None and lo[j]<fw<=hi[j]:lp_inside.append(int(j))
  timing=next(x.data for x in ULog(str(target/'run/flight.ulg'),['research_timing']).data_list if x.name=='research_timing');sel=(timing['timestamp_sample']==i['sample_us'])&timing['active'].astype(bool)&(timing['p11_cycle_wall_end_ns']>0);assert np.any(sel);end=int(timing['p11_cycle_wall_end_ns'][np.flatnonzero(sel)[-1]]);j=int(np.flatnonzero(obs['sample_us']==i['sample_us'])[-1]);epoch=round(int(obs['run_wall_ns'][j])-obs['t'][j]*1e9);A_wall=epoch+round(doc['plan']['full_source_windows_profile_s'][0][0]*1e9);nextrows=np.flatnonzero(obs['sample_us']>i['sample_us']);next_start=int(obs['run_wall_ns'][nextrows[0]]) if len(nextrows) else None
  row=dict(id=target.name,initial_original_runstart_cut_ns=i['observer']['cutoff_wall_ns'],initial_information_upper_cycleend_ns=end,initial_origin_interval_ns=[int(obs['run_wall_ns'][j]),end],all_controller_row_fields_available_before_A=end<A_wall,initial_end_to_A_ms=(A_wall-end)/1e6,initial_end_before_next_forecasted_control=next_start is not None and end<next_start,initial_Runstart_is_not_h_after_availability=True,profile_scoring_not_shifted=True,rows=len(ix),producer_updates_inside_cache_copy_window=int(sum(inside)),actual_attitude_post_inside_window=len(att_inside),actual_LP_fusion_post_inside_window=len(lp_inside),attitude_timestamp_no_completed_CALC_POST_by_readend=len(att_unavailable),OP_sample_minus_control_range_us=[int(min(ut-control)),int(max(ut-control))],OP_completed_sample_ahead_control_rows=int(sum(ut>control)),future_nominal_PRE4ms_mismatch_rows=int(sum(ut!=np.maximum(i['observer']['latest_completed_update_sample_us'],control-4000))),first_in_window_example=None if not att_inside else dict(sample_us=int(obs['sample_us'][att_inside[0]]),run_wall_ns=int(lo[att_inside[0]]),read_wall_ns=int(hi[att_inside[0]]),att_sample_us=int(obs['att_sample'][att_inside[0]]),source_post_wall_ns=pidx[int(obs['att_sample'][att_inside[0]])]),future_timestamps_never_primary_inputs=True)
  assert row['all_controller_row_fields_available_before_A'] and row['initial_end_before_next_forecasted_control'];rows.append(row)
 write(out/'result.json',dict(rows=rows,all_initial_information_before_A=True,strict_Runstart_cut_claim='WITHDRAWN for completed h/action/cache row: availability upper is source cycleend. Frozen packet and scores retained; no task-future leak, no posthoc time alignment.',diagnostic_correction='producer-v1/v2 Runstart lookup is LOWER-BOUND completion word, not unique actual cache-copy word. Payload missing there can be an in-call ordering artifact; do not attribute it uniquely to EKF or a missing sensor.',model_mismatch='primary PRE_COMPLETE4ms nominal is still not all-real-timing coverage; actual legal interval branches and OP/control sample order require asynchronous event state',no_frozen_grade_or_parameter_changed=True))
 print('TIMING_WINDOW_AUDITED',len(rows),sum(r['actual_attitude_post_inside_window'] for r in rows),sum(r['OP_completed_sample_ahead_control_rows'] for r in rows))
if __name__=='__main__':main()
