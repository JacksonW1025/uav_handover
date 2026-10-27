import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *
from p14g.partition import *
from p12b.read_trace import load as pre_load
from p12c.features import load
from p14r.clock_reach import reach

def main():
 out=Path(sys.argv[1]);register(out,'H1: exact source-order contract and continuous resume delivery cells; normalclock conditional brackets separate');start=time.perf_counter();rows=[]
 for n,c in cases().items():
  run=R/c['raw_run'];pre=pre_load(run/'gz-motor/read-p12b.bin');active=pre['active'].astype(bool);idx=np.flatnonzero(active);gates=[];invalid_refresh=[];signatures={}
  for j in idx:
   dec=decision(int(pre['requested_phase'][j]),True,bool(pre['timing_initialized_pre'][j]),bool(pre['force_sync_initialized_pre'][j]),int(pre['call_index_pre'][j]),int(pre['force_sync_pre'][j]));gates.append(dec['gate_permit']==bool(pre['gate_permit'][j]) and dec['gate_applicable']==bool(pre['gate_applicable'][j]) and (not pre['read_updated'][j] or dec['gate_permit']));invalid_refresh.append(not(pre['read_updated'][j] and not pre['read_valid'][j]) or pre['last_valid_read_pre'][j]==pre['last_valid_read_post'][j]);sig=(bool(pre['timing_initialized_pre'][j]),int(pre['call_index_pre'][j])%max(1,int(pre['force_sync_pre'][j])),bool(pre['gate_pending'][j]),bool(pre['read_updated'][j]),bool(pre['read_valid'][j]));signatures[str(sig)]=signatures.get(str(sig),0)+1
  target=run.parent;d=load(run,target/'analysis-v1');D=doc(n);zones=[];p0=D['initial']['profile_s'];cindex=D['initial']['call_index'];first_allowed=[p0+.004*k for k in range(1,1000) if (cindex+k-1)%2==(0 if D['plan']['p12_phase']==1 else 1)]
  for a,b in D['plan']['windows_profile_s']:
   cells=resume_zones(b,.010,.004,[r for r in first_allowed if b-.008<=r<=b+.032]);zones.append({'gap':[a,b],'cells':cells,'continuous_P_D_retained':True})
  prior=reach(D);caps=np.flatnonzero(d['stale']&np.r_[False,~d['stale'][:-1]]);res=np.flatnonzero(~d['stale']&np.r_[False,d['stale'][:-1]]);coverage=[]
  for e in prior['events']:
   a,b=e['planned_gap'];cap=[float(d['t'][j]) for j in caps if a<=d['t'][j]<b+.08];rr=[float(d['t'][j]) for j in res if b<=d['t'][j]<b+.08];coverage.append({'capture':cap,'resume':rr,'conditional_brackets':e,'capture_covered':all(e['capture_profile_interval'][0]<=t<=e['capture_profile_interval'][1] for t in cap) if cap else None,'resume_covered':all(e['resume_profile_interval'][0]<=t<=e['resume_profile_interval'][1] for t in rr) if rr else None})
  rows.append({'id':n,'active_calls':len(idx),'source_pre_read_contract_all':all(gates),'invalid_reads_do_not_refresh':all(invalid_refresh),'discrete_signatures':signatures,'normal_clock_resume_zones':zones,'conditional_bracket_coverage':coverage,'actual_word_is_scoring_only':True,'source_record_sha256':sha(run/'gz-motor/read-p12b.bin')})
 historical=json.load(open(OLD/'A-timing-v2/timing.json'));miss=[x for x in historical['records'] if x['id']=='p13-F2-b1-AB-short'];legacy=json.load(open(OLD/'A-clock-reach-v2/p13-F2-b1-AB-short.json'));growths=[growth(n) for n in [1,2,4,8]]
 # Concrete forbidden words and capture-before-duplicate are independent fixtures.
 s=State(10000,210000,1,1,0,False,pending=4,latest_generated=5);z,x=transition(s,sample=10000,native=214000);z2,y=transition(z,sample=14000,native=218000);rejected=False
 try:transition(s,sample=14000,native=214000,consume=6)
 except ValueError:rejected=True
 tests={'forbidden_read_keeps_slot':z.pending==4 and not x['read'],'capture_precedes_duplicate':x['capture_before_duplicate'],'duplicate_keeps_index_history':z.index==s.index and z.count==s.count,'illegal_early_consume_rejected':rejected,'strict_timeout_200000_not_capture':not transition(State(0,196000,0,0,0),sample=4000,native=200000)[1]['capture'],'initialized_bypass_source_not_lastGRU':decision(1,True,False,False,1,2)['gate_permit']}
 result={'rows':rows,'local_tests':tests,'historical_two_call_example':miss,'historical_B_capture_conditional_interval':legacy['events'][1],'fixed8_scope':'P14R A-clock-v1 predictions retained; misses Bcapture by8ms; discrete-order polygons/clockgraph extend representation but no trajectory equivalence claimed','growth':growths,'elapsed_s':time.perf_counter()-start,'H1':'source-contract coverage and continuous delivery partition supported conditionally; arbitrary future native/sample jumps not exhaustively bounded','all_source_contracts':all(r['source_pre_read_contract_all'] for r in rows)};write(out/'result.json',result);assert all(tests.values()) and result['all_source_contracts'];print('A_DONE',result['elapsed_s'])
if __name__=='__main__':main()
