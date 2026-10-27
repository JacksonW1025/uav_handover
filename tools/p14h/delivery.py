"""Source-shaped latest delivery with explicit planned resume cell times."""
from p14r.delivery import Delivery as Base,Word
from p11.models import reference
class Delivery(Base):
 def __init__(self,d,w):super().__init__(d,w);self.cells={int(x['index']):x for x in d['plan'].get('p14h_cells',[])};self.done=set()
 def step(self,t):
  for k,c in self.cells.items():
   if k in self.done:continue
   a,b=self.plan['windows_profile_s'][k];P,D=c['publication_s'],c['delivery_s']
   if t>=b and self.gap==k:
    self.next_poll=P
    if t<P:return None
    self.transit.append((D,reference(P,self.plan['profile'],self.table)));self.last=P;self.emissions.append(P);self.gap=None;self.next_poll=P+self.word.poll_period_s;self.done.add(k)
  return super().step(t)
