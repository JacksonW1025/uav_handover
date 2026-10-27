import sys,json,time,resource
from pathlib import Path
import numpy as np
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
from p14r.affine import install
from p14r import tube
from p14r.algebra import rotation
job=json.load(open(sys.argv[1]));out=Path(sys.argv[2]);out.mkdir();install(job.get('quadratic',False));doc=json.load(open(R/job['input']));other=json.load(open(R/job['joint_input'])) if job.get('joint_input') else None;old=tube.metrics;LPD=[doc['initial'].get('LP_D0_m',0)]
def rich(s,nom):
 r=old(s,nom);r['center_defect_vs_float_source_nominal']={key:float(max(abs(s[key].c-nom[key]))) for key in ['p','v','q','w']};r['row_radius_only']={key:float(max(s[key].radius())) for key in ['p','v','q','w','h','previous']};r['W_COM_down_interval']=s['v'][2].bounds()[0].tolist()+s['v'][2].bounds()[1].tolist();lp=s['lp'][2]-doc['initial'].get('LP_H0_NED_z',doc['initial']['position'][2]);l,u=lp.bounds();LPD[0]=max(LPD[0],u[0]);r['LP_L_interval_m']=[float(l[0]),float(u[0])];r['LP_D_upper_m']=float(LPD[0]);r['cache_tilt_upper_deg']=float(np.degrees(np.arccos(np.clip(rotation(s['att'])[8].bounds()[0][0],-1,1))));return r
tube.metrics=rich;P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));end=doc['initial']['profile_s']+job.get('horizon_s',2)
result,s=tube.run(doc,P,job.get('scale',0),end=end,group=True,compress_rank=job.get('compress_rank',-512),observer_library=R/'data/p14r-20261027/offline-build-v2/libop.bin',joint_doc=other,joint_segment=job.get('segment',(0,1)));result['tag_interpretation']='round_libm is propagated algorithmic gamma/assumed-libm budget; not certified true source float32 rounding and not actual physical uncertainty. center_defect records declared real NED chart vs float source point separately.';write(out/'result.json',result);print(len(result['rows']),result['elapsed_s'],result['first_precision_loss'],flush=True)
