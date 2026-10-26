import sys,struct
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from p13.physics import BODY,ROTOR,HEAD,read,rot
from p13.campaign import claim

def test_partial_physical_buffer_not_accepted(tmp_path):
 p=tmp_path/'body.bin';p.write_bytes(HEAD.pack(b'P13BODY1',1,BODY.itemsize,100,1,0,0,0))
 with pytest.raises(ValueError,match='truncated'):read(p,BODY,b'P13BODY1')

def test_physical_buffer_explicit_invalid_not_zero_inferred(tmp_path):
 p=tmp_path/'body.bin';a=np.zeros(2,BODY);a['valid']=[0,63]
 p.write_bytes(HEAD.pack(b'P13BODY1',1,BODY.itemsize,2,2,7,0,1)+a.tobytes())
 b,h=read(p,BODY,b'P13BODY1');assert h['dropped']==7 and b['valid'].tolist()==[0,63]

def test_rotation_and_COM_cross_term():
 q=np.array([[np.cos(.3),np.sin(.3),0,0]])
 M=rot(q)[0];r=M@np.array([0.,0.,.241869131018]);w=np.array([1.,2.,3.]);assert np.linalg.norm(np.cross(w,r))>.1
 assert np.allclose(M@M.T,np.eye(3),atol=1e-15)

def test_budget_failed_start_still_counts():
 rows=[{'event':'START_INTENT','id':str(i),'budget_class':'development'} for i in range(12)]
 with pytest.raises(RuntimeError,match='cap'):claim(rows,'new','development')
 with pytest.raises(RuntimeError):claim(rows,'0','development')
 assert claim(rows,'formal0','formal')==13
