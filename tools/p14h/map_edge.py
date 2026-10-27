"""Explicit A→resume→recovery→B conditional point edge and successor connection.
The joint-set failure is delivered separately, never replaced by this point.
"""
import sys,json,copy,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p14h.selection import apply_parameters

def worker(out):
 from p14h.model import forecast
 out=Path(out);out.mkdir();tmp=out/'inputs';tmp.mkdir();shutil.copyfile(R/'data/p14r-20261027/offline-build-v2/libop.bin',tmp/'libop.bin');shutil.copyfile(B/'cadence-recovery-v2/cadence.bin',tmp/'cadence.bin');P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));rows=[]
 for n in range(1,5):
  d=apply_parameters(json.load(open(B/f'cadence-recovery-v2/d{n:02d}/input.json')),.36,.85,'BEFORE');a=d['plan']['windows_profile_s'][0][0];end=a+2.2;d['plan']['horizon_profile_s']=end;r=forecast(d,{},P,observer_library=tmp/'libop.bin',checkpoint_times=[a+.8]);cp=r['checkpoints'][0];nextdoc=copy.deepcopy(d);nextdoc['initial']=cp['initial'];tail=forecast(nextdoc,{},P,observer_library=tmp/'libop.bin');k=int(round((cp['actual_time']-d['initial']['profile_s'])/.004));diff=float(np.nanmax(abs(tail['trace']-r['trace'][k:])));assert diff<1e-10
  tr=r['trace'];s=r['states'];D=np.maximum.accumulate(np.maximum(s[:,2]-d['initial']['physical_H0_NED_z'],d['initial'].get('physical_D0_m',0)));np.savez_compressed(out/f'd{n:02d}.npz',trace=tr,states=s,D=D);write(out/f'd{n:02d}-successor.json',cp);events=[dict(kind='CAPTURE' if x['capture'] else 'RESUME',relative_call=j+1,profile_s=float(tr[j+1,0])) for j,x in enumerate(r['branches']) if x['capture'] or x['resume']];rows.append(dict(initial=f'd{n:02d}',declared_model='H1 conditional causal source observer + source moving physics',events=events,stop=r['stop'],connected_tail_max_error=diff,successor_file=f'd{n:02d}-successor.json',all_prefix_tilt_margin_deg=float(45-max(tr[:,7])),all_prefix_COM_height_margin_m=float(1-max(D)),D_monotone=True,successor_history_clock_pending_and_producer_retained=True,point_depth_capture_count=sum(x['kind']=='CAPTURE' for x in events),joint_depth='see actual eight-fiber sets-AB-v1, no point-to-region promotion'))
 write(out/'edge.json',dict(schema='P14H-map-edge-1',input={'mode':'NEURAL_ACTIVE, RINI/history not reset','initial':'four sourced diagnostic points, source covariance snapshot separate; genuine old G union sets are independent panel','event':'A gap .36, recovery .85, B gap .36; BEFORE source read policy','timing':'nominal 4ms, source recovered downsample phase, latest pending slot; PRE_COMPLETE producer conditional','model_error':'future aiding/producer branches and floating/geodesy/servo error not certified'},output={'rows':rows,'point_successor_reusable':True,'joint_successor':'UNKNOWN/TOP after first original-domain loss, no complete event certificate','full_prefix_margins':'nominal point only; negative is modeled witness, not universal danger'},storage={'scope':'H0 nominal fixed-branch linearization; H1 new producer connection requires an additional mode/error relation','formula':'Qpre[k]=Jk^T(Cpostk^T Cpostk+Qpre[k+1])Jk; W=e^T Qpre e. sqrt(Wnext)<=sqrt(e^T J^T Pnext J e)+||Pnext^.5 r||','copy_or_jump':'e+=S_m e-+j_m dt+r_m; any seminorm-only reuse requires ker(P-) subset ker(P+^.5 S_m), otherwise retain the full joint successor','remaining_obligations':'nonlinear remainder and future EKF/queue mode budget not certified; Jacobian energy identity is not a nonlinear safety proof'},analysis_result='conditional point composition verified, true joint-domain full event still not covered; no false safe/danger label'))
 print('POINT_MAP',[(r['initial'],r['point_depth_capture_count'],r['connected_tail_max_error']) for r in rows])
if __name__=='__main__':
 if sys.argv[1]=='worker':worker(sys.argv[2])
 else:
  out=register(sys.argv[1],'explicit true AB and reusable point successor, separate from original joint-set failure',CPU_cap=60);run([PY,Path(__file__),'worker',out/'result'],out/'worker',cpu=60,wall=90,scope='conditional map point composition, separate model coverage obligations')
