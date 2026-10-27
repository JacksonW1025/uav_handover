"""Source OP projection plus optional conditional past-rate innovation state.
All new quantities keep the same joint roots; external EKF disturbance remains
an explicit model assumption, not certified by OP integral/correction equations.
"""
import numpy as np
from p14r.affine_observer import init as base_init,step as base_step
from p14r.algebra import qmul,qexp

def init(s,doc,library):
 meta=base_init(s,doc,library);m=doc['initial'].get('p14g_innovation')
 if m and m['mode']=='fading':
  C=s['p'].ctx
  for key,field in [('f_rate_theta','theta'),('f_rate_v','velocity'),('f_rate_p','position')]:s[key]=C.constant(m['rates'][field])
  meta['fading_tau_s']=m['tau_s'];meta['fading_last_delayed_sample_us']=m['past_delayed_sample_us']
 return meta

def step(s,meta,control_sample):
 output_sample=control_sample-4000
 if 'fading_tau_s' in meta and output_sample-meta['fusion_pub_sample']>=8000:
  # Source correction receives the delayed target at sample output-delay.
  delayed=output_sample-meta['delay_us'];dt=max(0,(delayed-meta['fading_last_delayed_sample_us'])*1e-6);tau=meta['fading_tau_s'];rho=np.exp(-dt/tau);amp=tau*(1-rho)
  s['f_align']=qmul(qexp(amp*s['f_rate_theta'],group=True),s['f_align']);s['f_ev']=s['f_ev']+amp*s['f_rate_v'];s['f_ep']=s['f_ep']+amp*s['f_rate_p']
  for k in ['f_rate_theta','f_rate_v','f_rate_p']:s[k]=rho*s[k]
  meta['fading_last_delayed_sample_us']=delayed
 return base_step(s,meta,control_sample)
