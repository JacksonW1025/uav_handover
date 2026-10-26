#!/usr/bin/env python3
"""Past-only direct COM state, with source/time manifest separate from blind input."""
import json,sys,shutil
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p13.physics import read,BODY,rot
from p11.models import R as matrix
from p9_model import write,sha
S=np.array([[0,1,0],[1,0,0],[0,0,-1]]);B=np.diag([1,-1,-1])
def create(run,base,out):
 out.mkdir(parents=True,exist_ok=False);doc=json.load(open(base/'prediction-input.json'));man=json.load(open(base/'manifest.json'));cutoff=min(man['initial_cutoff_host_ns'],man['initial_max_host_ns'])
 body_path=run/'gz-motor/physics-p13-body.bin';b,h=read(body_path,BODY,b'P13BODY1')
 if h['complete']!=1 or h['dropped'] or h['errors']:raise RuntimeError('physical buffer incomplete')
 eligible=np.flatnonzero((b['phase']==1)&(b['valid']==63)&(b['wall_ns']<cutoff))
 if not len(eligible):raise RuntimeError('no known physical COM initial state')
 i=int(eligible[-1]);x=b[i];q=Rotation.from_matrix(S@rot(x['base_q'][None,:])[0]@B).as_quat()[[3,0,1,2]]
 doc['initial'].update(physical_COM_p=(S@x['com_p']).tolist(),physical_COM_v=(S@x['com_v']).tolist(),physical_q=q.tolist(),physical_omega=(matrix(q).T@S@x['base_omega']).tolist(),COM_to_origin_body=(matrix(q).T@S@(x['origin_p']-x['com_p'])).tolist(),physical_sample_us=int(x['sim_ns']//1000),physical_host_age_us=(cutoff-int(x['wall_ns']))/1000)
 doc['schema']='p13-past-only-input-1';write(out/'prediction-input.json',doc);shutil.copyfile(base/'measurement.npz',out/'measurement.npz')
 write(out/'manifest.json',dict(man,schema='p13-packing-1',base_input_sha256=man['input_sha256'],input_sha256=sha(out/'prediction-input.json'),physical_source_sha256=sha(body_path),physical_row=i,physical_step=int(x['step']),physical_sim_ns=int(x['sim_ns']),physical_host_ns=int(x['wall_ns']),cutoff_host_ns=cutoff,initial_state_scope='actual COM p/v/q/omega and named-origin relation direct and before cutoff; controller and physical initial times remain asynchronous, not exact snapshot fork; M5 inherits empirical angular/horizontal/cache closure; rotor filter direct, no steady command initialization'))
 return doc
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();create(a.run,a.base,a.output)
