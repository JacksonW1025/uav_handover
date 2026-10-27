"""An exact conditional publisher/delivery cell representative.
P,D are planned before forecast, not read from a future flight word. The full
continuous cell is NOT certified by its vertices/center point forecasts.
"""
from p14r.delivery import Delivery as Base,Word
from p11.models import reference
class Delivery(Base):
 def __init__(self,doc,word):
  super().__init__(doc,word);self.cell=doc['plan'].get('p14g_cell');self.injected=False
 def step(self,t):
  if not self.cell:return super().step(t)
  P=self.cell['publish_s'];D=self.cell['delivery_s'];a,b=self.plan['windows_profile_s'][0]
  if not self.injected and t>=b:
   # Suppress only plannedgap-exit poll untilP (<=b+10ms condition).
   if self.next_poll>=b-1e-12:self.next_poll=P
   if t>=P:
    self.transit.append((D,reference(P,self.plan['profile'],self.table)));self.last=P;self.emissions.append(P);self.gap=None;self.next_poll=P+self.word.poll_period_s;self.injected=True
   else:return None
  return super().step(t)
