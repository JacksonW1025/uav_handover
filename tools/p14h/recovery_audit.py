"""Try reset-history recovery from existing complete sources; report exact gap."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from pyulog import ULog
from p14h.common import *
from p14r.observer import read,CORE,FUSION

def main():
 out=register(sys.argv[1],'A: offline reset/aiding history and fullP recoverability before any newSITL');limit(30);rows=[]
 cases=json.load(open(R/'config/p14h/protocol-v1.json'))['cases']
 for n,c in cases.items():
  run=R/c['raw_run'];u=ULog(str(run/'flight.ulg'),['estimator_states','vehicle_imu','sensor_combined','sensor_gps','vehicle_gps_position','sensor_baro','sensor_mag','estimator_status_flags','estimator_sensor_bias']);core,ch=read(run/'gz-motor/observer-core.bin',CORE,b'P14RCORE',True);fu,fh=read(run/'gz-motor/observer-fusion.bin',FUSION,b'P14RFUS1',True);res=core[core['kind']>=10];first_fusion=int(fu['core']['native_us'][0]);topics={x.name:{'first_native':int(x.data['timestamp'][0]),'rows':len(x.data['timestamp']),'fields':list(x.data)} for x in u.data_list};states=next(x.data for x in u.data_list if x.name=='estimator_states');diag=[k for k in states if k.startswith('covariances[')];record={'id':n,'ULog_start_native':u.start_timestamp,'first_recorded_OP_fusion_native':first_fusion,'first_recorded_OP_core_native':int(core['native_us'][0]),'reset_events_native':[(int(x['kind']),int(x['native_us'])) for x in res[:20]],'topics':topics,'covariance_fields':diag,'complete_P_recorded':False,'reset_replay_attempt':'enumerated logged resets, sample/aiding topic coverage and state covariance fields; no hidden initialP or queue fabricated','full_EKF_bootstrap_status':'UNKNOWN_INITIAL_P_AND_AIDING_QUEUES','reason':'OP reset/align snapshot belongs to output predictor; not EKF covariance/auxiliary reset. ULog begins after earliest core/fusion; full aiding reception/consumption order and crossP absent. Nominal25/diagonal24 do not identify fullP. Cannot certify source bootstrap by injecting logged nominal/diagonal.','recoverable_now':['fullOPbuffer/integrals andsourceknowninput continuousreplay','gyroDFII+actualbias','NN/history/read/commit replay','directphysics+filter/joint'],'minimal_missing_snapshot':['full crossP and nominal fusedstate atsamepostEKFupdate','latestIMU anddelayedsample identities, controlflags','remainingunclosed: aidingqueues/auxfilters/reset context, notsilentlydeclaredrecovered']};rows.append(record)
 write(out/'result.json',{'rows':rows,'new_recording_justified':'bounded passive fullP/nominal/time/IMU/flags snapshot adds exactly missingobservable, doesnotclaimfullEKFrestorable; source OP traces reused','no_diagonal_as_fullP':True,'original_smallinnovation_budget_rejected':True,'future_actual_only_diagnostic':True})
 print('RECOVERY_AUDITED',len(rows),'fullEKF UNKNOWN, OP/localchainsavailable')
if __name__=='__main__':main()
