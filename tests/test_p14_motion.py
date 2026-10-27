import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from p14_motion.core import coeff,biquad,forecast
from p14_motion.algebra import Context,qexp,rotation,compress
from p14_motion.tube import run

def test_biquad_dc_and_dynamic_state():
 b0,b1,b2,a1,a2=coeff();v=np.array([.1,.2,-.3]);d1=v/(1+a1+a2);d2=d1.copy();y,_,_=biquad(v,d1,d2)
 assert np.max(abs(v-y))<1e-15
 y1,_,_=biquad(v,np.zeros(3),np.zeros(3));assert np.linalg.norm(y1-v)>.1

def test_rotation_group_moves_without_freezing():
 x=Context().variable([.004,.002,-.001],1e-7);q=qexp(x,group=True);lo,hi=q.bounds()
 a=np.linalg.norm(x.c);truth=np.r_[np.cos(a/2),x.c*np.sin(a/2)/a]
 assert np.all(truth>=lo) and np.all(truth<=hi)
 assert np.linalg.norm(truth[1:])>0

def test_direction_compression_contains_original_generators():
 C=Context();a=C.variable([0.,0.,0.],.01);b=a.linear(np.array([[1,2,3],[2,-1,4.]]));state={'p':a,'v':b};old={k:v for k,v in state.items()};new,proof=compress(state,0,-2)
 rng=np.random.default_rng(123)
 # Containment sampling is implementation validation, not the proof: selected
 # original columns plus rowL1 residual bound is analytic.
 for _ in range(20):
  z=rng.uniform(-1,1,old['p'].g.shape[1]);p=old['p'].c+old['p'].g@z;lo,hi=new['p'].bounds();assert np.all(p>=lo) and np.all(p<=hi)

def test_zero_radius_source_nominal_is_contained_after_two_calls():
 inp=ROOT/'data/p14-motion-20261027/inputs-v3/p13-F2-b1-AB-short/edge-input.json'
 doc=json.load(open(inp));P=dict(np.load(ROOT/'data/p13-20261026-freeze/models/policy.npz'));end=doc['initial']['profile_s']+.008
 result,s=run(doc,P,0,end=end,compress_rank=None,group=True)
 n=len(result['rows']);nom=forecast(doc,{},P,limit=end);tr=nom['trace'][n];st=nom['states'][n]
 expected={'p':st[:3],'v':st[3:6],'q':st[6:10],'w':st[10:13],'phi':st[13:17],'d1':st[17:20],'d2':st[20:23],'gyro':st[23:26],'op':st[26:29],'ov':st[29:32],'mean':st[32:36],'h':tr[12:28],'previous':tr[8:12],'f':tr[54:58],'lp':tr[42:45],'lv':tr[45:48],'att':tr[48:52]}
 for k,x in expected.items():
  lo,hi=s[k].bounds();assert np.all(x>=lo) and np.all(x<=hi),(k,x,lo,hi)
 assert result['initial_D0_m']==doc['initial']['physical_D0_m']
 assert result['H0_NED_z']==doc['initial']['physical_H0_NED_z']

def test_capture_shared_origin_does_not_reintroduce_position_uncertainty():
 C=Context();p=C.variable([0,0,-3],.01);r=p.noise(np.full(3,1e-6));difference=r-p
 assert max(difference.radius())<1.000001e-6

def test_log_chart_uses_moving_center_and_bounded_remainder():
 from p14_motion.assemble import local_region
 angle=.3;q0=np.array([np.cos(angle/2),np.sin(angle/2),0,0]);epsilon=1e-5
 doc={'q_center':q0,'q_generators':np.eye(4)*epsilon}
 local,claim=local_region(doc,q0)
 assert claim['positive_quaternion_chart']
 assert np.max(abs(local['local_SO3_center']))<1e-14
 assert claim['nonlinear_component_remainder_rad']>0

def test_map_keeps_global_height_history_and_conditions():
 p=ROOT/'data/p14-motion-20261027/delivery-v5/map-edge.json'
 doc=json.load(open(p));assert doc['input']['historical_D0_m']>0
 assert not doc['edge_composition']['B_capture_enclosed']
 assert doc['output']['stages']['resume_plus_p5']['prefix_margin']['height_margin_m']>0
 assert doc['output']['full_requested_2s_recovery']=='NOT_ENCLOSED'

def test_serialized_successor_restores_queue_clocks_and_D_relation():
 from p14_motion.complete_edge import discrete
 edge=json.load(open(ROOT/'data/p14-motion-20261027/delivery-v6-edge/map-edge.json'))
 doc=json.load(open(ROOT/edge['input']['initial']))
 for x in edge['output']['stages'].values():
  d=discrete(doc,x['metrics']['call']);assert d==x['successor_discrete']
  assert 'target_pending_slot' in d and 'last_send_profile_s' in d
  assert d['next_call_commit']==(d['index']%2==0)
  history=x['history_D_outer_relation'];assert history['interval_m'][1]>=max(0,x['metrics']['L_interval_m'][1])-1e-10
  assert 'full past-max generator correlation NOT retained' in history['representation']
