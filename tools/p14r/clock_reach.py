"""Finite publisher-deadline reachability, preserving emission ancestry.

This is conditional on host poll<=10ms, transport<=4ms and one native call per
4ms host profile interval; spin_once(timeout=.01) alone does not prove a host
scheduling bound. 1ms bins are outward time enclosures, not fabricated stamps.
The projection returns event brackets, not point trajectories or pure phase.
"""
import sys,json,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha,records
from p12c.features import load

def reach(doc):
 i,p=doc['initial'],doc['plan'];last=float(i.get('publisher_last_emit_s',i.get('last_send_profile_s',max(0,i['profile_s']))));nodes={int(math.floor(last*1000))};previous_exit=None;rows=[];edges=0
 for event,(a,b) in enumerate(p['windows_profile_s']):
  if b<i['profile_s']:continue
  low=int(math.floor(a*1000));high=int(math.ceil(b*1000));front=set(nodes);seen=set(nodes)
  # Nodes retain source previous-publish deadlines; gap-exit resets publisher
  # last, not neural/history/execution states. Finite projection only at edge.
  while front:
   new=set()
   for x in front:
    for d in range(20,32):
     y=x+d
     if y<low and y not in seen:new.add(y)
   edges+=len(front)*12;seen|=new;front=new
  last_before=sorted(x for x in seen if low-32<=x<low)
  if not last_before:last_before=[int(math.floor(last*1000))]
  # Latest read can be at most transport+read gating after last publication.
  # Strict >200ms then first native output call; time-bin uncertainty outward.
  capture=[min(last_before)*.001+.2-.001,max(last_before)*.001+.004+.008+.2+.004+.001]
  resume=[b-.001,b+.010+.004+.008+.001]
  rows.append({'event':event,'planned_gap':[a,b],'last_emit_bins_ms':last_before,'capture_profile_interval':capture,'resume_profile_interval':resume,'publisher_reset_only':True,'ancestry_from':previous_exit if previous_exit is not None else 'past initial last-emission','conditional_native_mode':'4ms native/sample progression; plateau/catch-up requires clock-debt extension, not silently covered'})
  nodes=set(range(int(math.floor(b*1000)),int(math.ceil((b+.010)*1000))+2));previous_exit=event;last=b
 return {'events':rows,'emission_transition_edges':edges,'conditions':{'poll_service_upper_s':.010,'transport_upper_s':.004,'read_gate_wait_upper_s':.008,'native_sample_host_relation':'one4ms call per4ms host profile; explicitly conditional','time_bin_s':.001,'poll_upper_certified_by_source':False},'future_actual_input':False,'state':'last-publish deadline/gap-exit ancestry retained; latest-value delivery projected to event brackets; payload correlation requires full branch tube, not independent targets'}

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
 write(out/'before-compute.json',{'source':sha(Path(__file__)),'conditional_bounds':'10ms host service,4ms transport,8ms read gate; no fitting to future capture; bins1ms outward','prior_fixed_poll_failure_retained':'A-clock-v1 F2-B capture is8ms early outside8 representatives','scope':'conditional clock projection, no dynamic safety claim'})
 for rec in records():
  doc=json.load(open(rec['packed']/'prediction-input.json'));d=load(rec['target']/'run',rec['analysis']);result=reach(doc);w=doc['plan']['windows_profile_s'];caps=np.flatnonzero(d['stale']&np.r_[False,~d['stale'][:-1]]);res=np.flatnonzero(~d['stale']&np.r_[False,d['stale'][:-1]])
  for e in result['events']:
   a,b=e['planned_gap'];actualcap=[float(d['t'][j]) for j in caps if a<=d['t'][j]<b+.08];actualres=[float(d['t'][j]) for j in res if b<=d['t'][j]<b+.08];e['actual_capture_diagnostic']=actualcap;e['actual_resume_diagnostic']=actualres
   e['capture_contained']=all(e['capture_profile_interval'][0]<=t<=e['capture_profile_interval'][1] for t in actualcap) if actualcap else None;e['resume_contained']=all(e['resume_profile_interval'][0]<=t<=e['resume_profile_interval'][1] for t in actualres) if actualres else None
  result['id']=rec['id'];rows.append(result);write(out/(rec['id']+'.json'),result)
 write(out/'summary.json',{'records':len(rows),'rows':rows,'capture_tested':sum(e['capture_contained'] is not None for r in rows for e in r['events']),'capture_missed':sum(e['capture_contained'] is False for r in rows for e in r['events']),'resume_tested':sum(e['resume_contained'] is not None for r in rows for e in r['events']),'resume_missed':sum(e['resume_contained'] is False for r in rows for e in r['events']),'validation':'retrospective interval coverage, does not certify assumed future host bounds'})
if __name__=='__main__':main()
