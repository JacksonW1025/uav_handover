"""Correlated legal publisher/transport words; source gap-exit is immediate.
Host poll phase and transport delay persist across calls/events, not iid choices.
The queue is latest-value; PH1/PH2 read gating remains in original Ctl.
"""
from dataclasses import dataclass
import numpy as np
from p11.models import reference
@dataclass(frozen=True)
class Word:
 poll_phase_s:float=0.
 transport_s:float=0.
 poll_period_s:float=.004
 producer_order:str='PRE'

class Delivery:
 def __init__(self,doc,word):
  self.plan=doc['plan'];self.i=doc['initial'];self.word=word;self.table=np.array(self.plan['profile']['table']);self.last=float(self.i.get('publisher_last_emit_s',self.i.get('last_send_profile_s',-1e30)));self.gap=self.inside(self.i['profile_s']);self.next_poll=self.i['profile_s']+word.poll_phase_s
  if self.next_poll<=self.i['profile_s']+1e-12:self.next_poll+=word.poll_period_s
  self.transit=[];self.emissions=[]
  live=self.i.get('delivery_live')
  if live:
   self.last=live['last'];self.gap=live['gap'];self.next_poll=live['next_poll'];self.transit=[(t,(np.array(m[0]),np.array(m[1]),m[2])) for t,m in live['transit']]
  old=self.i.get('publisher_unconsumed_past') if not live else None
  if old is not None:self.transit.append((self.i['profile_s']+word.transport_s,(np.array(old['p']),np.array(old['v']),old['yaw'])))
 def dump(self):return {'last':self.last,'gap':self.gap,'next_poll':self.next_poll,'transit':[(float(t),(m[0].tolist(),m[1].tolist(),float(m[2]))) for t,m in self.transit]}
 def inside(self,t):return next((j for j,(a,b) in enumerate(self.plan['windows_profile_s']) if a<=t<b),None)
 def step(self,t):
  while self.next_poll<=t+1e-10:
   tau=self.next_poll;self.next_poll+=self.word.poll_period_s;k=self.inside(tau)
   if k is not None:self.gap=k;continue
   exited=self.gap is not None;self.gap=None
   if tau<0 or tau>=self.plan['stream_end_profile_s']:continue
   if exited or tau-self.last>=self.plan['publish_period_s']-1e-10:
    message=reference(tau,self.plan['profile'],self.table);self.transit.append((tau+self.word.transport_s,message));self.last=tau;self.emissions.append(tau)
  available=[m for when,m in self.transit if when<=t+1e-10];self.transit=[(when,m) for when,m in self.transit if when>t+1e-10]
  return available[-1] if available else None

WORDS=[Word(phase,delay) for phase in [0.,.001,.002,.003] for delay in [0.,.004]]
