"""What a full source EKF replay would still need; no collection performed."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from pyulog import ULog
from p14g.common import *
def main():
 out=Path(sys.argv[1]);register(out,'existing aiding/state availability and covariance identifiability example, no newrecording');limit(10);rows=[]
 names=['estimator_states','estimator_innovations','estimator_status','estimator_status_flags','sensor_gps','vehicle_gps_position','vehicle_imu','sensor_combined','sensor_baro','sensor_mag']
 for n,c in cases().items():
  u=ULog(str(R/c['raw_run']/'flight.ulg'),names);topics={x:{'rows':0,'fields':[]} for x in names}
  for d in u.data_list:topics[d.name]={'rows':len(d.data['timestamp']),'fields':list(d.data)}
  rows.append({'id':n,'log_start_native_us':u.start_timestamp,'topics':topics,'missing':'full EKFcross-covariance anddelayed aidingqueue/reset identity notexported byOPtrace. ExistingULogcovariancediagonal/stateoutputs alone do not give fullP; recoveryfromresetwouldneed complete initialization andaiding/IMU consumptionsequence.'})
 P1=np.array([[1,.5],[.5,1]]);P2=np.array([[1,-.5],[-.5,1]]);H=np.array([[1.,0]]);RR=.1;K=lambda P:(P@H.T/(float((H@P@H.T)[0,0])+RR)).flatten();write(out/'result.json',{'rows':rows,'same_diagonal_different_gain_example':{'P1':P1.tolist(),'P2':P2.tolist(),'K1':K(P1).tolist(),'K2':K(P2).tolist(),'positive_definite':True,'scope':'linear measurement algebra showsdiagonalsalone insufficient; doesnotprovebothcovariancesreachableunderactualfullsourcehistory'},'existing_data_may_enable':'source bootstrap ifcomplete prelogreset/initialization andall aiding/IMU queueordercanbereconstructed; notdemonstratedhere; do notclaimfullEKFclosed','minimal_new_validation_only':'matched sameF4singleA read-boundaryreleaseP=R±.19ms x2seed=4starts proposedonly; logtargetgenerationarrival/read andsourcefusion/cache/firstaction; oldP14Gzero budgetremains. Need fullEKFsnapshotonlyif future-covarianceconditionalmodel is chosen, notautomaticallyheavylogging.'})
if __name__=='__main__':main()
