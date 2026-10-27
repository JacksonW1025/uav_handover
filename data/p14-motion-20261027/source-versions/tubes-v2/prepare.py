"""Four fixed identities; past-only task and edge states. Future data separate."""
import sys,json,copy
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import records,sha,write
from p12c.features import load
from p13.physics import read,BODY,ROTOR,rot
from p13.physical_model import S,B,turn
from p14_motion.core import coeff,biquad,R

def augment(i,run,cutoff,u):
 allb,_=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');b=allb[(allb['phase']==1)&(allb['valid']==63)&(allb['wall_ns']<cutoff)];x=b[-1];Q=S@rot(x['base_q'][None,:])[0]@B;q=Rotation.from_matrix(Q).as_quat()[[3,0,1,2]];w=Q.T@S@x['base_omega']
 pre=allb[(allb['phase']==0)&(allb['step']==x['step'])];assert len(pre)==1
 Qpre=S@rot(pre['base_q'])[0]@B
 i.update(physical_COM_p=(S@x['com_p']).tolist(),physical_COM_v=(S@x['com_v']).tolist(),physical_q=q.tolist(),physical_omega=w.tolist(),physical_sample_us=int(x['sim_ns']//1000),physical_host_ns=int(x['wall_ns']))
 phases=[];filters=[];commands=[]
 for k in range(4):
  z,_=read(run/f'gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1');j=np.flatnonzero((z['step']==x['step'])&(z['wall_ns']<cutoff))
  if len(j)!=1:raise ValueError('initial rotor phase absent')
  z=z[j[0]];rel=Qpre.T@S@rot(z['q'][None,:])[0]@B
  # Pre to Post: source joint angle update using already known filter-after.
  phases.append(float(np.arctan2(rel[1,0],rel[0,0])-turn[k]*z['filter_after']/10*.004));filters.append(float(z['filter_after']));commands.append(float(z['command']))
 i.update(rotor_phase=phases,rotor_filter=filters,pending_command=commands)
 raw=next(x.data for x in u.data_list if x.name=='sensor_gyro' and x.multi_id==0);sel=(raw['timestamp_sample']<=i['sample_us'])&(raw['timestamp']<=i['native_us'])
 g=np.column_stack([raw[k][sel] for k in ['x','y','z']]);assert len(g)>100
 b0,b1,b2,a1,a2=coeff();d1=g[0]/(1+a1+a2);d2=d1.copy()
 for v in g:gy,d1,d2=biquad(v,d1,d2)
 i.update(gyro_delay1=d1.tolist(),gyro_delay2=d2.tolist(),gyro_output_bias=(np.array(i['omega'])-gy).tolist())
 return {'physical_cutoff_host_ns':int(cutoff),'physical_row_host_ns':int(x['wall_ns']),'gyro_prefix_samples':len(g),'gyro_latest_sample_us':int(raw['timestamp_sample'][sel][-1]),'phase_scope':'source-estimated Post phase from known Pre+filter-after, solver angle residual not certified','queue_condition':'initial target pending slot empty, future nominal delivery; actual in-flight queues not restored'}

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);ids=json.load(open(ROOT/'config/p14-motion-offline.json'))['cases'];index=[];old={}
 for r in records():
  if r['id'] not in ids:continue
  run=r['target']/'run';a=r['analysis'];doc=json.load(open(r['packed']/'prediction-input.json'));u=ULog(str(run/'flight.ulg'));d=load(run,a);manifest=json.load(open(r['packed']/'manifest.json'));cutoff=min(manifest.get('cutoff_host_ns',manifest['initial_cutoff_host_ns']),manifest['initial_max_host_ns'])
  task=copy.deepcopy(doc);provenance=augment(task['initial'],run,cutoff,u);task['identity']=r['id'];write(out/r['id']/'task-input.json',task)
  h=dict(np.load(a/'native/history.npz'));start=doc['plan']['full_source_windows_profile_s'][0][0];j=int(np.flatnonzero(d['t']<start-.004)[-1]);i=copy.deepcopy(doc['initial'])
  i.update(position=d['position'][j].tolist(),velocity=d['velocity'][j].tolist(),attitude=d['attitude'][j].tolist(),omega=d['omega'][j].tolist(),h=d['h_after'][j].tolist(),previous=d['action'][j].tolist(),history=h['history_after'][j].tolist(),history_count=int(h['count_after'][j]),call_index=int(h['call_before'][j])+1,external_seen=True,target_p=d['target_p'][j].tolist(),target_v=d['target_v'][j].tolist(),target_yaw=float(d['target_yaw'][j]),stale=bool(d['stale'][j]),last_read_us=int(d['last_read'][j]),sample_us=int(d['sample_us'][j]),native_us=int(d['native_us'][j]),lp_phase_us=int(d['lp_sample'][j])%8000,profile_s=float(d['t'][j]))
  last=np.flatnonzero(d['read_valid'][:j+1]);i['last_send_profile_s']=float(d['t'][last[-1]]) if len(last) else -1e30
  edge=copy.deepcopy(doc);edge['initial']=i;edge['identity']=r['id'];edgeprovenance=augment(i,run,int(d['run_wall_ns'][j]),u);write(out/r['id']/'edge-input.json',edge)
  params={k:v for k,v in u.initial_parameters.items() if k.startswith(('IMU_GYRO_','EKF2_TAU','CAL_GYRO0','SENS_BOARD'))};assert params['IMU_GYRO_CUTOFF']==40 and params['IMU_GYRO_DNF_EN']==0
  refs=[run/'flight.ulg',run/'gz-motor/physics-p13-body.bin',r['packed']/'prediction-input.json',a/'native/history.npz',a/'observation/synchronized.npz']+list((run/'gz-motor').glob('physics-p13-rotor-*.bin'))
  old.update({str(p.relative_to(ROOT)):sha(p) for p in refs})
  index.append({'id':r['id'],'run':str(run.relative_to(ROOT)),'analysis':str(a.relative_to(ROOT)),'packed':str(r['packed'].relative_to(ROOT)),'old_prediction':str(r['prediction'].relative_to(ROOT)),'task_past':provenance,'edge_past':edgeprovenance,'parameters':params,'actual_task_outcome':json.load(open(r['measured']))['task_outcome']})
 write(out/'index.json',index);write(out/'old-input-hashes.json',old);print('PREPARED_FIXED4',len(index))
if __name__=='__main__':main()
