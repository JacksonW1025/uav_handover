"""Passive source model call record, unchanged source update/guards."""
from p14_motion.core import Ctl as Base
class Ctl(Base):
 def __init__(self,*a,**kw):super().__init__(*a,**kw);self.branch_trace=[]
 def step(self,native,sample,p,v,q,omega,message,P,ablation=None):
  commit=self.index%self.force_sync==0;allowed=self.phase==0 or self.phase==1 and commit or self.phase==2 and not commit;queued=message is not None or self.pending is not None;last=self.target.last_read;stale=self.target.stale;index=self.index
  action,info=super().step(native,sample,p,v,q,omega,message,P,ablation)
  self.branch_trace.append({'sample_us':int(sample),'native_us':int(native),'index_pre':index,'read':bool(allowed and queued),'refresh':self.target.last_read!=last,'commit':bool(info.get('commit',False)),'duplicate':bool(info.get('rejected',False)),'capture':bool(not stale and info['stale']),'resume':bool(stale and not info['stale']),'stale':bool(info['stale']),'command_generated':action is not None,'consume_rule':'next physical step; output latest slot, no extra delay nominal'})
  return action,info
