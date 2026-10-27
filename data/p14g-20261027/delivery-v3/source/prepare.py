"""Only past error samples; future fusion/sensors never enter initial packets."""
import sys,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.spatial.transform import Rotation
from p14g.common import *
from p14r.observer import read,FUSION
from p13.physics import read as pread,BODY,rot
from p13.physical_model import S,B as BODYB
from p14r.op import Op
from p14_motion.core import LEVER,mul,conjugate

def main():
 out=Path(sys.argv[1]);register(out,'C: source fusion recurrence and a past-only fading error-rate conditional proxy');rows=[]
 for name in cases():
  d=doc(name);i=d['initial'];cut=i['observer']['cutoff_wall_ns'];run=R/cases()[name]['raw_run'];f,_=read(run/'gz-motor/observer-fusion.bin',FUSION,b'P14RFUS1',True);f=f[(f['core']['kind']==4)&(f['core']['wall_ns']<=cut)];assert len(f)>=2;two=f[-2:];phy,_=pread(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');phy=phy[(phy['phase']==1)&(phy['valid']==63)&(phy['wall_ns']<=cut)];lookup={int(r['sim_ns']//1000):r for r in phy};errors=[];lib=OLD/'offline-build-v2/libop.bin';op=Op(lib,i['observer'])
  for row in two:
   r=row['core'];t=int(r['sample_us']);x=lookup[t];M=S@rot(x['base_q'][None,:])[0]@BODYB;q=Rotation.from_matrix(M).as_quat()[[3,0,1,2]];w=M.T@S@x['base_omega'];p=S@x['com_p']+M@LEVER;v=S@x['com_v']+M@np.cross(w,LEVER);eq=mul(r['data'][64:68],conjugate(q));theta=Rotation.from_quat(eq[[1,2,3,0]]).as_rotvec();ev=r['data'][68:71]-v;ep=op.sub(r['geo'][3:6],op.add(i['observer_parameters']['world_geo'],p));errors.append({'sample_us':t,'theta':theta,'velocity':ev,'position':ep})
  dt=(errors[1]['sample_us']-errors[0]['sample_us'])*1e-6;assert dt>0;rates={k:((errors[1][k]-errors[0][k])/dt).tolist() for k in ['theta','velocity','position']};tau=float(two[-1]['core']['data'][37]);assert .008<=tau<=10
  i['p14g_innovation']={'mode':'fading','tau_s':tau,'rates':rates,'past_delayed_sample_us':errors[-1]['sample_us'],'condition':'last two past fused-target residual slopes, decaying with source OP velocity tau as a proxy; NOT an EKF future-error theorem'};write(out/name/'input.json',d);row={'id':name,'past_fusion_wall_ns':[int(x['core']['wall_ns']) for x in two],'cutoff_wall_ns':cut,'tau_source_s':tau,'slope_interval_s':dt,'rates':rates,'input_sha256':sha(out/name/'input.json'),'rate_is_certified_future_bound':False};rows.append(row);op.close()
 write(out/'summary.json',{'rows':rows,'future_data_used':False,'core_source':'OP vi+=error; correction=gain*error+.1*gain²*vi. No source relation bounds arbitrary future EKF target innovation; fading derivative is a conditional model.'})
if __name__=='__main__':main()
