"""Causal timed partitions. Time ranges survive each discrete-order label.
Normal read-grid polygons are conditional; nonstandard clock transitions use a
separate source state graph. Neither is a whole-trajectory equivalence class.
"""
from dataclasses import dataclass,replace
import math,itertools,numpy as np
from p12b.contract import decision

def clip_polygon(poly,a,b,c):
 out=[]
 for p,q in zip(poly,poly[1:]+poly[:1]):
  fp=a*p[0]+b*p[1]-c;fq=a*q[0]+b*q[1]-c
  if fp<=1e-12:out.append(p)
  if (fp<=0)!=(fq<=0):
   t=fp/(fp-fq);out.append([p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])])
 return out

def resume_zones(release,poll,transport,allowed_reads):
 # CoordinatesP,D: release<=P<=release+poll; P<=D<=P+transport.
 # First-read cell: previous_allowed_read <D<=current_allowed_read.
 base=[[release,release],[release+poll,release+poll],[release+poll,release+poll+transport],[release,release+transport]];cells=[]
 for j,r in enumerate(allowed_reads):
  prev=allowed_reads[j-1] if j else release-poll-transport-1
  poly=clip_polygon(base,0,1,r);poly=clip_polygon(poly,0,-1,-prev)
  if len(poly)>=3:
   area=abs(sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(poly,poly[1:]+poly[:1])))/2
   if area>1e-15:cells.append({'first_read':r,'previous_allowed_read':prev,'polygon_P_D':poly,'open_previous_boundary':True,'publication_ancestry':'same P controlsD andsame payload; latest slot survives forbiddenreads','conditions':['normal allowed-read grid only','host poll andtransport explicit future assumptions'],'area_s2':area,'transport_bound_s':transport})
 return cells

def member(cell,p,d,r=None):
 z=np.array(cell['polygon_P_D']);lo=z.min(axis=0);hi=z.max(axis=0)
 return lo[0]-1e-12<=p<=hi[0]+1e-12 and lo[1]-1e-12<=d<=hi[1]+1e-12 and p<=d+1e-12 and d<=p+cell['transport_bound_s']+1e-12 and d<=cell['first_read']+1e-12 and d>cell['previous_allowed_read']+1e-12 and (r is None or abs(r-cell['first_read'])<1e-10)

@dataclass(frozen=True)
class State:
 sample:int;native:int;index:int;count:int;last_read:int;stale:bool=False;pending:int=-1;latest_generated:int=-1;consumed:int=-1

def transition(s,*,sample,native,publish=None,consume=None,phase=1,valid=True,initialized=True,force_sync=2,ordered_transport=True,component_override=False):
 if native<s.native:raise ValueError('native regression is not the plateau/catch-up model')
 permit=decision(phase,True,initialized,True,s.index,force_sync)['gate_permit'];pending=s.pending if publish is None else publish;last=s.last_read
 read=pending>=0 and permit
 if read:
  pending=-1
  if valid:last=native
 stale=native-last>200000;capture=stale and not s.stale;duplicate=sample<=s.sample;commit=not duplicate and s.index%force_sync==0
 if consume is not None and consume>s.latest_generated:raise ValueError('command consumed before its generation')
 if consume is not None and consume<s.consumed and ordered_transport and not component_override:raise ValueError('consumption regression violates declared ordered-single-producer transport condition; plugin itself does not check payload timestamp')
 z=State(max(s.sample,sample),native,s.index+(not duplicate),s.count if duplicate else 0 if commit else s.count+1,last,stale,pending,s.latest_generated if duplicate else s.latest_generated+1,s.consumed if consume is None else consume)
 return z,{'read':read,'valid_read':read and valid,'gate_permit':permit,'capture':capture,'duplicate_rejected':duplicate,'commit':commit,'order':['pre-read','latest-slot selection','valid message / strict native guard','capture/resume','duplicate rejection','observe/history','ordinary output or GRUcommit','new command generation','later physical consumption'],'capture_before_duplicate':capture and duplicate,'ordered_transport_condition':ordered_transport and not component_override,'source_component_or_reordered_transport_requires_separate_mode':not ordered_transport or component_override}

def growth(N):
 states={State(0,0,0,0,-196000)};counts=[];edges=0
 for k in range(N):
  nxt=set()
  for s in states:
   for ds,dn,p in itertools.product([0,4000],[0,4000,8000],[None,k]):
    if abs((s.native+dn)-(s.sample+ds))>8000:continue
    z,_=transition(s,sample=s.sample+ds,native=s.native+dn,publish=p);nxt.add(z);edges+=1
  states=nxt;counts.append(len(states))
 return {'calls':N,'states_per_prefix':counts,'edges':edges,'debt_bound_us':8000,'condition':'finite illustrative sample/native debt graph, not arbitrary-size native jumps or all real-time scheduling','independent_time_counters':True}
