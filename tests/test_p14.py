import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from p14.model import body_point,observer_step,BODY_LEVER
from p11.models import R
from p12.score import bundle

def test_body_lever_is_not_named_model():
 assert BODY_LEVER[2]<.002
 q=np.array([np.cos(.4),np.sin(.4),0,0]);w=np.array([1.,0,0])
 z,v=body_point(-3,.2,q,w)
 assert abs(z+3-(R(q)@BODY_LEVER)[2])<1e-15
 assert abs(v-.2-(R(q)@np.cross(w,BODY_LEVER))[2])<1e-15

def test_observer_preserves_physical_velocity_increment():
 z,v=observer_step(-3,0,-2.9996,.1,0,0)
 assert v==.1

def test_observer_error_is_dynamic_not_constant():
 _,v=observer_step(-3,.1,-3,0,0,0)
 assert 0<v<.1

def test_observer_origin_is_separate():
 z,v=observer_step(-2,0,-3,0,0,1)
 assert z==-2 and v==0

def test_unknown_never_hides_witness():
 r=bundle(46,None,False,46,0,True)
 assert r['predicted']['tilt']=='FAILURE' and r['predicted']['height']=='UNKNOWN'
 assert r['comparisons']['task']=='AGREEMENT'

def test_safe_incomplete_cannot_be_success():
 r=bundle(40,.1,False,46,.1,False)
 assert r['predicted']['task']=='UNKNOWN'
 assert r['comparisons']['tilt']=='UNKNOWN_PREDICTION_TRUNCATED'

def test_shared_capture_cancels_in_affine_map():
 from p14.affine import Context
 c=Context();p=c.variable([2.],.1);r=p
 assert (p-r).radius()[0]<1e-12

def test_analytic_nonlinear_affine_enclosure():
 from p14.affine import Context
 for center,rad in [(0,.001),(.2,.8),(-3,1),(3,4)]:
  for kind in ['sigmoid','tanh']:
   x=Context().variable([center],rad);y=x.smooth(kind);lo,hi=y.bounds()
   points=np.linspace(center-rad,center+rad,100)
   truth=np.tanh(points) if kind=='tanh' else 1/(1+np.exp(-points))
   assert truth.min()>=lo[0] and truth.max()<=hi[0]

def test_product_remainder_and_clip_enclose():
 from p14.affine import Context
 c=Context();x=c.variable([.3],.5);y=c.variable([-.1],.8)
 lo,hi=(x*y).bounds();assert lo<=-.72 and hi>=.56
 lo,hi=x.clip(.4).bounds();assert lo<=-.2 and hi>=.4

def test_exact_height_prefix_not_only_endpoint():
 from p14.height import map_prefix,calculate
 from fractions import Fraction as F
 x=map_prefix(F(3,10),F(8,10),F(4,10),F(1),500)
 assert x['D_upper']>x['L_upper'] and x['D_upper']<F(1)
 assert x['W_upper']<0
 assert calculate()['future_hard_actual_certificate'] is False
