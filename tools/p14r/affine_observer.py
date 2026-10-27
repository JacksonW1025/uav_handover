"""Correlated NED-chart OutputPredictor projection with its live ring state.

Uses source quaternion/velocity/position corrections and source-shaped IMU
trapezoids. Global geodesy is represented by a conditional flat NED chart;
chart error, float32 and future EKF innovation coverage remain explicit
obligations. Dead vertical diagnostic/auxiliary yaw states do not feed the
retained q/v/p/output map, and are not silently substituted for LP velocity.
"""
import numpy as np
from p14.affine import cat
from p14_motion.algebra import qmul,qconj,qexp,normalize,rotation,mv,transpose,cross
from p14_motion.core import LEVER
from p14r.op import Op
from p14r.observer import FUSION

def init(s,doc,library):
 i=doc['initial'];C=s['p'].ctx;op=Op(library,i['observer']);f=np.frombuffer(op.snapshot(),FUSION,count=1)[0];c=f['core'];d=c['data'];n=int(c['ids'][2]);oldest=int(c['ids'][5]);order=[(oldest+j)%n for j in range(n)];par=i['observer_parameters'];globalLP=op.project(c['geo'][:3],par['LP_reference_geo']);worldLP=op.project(par['world_geo'],par['LP_reference_geo']);V=lambda x:C.constant(np.asarray(x,float))
 s.update(oq=V(d[:4]),ov=V(d[4:7]),op=V(d[7:10]+globalLP),corr=V(d[19:22]),vi=V(d[22:25]),pi=V(d[25:28]),bg=V(par['gyro_bias']),ba=V(par['accel_bias']),sensor_bg=V(par['sensor_gyro_bias']),sensor_ba=V(par['sensor_accel_bias']),f_align=V(par['fusion_attitude_alignment']),f_ev=V(par['fusion_velocity_error']),f_ep=V(np.array(par['fusion_position_error_NED'])+worldLP),bq=V(f['state'][order,:4].reshape(-1)),bv=V(f['state'][order,4:7].reshape(-1)),bp=V((f['state'][order,7:10]+globalLP).reshape(-1)),op_gravity=V([d[39]]),op_velgain=V([d[36]/np.clip(d[37],d[36],10)]),op_posgain=V([d[36]/np.clip(d[38],d[36],10)]),op_attgain=V([.5*d[35]/max(par['fusion_delay_us']*1e-6,d[35])]))
 prefix={x['sample_us']:x for x in i['physical_prefix']};times=list(range(i['sample_us']-156000,i['sample_us']+1,4000));assert all(t in prefix for t in times)
 for key,field in [('histP','p'),('histV','v'),('histQ','q'),('histW','w')]:s[key]=V(np.concatenate([prefix[t][field] for t in times]))
 t=i['sample_us']-par['OP_lag_us'];x=prefix[t];y=prefix[t-4000];z=prefix[t-8000]
 rawg=np.array(x['w'])+par['sensor_gyro_bias'];da=.5*(rawg+np.array(y['w'])+par['sensor_gyro_bias'])*.004
 specific=np.array(x['q']);from p11.models import R
 rawacc=R(specific).T@((np.array(x['body_v'])-y['body_v'])/.004-np.array([0,0,9.8]))+par['sensor_accel_bias']
 s.update(last_rawg=V(rawg),last_da=V(da),last_rawacc=V(rawacc));op.close()
 return {'ring_length':n,'fusion_pub_sample':i['observer']['latest_fusion_publication_sample_us'],'initial_control_sample':i['sample_us'],'lag_us':par['OP_lag_us'],'delay_us':par['fusion_delay_us'],'scope':'source q/v/p correction in conditional local NED chart; future fused-target residual held, not complete EKF'}

def step(s,meta,control_sample):
 C=s['p'].ctx
 for key,live,width in [('histP','p',3),('histV','v',3),('histQ','q',4),('histW','w',3)]:s[key]=cat(s[key][width:],s[live])
 lag=meta['lag_us']//4000
 if lag!=1:raise ValueError('this finite interface supports observed one-step OP lag; other stages require branching')
 def phy(offset):
  # offset0=current control; source output propagated from one-step old state.
  j=39-offset;q=s['histQ'][4*j:4*j+4];w=s['histW'][3*j:3*j+3];p=s['histP'][3*j:3*j+3];v=s['histV'][3*j:3*j+3];M=rotation(q);return q,w,p+mv(M,C.constant(LEVER)),v+mv(M,cross(w,C.constant(LEVER)))
 q,w,bp,bv=phy(1);_,_,_,oldbv=phy(2);rawg=w+s['sensor_bg'];rawacc=mv(transpose(rotation(q)),(bv-oldbv)*250-C.constant([0,0,9.8]))+s['sensor_ba'];da=.002*(rawg+s['last_rawg']);dv=.002*(rawacc+s['last_rawacc']);coning=cross(s['last_da'],da)*(1/12);s.update(last_da=da,last_rawg=rawg,last_rawacc=rawacc)
 s['oq']=normalize(qmul(s['oq'],qexp(da+coning-.004*s['bg']+s['corr'],group=True)));dvE=mv(rotation(s['oq']),dv-.004*s['ba'])+cat(C.constant([0,0]),.004*s['op_gravity']);old=s['ov'];s['ov']=old+dvE;s['op']=s['op']+.002*(old+s['ov'])
 output_sample=control_sample-4000;fused=output_sample-meta['fusion_pub_sample']>=8000
 if fused:
  meta['fusion_pub_sample']=output_sample;n=meta['ring_length'];s['bq']=cat(s['bq'][4:],s['oq']);s['bv']=cat(s['bv'][3:],s['ov']);s['bp']=cat(s['bp'][3:],s['op']);dq,dw,dp,dv=phy(39);qf=qmul(s['f_align'],dq);vf=dv+s['f_ev'];pf=dp+s['f_ep']
  budget=meta.get('innovation_budget')
  if budget:
   oldtag=getattr(C,'tag','nonlinear');C.tag='observation_innovation'
   pieces=[]
   for key,radius in [('innovation_theta',budget['theta_rad']),('innovation_v',budget['velocity_m_s']),('innovation_p',budget['position_m'])]:
    if budget['mode']=='persistent':
     if key not in s:s[key]=C.variable([0.,0.,0.],radius)
     pieces.append(s[key])
    else:pieces.append(C.variable([0.,0.,0.],radius))
   C.tag=oldtag;qf=qmul(qf,qexp(pieces[0],group=True));vf=vf+pieces[1];pf=pf+pieces[2]
  qe=normalize(qmul(qconj(qf),s['bq'][:4]));lo,hi=qe[0].bounds()
  if lo[0]<=0<=hi[0]:raise ValueError('OutputPredictor quaternion correction sign requires discrete split')
  s['corr']=qe[1:] *(-2 if lo[0]>=0 else 2)*s['op_attgain'];ev=vf-s['bv'][:3];ep=pf-s['bp'][:3];s['vi']=s['vi']+ev;s['pi']=s['pi']+ep;cv=ev*s['op_velgain']+.1*s['vi']*s['op_velgain']*s['op_velgain'];cp=ep*s['op_posgain']+.1*s['pi']*s['op_posgain']*s['op_posgain'];s['bv']=cat(*(s['bv'][j*3:j*3+3]+cv for j in range(n)));s['bp']=cat(*(s['bp'][j*3:j*3+3]+cp for j in range(n)));s['ov']=s['bv'][-3:];s['op']=s['bp'][-3:]
 s['att']=s['oq']
 if fused:s['lp']=s['op'];s['lv']=s['ov']
 return s
