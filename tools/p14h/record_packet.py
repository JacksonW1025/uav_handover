"""Past-cut initial reconstruction recipe frozen before independent evaluation.
Recovers decision/timestamp projection only; aiding payloads are not invented.
"""
import sys,json,base64,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from pyulog import ULog
from p14h.common import *
from p14h.adapt_initial import adapt
from p14h.cadence import Cadence
from p14r.observer import read,CORE,FUSION

def packet(target,review,out):
 target=Path(target).resolve();review=Path(review).resolve();out=Path(out);out.mkdir(parents=True,exist_ok=False);info=json.load(open(target/('information-v2.json' if (target/'information-v2.json').exists() else 'information.json')));analysis=R/info['source_analysis'] if info.get('source_analysis') else target/'analysis-v1';d,proof=adapt(json.load(open(review/'source-initial/input.json')),target/'run',analysis);i=d['initial'];cut=i['observer']['cutoff_wall_ns'];lib=B/'cadence-recovery-v2/cadence.bin';core,h=read(target/'run/gz-motor/observer-core.bin',CORE,b'P14RCORE',True);assert h['dropped']==h['errors']==0
 pre=core[(core['kind']==1)&(core['wall_ns']<=cut)];u=ULog(str(target/'run/flight.ulg'),[]);target_us=int(u.initial_parameters['EKF2_PREDICT_US']);assert not any(k=='EKF2_PREDICT_US' for _,k,v in u.changed_parameters);cad=Cadence(lib,target_us);pred=[]
 for x in pre:
  if cad.push(x['data'][70]):pred.append(int(x['sample_us']))
 fu,h=read(target/'run/gz-motor/observer-fusion.bin',FUSION,b'P14RFUS1',True);assert h['dropped']==h['errors']==0;f=fu['core'][(fu['core']['kind']==3)&(fu['core']['wall_ns']<=cut)];actual=f['ids'][:,0].astype(np.int64);lo=int(actual[0])+1000000;observed={int(x) for x in actual if int(x)>=lo};guessed={x for x in pred if x>=lo};extra=guessed-observed;pending=int(pre[-1]['sample_us']) in extra;assert not observed-guessed;assert not extra-{int(pre[-1]['sample_us'])};N=int(np.frombuffer(base64.b64decode(i['observer']['fusion_base64']),FUSION,count=1)[0]['core']['ids'][2]);queue=[x for x in pred if not(pending and x==int(pre[-1]['sample_us']))][-N:];assert queue[0]==int(f[-1]['sample_us'])
 i['p14h_schedule_model'].update(downsampled_time_queue=queue,imu_queue_length=N,cadence_state=cad.dump(),cadence_target_us=target_us,last_IMU_dt_s=float(pre[-1]['data'][70]),pending_fusion_after_snapshot=pending,cadence_library_sha256=sha(lib),cadence_scope='decision and timestamp queue only; observed FUSION_PRE starts, pending completion is explicit nominal conditional mode; aiding/auxiliary states not restored')
 write(out/'input.json',d);write(out/'proof.json',dict(**proof,actual_fusion_starts=len(observed),predicted_yields=len(guessed),finite_prefix_membership_exact=True,current_downsample_yield_pending_fusion_start=pending,full_EKF_restored=False,physical_future_used=False,input_sha256=sha(out/'input.json'),role='frozen recipe evaluated after flight from pre-A past prefix; not task0 prospective initial measurement'))
 return d,analysis

if __name__=='__main__':packet(sys.argv[1],sys.argv[2],sys.argv[3])
