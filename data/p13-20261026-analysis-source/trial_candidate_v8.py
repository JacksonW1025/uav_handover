import json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from p13.physics import read,BODY,rot
from model_working_v8 import forecast
from open_plant_v1 import S,B,matrix
from p9_model import write

def packed(target):
 doc=json.load(open(target/'analysis-v1/packed/prediction-input.json'));man=json.load(open(target/'analysis-v1/packed/manifest.json'));b,_=read(target/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');cutoff=min(man['initial_cutoff_host_ns'],man['initial_max_host_ns']);valid=b[(b['phase']==1)&(b['valid']==63)&(b['wall_ns']<cutoff)];x=valid[-1];q=Rotation.from_matrix(S@rot(x['base_q'][None,:])[0]@B).as_quat()[[3,0,1,2]];doc['initial'].update(physical_COM_p=(S@x['com_p']).tolist(),physical_COM_v=(S@x['com_v']).tolist(),physical_q=q.tolist(),physical_omega=(matrix(q).T@S@x['base_omega']).tolist(),COM_to_origin_body=(matrix(q).T@S@(x['origin_p']-x['com_p'])).tolist(),physical_sample_us=int(x['sim_ns']//1000),physical_host_age_us=(cutoff-int(x['wall_ns']))/1000)
 return doc
if __name__=='__main__':
 target=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False);doc=packed(target);write(out/'prediction-input.json',doc);P=dict(np.load(R/'data/p12-cont-20261026-freeze/models/policy.npz'));r=forecast(doc,json.load(open(R/'data/p12-cont-20261026-freeze/models/models.json'))['M2'],P);tr=r.pop('trace');nt=r.pop('native_us');write(out/'prediction.json',r);np.savez_compressed(out/'M5.npz',trace=tr,native_us=nt);print(target.name,tr.shape,'stop',r['stop'],'peak',float(tr[:,7].max()),'zloss',float(tr[:,3].max()-tr[0,3]))
