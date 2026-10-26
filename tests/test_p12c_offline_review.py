"""Independent stopped-delivery fixes/theory checks; no runtime or flight change."""
import sys,importlib.util
from pathlib import Path
from fractions import Fraction as F
import numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
D=R/'data/p12c-20261026-analysis-source'
def module(name):
 spec=importlib.util.spec_from_file_location(name,D/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_missing_resume_cannot_pass_a_complete_event_as_empty_timing():
 m=module('completeness_review')
 for cap,res in [(None,None),(1.2,None),(None,2.01)]:assert m.classify(20,1,2,cap,res)['status']=='FAIL_MISSING_EXPECTED_WITNESS'
 assert m.classify(20,1,2,1.2,2.01)['status']=='PASS'
 assert m.classify(1.8,1,2,1.2,None)['status']=='NOT_REACHED_OR_RIGHT_CENSORED'


def test_source_servo_inverse_is_exact_for_every_rhs_basis():
 m=module('finite_execution_domain');s=m.source_domain();a=1/F(s['rotor_Izz_kg_m2_exact']);k=1/F(s['yaw_free_effective_inertia_exact']);c=F('1e-9');d=a+c*(a+k);A=[[d*(i==j)+k for j in range(4)] for i in range(4)];B=[[(F(i==j)/d)-k/(d*(d+4*k)) for j in range(4)] for i in range(4)]
 assert all(sum(A[i][l]*B[l][j] for l in range(4))==int(i==j) for i in range(4) for j in range(4))
 assert s['max_collision_radius_m']<s['finite_working_domain']['world_model_origin_H_m'][0]
 assert 'NOT_PROVEN' in s['finite_working_domain']['unknown_invariance']


def test_full_prefix_failure_is_not_erased_by_endpoint_height_or_capture():
 m=module('conditional_maps');L,W,D0=m.flow('.9',1,'.9',2,-1)
 assert L==F('.9') and D0==F('1.4')
 assert m.flow(L,W,D0,0,0)==(L,W,D0)
 assert m.flow(L,W,D0,1,0)[2]==D0
 t,loss=m.recovery_requirement('.98',1);assert t==F('.98') and loss==F('.4802')


def test_COM_geometry_velocity_sign_matches_height_derivative():
 from p3_memory import rotation
 r=.24186913101803548;theta=.3;rate=.4;dt=1e-6
 q=lambda x:np.array([np.cos(x/2),0,np.sin(x/2),0]);M=rotation(q(theta)).reshape(3,3)
 analytic=r*M[2,0]*rate;fd=r*(rotation(q(theta+rate*dt)).reshape(3,3)[2,2]-M[2,2])/dt
 assert abs(analytic-fd)<1e-7 and analytic<0
 # H_model=H_COM-rR33, therefore W_model=W_COM+d(rR33)/dt.


def test_completed_engineering_stop_cannot_implicitly_resume():
 from p12c_platform.campaign import baseline
 import pytest
 with pytest.raises(RuntimeError,match='engineering queue is stopped'):baseline()
