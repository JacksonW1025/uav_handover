"""Known future inputs are explicit DIAGNOSTICS, never forecast inputs."""
import sys,json,importlib.util
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'data/p13-20261026-analysis-source')]
from p14.common import records,write,sha
from p14.model import observer_step
from p12c.features import load
from p12.state import EventTarget
from p11.observe import network
from source_discrete_kernel_v1 import audit as source_audit

def first(t,e,lim):
 j=np.flatnonzero(e>lim);return None if not len(j) else float(t[j[0]])

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);P=dict(np.load(ROOT/'data/p13-20261026-freeze/models/policy.npz'));rows=[]
 reps=json.load(open(ROOT/'config/p14-offline.json'))['diagnostic_representatives']
 for r in records():
  d=load(r['target']/'run',r['analysis']);doc=json.load(open(r['packed']/'prediction-input.json'));n=len(d['t']);h=d['h_before'][0].copy();prev=d['previous'][0].copy();mean=d['mean'][0].copy();count=int(d['count'][0]);ha=[];aa=[];xx=[]
  for k in range(n):
   mean=(mean*count+prev)/(count+1);x=np.r_[d['input'][k,:18],mean];hh,raw,a=network(P,h,x)
   if d['committed'][k]:h=hh
   count=0 if d['committed'][k] else count+1;prev=a;ha.append(h.copy());aa.append(a.copy());xx.append(x)
  eh=np.linalg.norm(np.array(ha)-d['h_after'],axis=1);ea=np.linalg.norm(np.array(aa)-d['action'],axis=1)
  target=EventTarget();target_errors=[];modes=[]
  for k in range(n):
   st=int(d['sample_us'][k]);now=int(d['native_us'][k]);target.repair=doc['plan']['p12_repair'] and st>=doc['plan'].get('repair_not_before_sample_us',0)
   msg=(d['external_p'][k],d['external_v'][k],float(d['external_yaw'][k])) if d['read_valid'][k] else None
   p,v,yaw,stale=target.step(now,st,d['position'][k],d['velocity'][k],d['attitude'][k],msg,activation=bool(d['activation'][k]))
   target_errors.append(max(abs(p-d['target_p'][k]).max(),abs(v-d['target_v'][k]).max()));modes.append(stale!=bool(d['stale'][k]))
  row={'id':r['id'],'group':r['group'],'D_known18_and_commit_only':{'rows':n,'h_L2_max':float(eh.max()),'action_L2_max':float(ea.max()),'first_h_over_p5':first(d['t'],eh,.5),'first_action_over_p1':first(d['t'],ea,.1),'continuous':True,'future_h_resets':False},
   'C_known_read_message_cache_clock':{'rows':n,'target_component_max':float(max(target_errors)),'stale_mismatch_n':int(sum(modes)),'first_target_error_over_p1':first(d['t'],np.array(target_errors),.1)},
   'future_inputs':'D: actual18D cache observations+commit word, h/previous/mean carried once; C: actual native/sample, valid messages and cache p/v/q; no causal attribution percentages'}
  if r['id'] in reps:
   rr=source_audit(r['target'],out/r['id']/'A-source',open_replay=True);row['A']=rr
   arrays=np.load(out/r['id']/'A-source/arrays.npz');ar=arrays['known_command_open'];t=arrays['profile_s'][:len(ar)]
   pe=np.linalg.norm(ar[:,:3]-arrays['COM_p_post'][:len(ar)],axis=1);ve=np.linalg.norm(ar[:,3:6]-arrays['COM_v_post'][:len(ar)],axis=1)
   from p11.models import tilt
   te=abs(ar[:,-1]-np.array([tilt(q) for q in arrays['body_q_post'][:len(ar)]]))
   row['A']['frozen_first_obvious']={'position10cm':first(t,pe,.1),'velocity15cm_s':first(t,ve,.15),'tilt5deg':first(t,te,5)}
   # Existing controlled kernel replacement order is independently re-evaluated
   # only on two representatives already within the fixed four-case panel.
   if r['id'] in ['dev01-F2-NORMAL','dev03-F4-AB']:
    from controlled_kernel_replays_v1 import run as controlled
    controlled(r['target'],out/r['id']/'A-replacement-order')
   # B: body-point driven complementary observer, future physical body and its
   # increments only. Actual LP initial origin is calibrated ONCE, no future LP.
   from p13.physics import read,BODY
   b,_=read(r['target']/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');b=b[b['phase']==1]
   ii=np.flatnonzero(d['t']>=0);j=np.searchsorted(b['wall_ns'],d['run_wall_ns'][ii],side='right')-1
   bz=-b['base_p'][j,2];bw=-b['base_v'][j,2];z=d['position'][ii[0],2];w=d['velocity'][ii[0],2];origin=z-bz[0];zs=[];ws=[]
   for k in range(len(ii)):
    if k:z,w=observer_step(z,w,bz[k],bw[k],bw[k-1],origin,dt=float(d['t'][ii[k]]-d['t'][ii[k-1]]))
    zs.append(z);ws.append(w)
   ez=np.asarray(zs)-d['position'][ii,2];ev=np.asarray(ws)-d['velocity'][ii,2]
   row['B_future_physical_body_observer']={'rows':len(ii),'z_max_m':float(max(abs(ez))),'v_max_m_s':float(max(abs(ev))),'first_z10cm':first(d['t'][ii],abs(ez),.1),'first_v15cm_s':first(d['t'][ii],abs(ev),.15),'input':'future directly observed base p/v; LP only at initial state, no LP future corrections','not_autonomous':True}
  write(out/r['id']/'layers.json',row);rows.append(row);print('LAYERS',r['id'],flush=True)
 write(out/'summary.json',{'schema':'p14-layer-diagnostics-1','rows':rows,'new_SITL':0,'candidate_parameters_unchanged':True,'injected_inputs_not_used_in_scores':True})
if __name__=='__main__':main()
