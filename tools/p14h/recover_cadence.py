"""Recover source IMU downsample decision state fromall knownpre-cut core rows."""
import sys,json,subprocess,base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from pyulog import ULog
from p14h.common import *
from p14r.observer import read,CORE,FUSION
from p14h.cadence import Cadence

def main():
 out=register(sys.argv[1],'recover decision-onlyImuDownSampler fromsource ctor +allrecordedIMUdt, verifyactualyield membership; futureonlynominaldt',no_new_data=True);lib=out/'cadence.bin';cmd=['g++','-std=c++17','-O2','-fno-associative-math','-fno-signed-zeros','-shared','-fPIC',str(R/'tools/p14h/cadence.cpp'),'-o',str(lib)];subprocess.run(cmd,check=True);rows=[]
 for n in range(1,5):
  target=next((B/'runs').glob(f'p14h-d{n:02d}-*'));doc=json.load(open(B/'causal-initials-v1'/f'd{n:02d}/input.json'));i=doc['initial'];cut=i['observer']['cutoff_wall_ns'];core,_=read(target/'run/gz-motor/observer-core.bin',CORE,b'P14RCORE',True);pre=core[(core['kind']==1)&(core['wall_ns']<=cut)];u=ULog(str(target/'run/flight.ulg'),[]);predict=int(u.initial_parameters['EKF2_PREDICT_US']);assert not any(k=='EKF2_PREDICT_US' for _,k,v in u.changed_parameters);cad=Cadence(lib,predict);pred=[]
  for x in pre:
   if cad.push(x['data'][70]):pred.append(int(x['sample_us']))
  fu,_=read(target/'run/gz-motor/observer-fusion.bin',FUSION,b'P14RFUS1',True);f=fu['core'][(fu['core']['kind']==3)&(fu['core']['wall_ns']<=cut)];actual=f['ids'][:,0].astype(np.int64);start=int(actual[0])+1000000;observed=set(int(t) for t in actual if start<=int(t)<=int(pre['sample_us'][-1]));guessed=set(t for t in pred if t>=start);missing=sorted(observed-guessed);extra=sorted(guessed-observed);pending=int(pre['sample_us'][-1]) in extra;extra_completed=[t for t in extra if t!=int(pre['sample_us'][-1])];N=int(np.frombuffer(base64.b64decode(i['observer']['fusion_base64']),FUSION,count=1)[0]['core']['ids'][2]);completed=[t for t in pred if not (pending and t==int(pre['sample_us'][-1]))];timequeue=completed[-N:];assert timequeue[0]==int(f[-1]['sample_us']);i['p14h_schedule_model'].update(downsampled_time_queue=timequeue,imu_queue_length=N,cadence_state=cad.dump(),cadence_target_us=predict,last_IMU_dt_s=float(pre[-1]['data'][70]),pending_fusion_after_snapshot=pending,cadence_library_sha256=sha(lib),cadence_scope='decisionprojectionrecovered, finite actualprecutmatch; fullauxEKF/aidingqueues notrestored; currentcallbackcompletionnominal beforefirstfutureread');write(out/f'd{n:02d}/input.json',doc);row={'case':n,'precut_IMU_rows':len(pre),'source_ctor_avg_s':.005,'target_parameter_us':predict,'actual_fusion_after_first1s':len(observed),'predicted_yields':len(guessed),'actual_not_predicted':missing,'predicted_no_completed_fusion_except_current':extra_completed,'current_callback_pending_fusion':pending,'current_OP_sample':int(pre['sample_us'][-1]),'last_actual_completed_fusion_sample':int(actual[-1]),'state':cad.dump(),'finite_projection_verified':not missing and not extra_completed,'future_dt_assumption':'actualphysics4ms, predictedIMUdt.004f, future coalescing remains separatelegalbranch'};rows.append(row)
 write(out/'result.json',{'rows':rows,'all_finite_prefixes_match':all(x['finite_projection_verified'] for x in rows),'source_definition':'ImuDownSampler update/reset predicate .9avg+.1dt and roundf(target/avg); 10000us parameter doesnot implyfixed10ms or4msmap','library_sha256':sha(lib),'not_full_EKF_restore':True});print('CADENCE_RECOVERY',[(r['case'],r['finite_projection_verified'],len(r['actual_not_predicted']),len(r['predicted_no_completed_fusion_except_current']),r['current_callback_pending_fusion']) for r in rows])
if __name__=='__main__':main()
