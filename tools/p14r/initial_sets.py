"""B: actual same-prefix joint support; no arbitrary independent h/history box.
Observed support coverage is finite-data evidence, not all-future reachability.
"""
import sys,json,time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from pyulog import ULog
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import records,write,sha
from p12c.features import load
from p14_motion.prepare import augment
from p13.physics import read,BODY

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[];started=time.perf_counter()
 for rec in records():
  if rec['group']!='formal':continue
  run=rec['target']/'run';doc=json.load(open(rec['packed']/'prediction-input.json'));d=load(run,rec['analysis']);history=dict(np.load(rec['analysis']/'native/history.npz'));A=doc['plan']['full_source_windows_profile_s'][0][0];j=int(np.flatnonzero(d['t']<A-.004)[-1]);i=dict(doc['initial']);wall=int(d['run_wall_ns'][j]);u=ULog(str(run/'flight.ulg'),['sensor_gyro'])
  i.update(position=d['position'][j].tolist(),velocity=d['velocity'][j].tolist(),attitude=d['attitude'][j].tolist(),omega=d['omega'][j].tolist(),h=d['h_after'][j].tolist(),previous=d['action'][j].tolist(),history=history['history_after'][j].tolist(),history_count=int(history['count_after'][j]),call_index=int(history['call_before'][j])+1,external_seen=True,target_p=d['target_p'][j].tolist(),target_v=d['target_v'][j].tolist(),target_yaw=float(d['target_yaw'][j]),stale=bool(d['stale'][j]),last_read_us=int(d['last_read'][j]),sample_us=int(d['sample_us'][j]),native_us=int(d['native_us'][j]),lp_phase_us=int(d['lp_sample'][j])%8000,profile_s=float(d['t'][j]),navigation_rotation_NED=np.eye(3).tolist())
  provenance=augment(i,run,wall,u);sends=[json.loads(l) for l in (run/'p11-sends.jsonl').read_text().splitlines()];past=[s for s in sends if s['after_ns']<=wall];last=past[-1];i['last_send_profile_s']=i['publisher_last_emit_s']=float(last['profile_s']);i['publisher_unconsumed_past']=None
  if max(abs(np.array(last['position'],np.float32)-d['target_p'][j]))>3e-6 or max(abs(np.array(last['velocity'],np.float32)-d['target_v'][j]))>3e-6:i['publisher_unconsumed_past']={'p':last['position'],'v':last['velocity'],'yaw':last['yaw']}
  body,_=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');body=body[body['phase']==1];epoch=round(wall-d['t'][j]*1e9);start=max(0,np.searchsorted(body['wall_ns'],epoch,side='right')-1);selected=body[(body['wall_ns']>=body['wall_ns'][start])&(body['wall_ns']<wall)];i['physical_H0_NED_z']=-float(body['com_p'][start,2]);i['physical_D0_m']=float(max(0,np.max(body['com_p'][start,2]-selected['com_p'][:,2])))
  family='F2' if '-F2-' in rec['id'] else 'F4';cls=[i['call_index']%2,i['history_count'],int(d['sample_us'][j]-d['lp_sample'][j]),int(d['sample_us'][j]-d['att_sample'][j]),int(d['stale'][j]),int(i['publisher_unconsumed_past'] is not None)]
  row={'id':rec['id'],'family':family,'class':cls,'initial':i,'source_provenance':provenance,'known_cutoff_wall_ns':wall,'source_paths':{'analysis':str(rec['analysis'].relative_to(R)),'packed':str(rec['packed'].relative_to(R))},'source_hashes':{str(p.relative_to(R)):sha(p) for p in [run/'flight.ulg',run/'p11-sends.jsonl',rec['analysis']/'native/history.npz']},'future_outcome_used_for_selection':False}
  write(out/rec['id']/'initial.json',row);rows.append(row);print('JOINT_PREFIX',rec['id'],cls,flush=True)
 groups=[]
 for family in ['F2','F4']:
  familyrows=[r for r in rows if r['family']==family]
  for cls in sorted(set(tuple(r['class']) for r in familyrows)):
   rr=[r for r in familyrows if tuple(r['class'])==cls];center=rr[0]['initial'];features=[];names=[];scales=[]
   fields=[('physical_COM_p',.1),('physical_COM_v',.15),('physical_omega',.1),('position',.1),('velocity',.15),('omega',.1),('h',.5),('previous',.1),('history',.1),('rotor_filter',10.),('pending_command',10.),('gyro_delay1',.1),('gyro_delay2',.1),('gyro_output_bias',.01),('target_p',.1),('target_v',.15),('physical_H0_NED_z',.1),('physical_D0_m',.1)]
   for field,scale in fields:
    n=np.size(center[field]);names.extend([field+':'+str(k) for k in range(n)]);scales.extend([scale]*n)
   names+=['physical_local_SO3:'+str(k) for k in range(3)]+['attitude_local_SO3:'+str(k) for k in range(3)];scales.extend([np.radians(2.5)]*6)
   for row in rr:
    i=row['initial'];x=np.concatenate([np.atleast_1d(i[k])-np.atleast_1d(center[k]) for k,_ in fields]);angles=[]
    for key in ['physical_q','attitude']:
     a=Rotation.from_quat(np.array(center[key])[[1,2,3,0]]);b=Rotation.from_quat(np.array(i[key])[[1,2,3,0]]);angles.extend((a.inv()*b).as_rotvec())
    features.append(np.r_[x,angles])
   X=np.array(features);scale=np.array(scales);U,s,V=np.linalg.svd((X/scale).T,full_matrices=False);rank=min(8,len(s));basis=U[:,:rank]*scale[:,None];coordinates=(X/scale)@U[:,:rank];amps=np.max(abs(coordinates),axis=0);residual=X-coordinates@basis.T;tail=np.max(abs(residual),axis=0)+2e-13;G=np.column_stack([basis*amps,np.diag(tail)]);coverage=np.all(abs(X)<=np.sum(abs(G),axis=1)+1e-12,axis=1)
   key=family+'-class'+str(len(groups));np.savez_compressed(out/(key+'.npz'),features=X,generators=G,scales=scale,coordinates=coordinates)
   groups.append({'key':key,'family':family,'class':cls,'ids':[r['id'] for r in rr],'source_center':rr[0]['id'],'feature_names':names,'support_points':len(rr),'observed_coverage':int(sum(coverage)),'rank':rank,'rank8_remainder_max_scaled':float(max(tail/scale)),'independent_box_radii':np.max(abs(X),axis=0).tolist(),'joint_outer_row_radii':np.sum(abs(G),axis=1).tolist(),'finite_bundle_members': [r['id'] for r in rr[:12]],'finite_bundle_not_cherry_picked':'first12 in pre-existing lexical identity order, allsupport remains in outer enclosure','meaning':'real jointly observed pre-event support; convex/PCA outer hull not claimed fully reachable, no future support guarantee','source_q_vs_attitude_separate':True,'no_nav_yaw_rotation':True})
 write(out/'summary.json',{'groups':groups,'records':len(rows),'elapsed_s':time.perf_counter()-started,'new_starts':0,'classification_is_pre_event_only':True,'real_reachable_points':'recorded runtime prefixes under oldfixedplatform; newpassiveplatform support must be checked separately','hull_future_certificate':False})

if __name__=='__main__':main()
