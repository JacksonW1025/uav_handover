"""Moving-source joint tube with capture/resume, observer, history and execution.
No future log word. The set covers the DECLARED conditional model, not unknownEKF.
"""
import sys,json,time,resource
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14_motion.algebra import *
from p14_motion.core import LEVER,DT,coeff,physical,mul,yaw as pointyaw,forecast
from p13.physical_model import pos,turn,I as Iavg,Ir,mass
from p11.models import reference,R
from p14.common import write,sha

def source(s):
 C=s['p'].ctx;p,v,q,w,f,fn,phi=(s[k] for k in ['p','v','q','w','f','fn','phi']);M=rotation(q);vb=mv(transpose(M),v)
 bodyforces=[];torques=C.constant(np.zeros(3));T=f*f*8.54858e-6
 for j in range(4):
  vl=vb+cross(w,C.constant(pos[j]));perp=cat(vl[:2],C.constant([0.]));fb=cat(-8.06428e-5*f[j]*perp[0],-8.06428e-5*f[j]*perp[1],-T[j])
  bodyforces.append(fb);torques=torques+cross(C.constant(pos[j]),fb)+cat(-1e-6*f[j]*perp[0],-1e-6*f[j]*perp[1],C.constant([0.]))
 torques=torques+cat(C.constant([0.,0.]),T.linear((.016*turn)[None,:]));F=bodyforces[0]
 for fb in bodyforces[1:]:F=F+fb
 ac=C.constant([0,0,9.8])+mv(M,F)*(1/mass)
 spin=cat(C.constant([0.,0.]),f.linear((-Ir*turn/10)[None,:]));sr=cat(C.constant([0.,0.]),(fn-f).linear((-Ir*turn/(10*DT))[None,:]))
 inertia=C.constant(Iavg.reshape(-1));dI=C.constant(np.zeros(9));delta=(3.8464910483993325e-7-2.6115851691700804e-5)/2
 for j in range(4):
  c=trig(2*phi[j],'cos');z=trig(2*phi[j],'sin');z0=C.constant([0.]);speed=f[j]*(-turn[j]/10)
  inertia=inertia+delta*cat(c,z,z0,z,-c,z0,z0,z0,z0)
  dI=dI+2*delta*cat(-z*speed,c*speed,z0,c*speed,z*speed,z0,z0,z0,z0)
 dw=solve(inertia,torques-sr-mv(dI,w)-cross(w,mv(inertia,w)+spin));wn=w+DT*dw
 qn=normalize(qmul(q,qexp(DT*wn)));N=rotation(qn);r=C.constant(-LEVER)
 bv=v-mv(M,cross(w,r));ab=ac-mv(M,cross(dw,r)+cross(w,cross(w,r)));bvn=bv+DT*ab
 return p-mv(M,r)+DT*bvn+mv(N,r),bvn+mv(N,cross(wn,r)),qn,wn,phi+fn*(-DT*turn/10)

def initial(doc,scale):
 i=doc['initial'];C=Context();rad=json.load(open(ROOT/'config/p14-motion-offline.json'))['initial_scenario_radii'];V=lambda x,r:C.variable(np.array(x,float),r*scale)
 q=normalize(qmul(C.constant(i['physical_q']),qexp(V([0,0,0],rad['attitude_rad']))));qh=normalize(qmul(C.constant(i['attitude']),qexp(V([0,0,0],rad['attitude_output_rad']))))
 s={'p':V(i['physical_COM_p'],rad['p_m']),'v':V(i['physical_COM_v'],rad['v_m_s']),'q':q,'w':V(i['physical_omega'],rad['omega_rad_s']),'op':V(i['position'],rad['LP_p_m']),'ov':V(i['velocity'],rad['LP_v_m_s']),
 'd1':V(i['gyro_delay1'],rad['gyro_delay_rad_s']),'d2':V(i['gyro_delay2'],rad['gyro_delay_rad_s']),'bias':V(i['gyro_output_bias'],rad['gyro_bias_rad_s']),'h':V(i['h'],rad['h']),'previous':V(i['previous'],rad['previous_mean']),'mean':V(i['history'],rad['previous_mean']),'f':V(i['rotor_filter'],rad['filter_rad_s']),'pending':V(i['pending_command'],rad['filter_rad_s']),'phi':V(i['rotor_phase'],1e-5)}
 dy=pointyaw(np.array(i['attitude']))-pointyaw(np.array(i['physical_q']));nav=np.array([[np.cos(dy),-np.sin(dy),0],[np.sin(dy),np.cos(dy),0],[0,0,1.]])
 s['align']=normalize(qmul(qh,qconj(q)));s['bpold']=(s['v']+mv(rotation(q),cross(s['w'],C.constant(LEVER)))).linear(nav)
 s['origin']=s['op']-(s['p']+mv(rotation(q),C.constant(LEVER))).linear(nav)
 s.update(lp=s['op'],lv=s['ov'],att=qh,gyro=V(i['omega'],.001),r=C.constant(i['target_p']),rv=C.constant(i['target_v']),ty=C.constant([i['target_yaw']]),capture_p=C.constant(i['target_p']),H0=s['p'][2])
 return s,C,nav

def metrics(s,nom):
 p,v,q,w=(s[k] for k in ['p','v','q','w']);qn=nom['q'];er=abs(q.c-qn)+q.radius();dq=np.linalg.norm(er);theta=4*np.arcsin(min(1.,dq/2))*180/np.pi
 Rzz=rotation(q)[8].bounds();tiltmax=np.degrees(np.arccos(np.clip(Rzz[0][0],-1,1)));loss=s['p'][2]-s['H0'];ll,lu=loss.bounds()
 return {'p_radius_m':float(np.linalg.norm(abs(p.c-nom['p'])+p.radius())),'v_radius_m_s':float(np.linalg.norm(abs(v.c-nom['v'])+v.radius())),'SO3_error_upper_deg':float(theta),'omega_radius_rad_s':float(max(abs(w.c-nom['w'])+w.radius())), 'tilt_upper_deg':float(tiltmax),'L_interval_m':[float(ll[0]),float(lu[0])],'generators':s['p'].ctx.n,'action_width_max':float(2*max(s['previous'].radius())),'h_radius_max':float(max(s['h'].radius()))}

def run(doc,P,scale,variant='joint',end=None):
 start=time.perf_counter();s,C,nav=initial(doc,scale);initial_n=C.n;i=doc['initial'];plan=doc['plan'];count=i['history_count'];index=i['call_index'];last_read=i['last_read_us'];stale=i['stale'];pending_msg=None;last_send=i.get('last_send_profile_s',-1e30);table=np.array(plan['profile']['table']);t0=i['profile_s'];nom={k:s[k].c.copy() for k in ['p','v','q','w']};rows=[];compressions=[];events=[];domain=None;precision=None;Dupper=0.;nomf=s['f'].c.copy();nompending=s['pending'].c.copy();nomphase=s['phi'].c.copy();capture_alias=[]
 horizon=plan['full_source_windows_profile_s'][0][1]+2 if end is None else end
 exact=forecast(doc,{},P,limit=horizon)
 for k in range(1,int(np.ceil((horizon-t0)/DT))+1):
  t=t0+k*DT;st=i['sample_us']+4000*k;now=i['native_us']+4000*k
  try:
   oldhat=normalize(qmul(s['align'],s['q']));s['fn']=filter_step(s['f'],s['pending']);p,v,q,w,phi=source(s);s.pop('fn');s.update(p=p,v=v,q=q,w=w,phi=phi,f=filter_step(s['f'],s['pending']))
   if k>=len(exact['states']):raise ValueError('independent point nominal left configured physical domain')
   row=exact['states'][k];nom={'p':row[:3],'v':row[3:6],'q':row[6:10],'w':row[10:13]}
   bn=(s['p']+mv(rotation(s['q']),C.constant(LEVER))).linear(nav);vnA=(s['v']+mv(rotation(s['q']),cross(s['w'],C.constant(LEVER)))).linear(nav);rho=np.exp(-DT/.25)
   ovn=vnA+rho*(s['ov']-s['bpold']);s['op']=bn+s['origin']+rho*(s['op']+.5*DT*(s['ov']+ovn)-bn-s['origin']);s['ov']=ovn;s['bpold']=vnA
   b0,b1,b2,a1,a2=coeff();d0=s['w']-a1*s['d1']-a2*s['d2'];s['gyro']=b0*d0+b1*s['d1']+b2*s['d2']+s['bias'];s['d2']=s['d1'];s['d1']=d0;s['att']=oldhat
   if (st-i['lp_phase_us'])%8000==0:s['lp']=s['op'];s['lv']=s['ov']
   inside=any(a<=t<b for a,b in plan['windows_profile_s'])
   if 0<=t<plan['stream_end_profile_s'] and not inside and t-last_send>=plan['publish_period_s']-1e-10:pending_msg=reference(t,plan['profile'],table);last_send=t
   commit=index%2==0;allowed=plan['p12_phase']==0 or plan['p12_phase']==1 and commit or plan['p12_phase']==2 and not commit
   was=stale
   if pending_msg is not None and allowed:
    s['r']=C.constant(np.asarray(pending_msg[0],np.float32).astype(float));s['rv']=C.constant(np.asarray(pending_msg[1],np.float32).astype(float));s['ty']=C.constant([float(np.float32(pending_msg[2]))]);last_read=now;pending_msg=None
   stale=last_read is None or now-last_read>200000
   resumed=was and not stale
   if stale and not was:
    s['r']=s['lp'].noise(np.full(3,1e-6));s['capture_p']=s['r'];s['rv']=C.constant([0.,0.,0.]);s['ty']=yaw(s['att']);events.append({'kind':'CAPTURE','t':t,'index':index});capture_alias.append({'t':t,'copied_generator_error':float(max((s['r']-s['capture_p']).radius()))})
   if resumed:events.append({'kind':'RESUME','t':t,'index':index})
   if plan['p12_repair']:raise ValueError('tube panel T0 only; repaired profile needs separate radial capture operator')
   cy=trig(s['ty'],'cos');sy=trig(s['ty'],'sin');z0=C.constant([0.]);frame=cat(cy,sy,z0,sy,-cy,z0,z0,z0,C.constant([-1.]))
   pe=mv(frame,s['lp']-s['r']).clip(.5);ve=mv(frame,s['lv']-s['rv']).clip(1.)
   targetq=cat(trig(.5*s['ty'],'cos'),z0,z0,trig(.5*s['ty'],'sin'));qr=s['att']*np.array([1,1,-1,-1]);orient=rotation(qmul(targetq,qr));s['mean']=count/(count+1)*s['mean']+1/(count+1)*s['previous'];x=cat(pe,orient,ve,s['gyro']*np.array([1,-1,-1]),s['mean'])
   hn,action=network(P,s['h'],x)
   if commit:s['h']=hn;count=0
   else:count+=1
   index+=1;s['previous']=action;s['pending']=150+425*(action[[0,2,3,1]]+1)
   mm0=metrics(s,nom);Dupper=max(Dupper,mm0['L_interval_m'][1]);mm0.update(t=t,call=k,D_upper_m=Dupper,phase='HOLD' if stale else 'FRESH',compression=None)
   if precision is None and (mm0['p_radius_m']>.1 or mm0['v_radius_m_s']>.15 or mm0['SO3_error_upper_deg']>2.5 or mm0['omega_radius_rad_s']>.1 or mm0['action_width_max']>.2):precision={'call':k,'t':t,'metrics':mm0.copy()}
   if C.n>2048 or variant=='box_each_call' or resumed and variant=='rebox_at_resume':
    s,co=compress(s,initial_n,24,variant=='box_each_call' or resumed and variant=='rebox_at_resume');C=s['p'].ctx
    if stale and variant=='joint':s['r']=s['capture_p']
    compressions.append({'t':t,**co});mm0['compression']=co
   rows.append(mm0)
   # Finite source domain is declared, not inferred from an observed maximum.
   vlim=max(abs(s['v'].c)+s['v'].radius());wlim=max(abs(s['w'].c)+s['w'].radius())
   if wlim>8 or vlim>8 or mm0['tilt_upper_deg']>80:domain={'t':t,'call':k,'reason':'outer tube no longer certified in predeclared finite source domain','not_actual_exit_proof':True};break
  except (ValueError,FloatingPointError,np.linalg.LinAlgError) as e:domain={'t':t,'call':k,'reason':str(e),'partial_state_preserved':True};break
 result={'scale':scale,'variant':variant,'start_t':t0,'planned_end_t':horizon,'last_completed_t':rows[-1]['t'] if rows else t0,'rows':rows,'events':events,'capture_alias':capture_alias,'first_precision_loss':precision,'first_domain_loss':domain,'successor':'TOP_OUTSIDE_DECLARED_DOMAIN' if domain else 'CONDITIONAL_JOINT_REGION','compression':compressions,'elapsed_s':time.perf_counter()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'initial_generators':initial_n,'final_generators':C.n,'full_EKF_or_actual_SERVO_certificate':False,'D_not_reset':True}
 return result,s
