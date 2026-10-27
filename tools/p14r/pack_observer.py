"""Past-only joint source-observer initial state, known prefix/source parameters.
No future state, fusion, termination or clock word copied to prediction inputs.
"""
import sys,json,base64,time,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from pyulog import ULog
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
from p14r.observer import read,CORE,FUSION
from p14r.op import Op
from p14_motion.prepare import augment
from p14_motion.core import mul,conjugate,LEVER
from p11.models import speeds
from p13.physics import read as phread,BODY,rot
from p13.physical_model import S,B
from p12c.features import load

def main():
 run=Path(sys.argv[1]).resolve();analysis=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=False);d=load(run,analysis);old=json.load(open(analysis/'packed/prediction-input.json'));start=old['plan']['full_source_windows_profile_s'][0][0];j=int(np.flatnonzero(d['t']<start-.004)[-1]);wall=int(d['run_wall_ns'][j]);u=ULog(str(run/'flight.ulg'),['sensor_gyro','vehicle_local_position']);history=dict(np.load(analysis/'native/history.npz'));i=dict(old['initial']);LPH0=i['position'][2];pastLP=(d['t']>=0)&(np.arange(len(d['t']))<=j);i.update(LP_H0_NED_z=LPH0,LP_D0_m=float(max(0,np.max(d['position'][pastLP,2]-LPH0))),LP_tilt_failed_past=bool(np.any(d['tilt'][pastLP]>45)) if 'tilt' in d else False);i.update(position=d['position'][j].tolist(),velocity=d['velocity'][j].tolist(),attitude=d['attitude'][j].tolist(),omega=d['omega'][j].tolist(),h=d['h_after'][j].tolist(),previous=d['action'][j].tolist(),history=history['history_after'][j].tolist(),history_count=int(history['count_after'][j]),call_index=int(history['call_before'][j])+1,external_seen=True,target_p=d['target_p'][j].tolist(),target_v=d['target_v'][j].tolist(),target_yaw=float(d['target_yaw'][j]),stale=bool(d['stale'][j]),last_read_us=int(d['last_read'][j]),sample_us=int(d['sample_us'][j]),native_us=int(d['native_us'][j]),lp_phase_us=int(d['lp_sample'][j])%8000,profile_s=float(d['t'][j]),navigation_rotation_NED=np.eye(3).tolist());augment(i,run,wall,u)
 sends=[json.loads(l) for l in (run/'p11-sends.jsonl').read_text().splitlines()];past=[s for s in sends if s['after_ns']<=wall];i['last_send_profile_s']=i['publisher_last_emit_s']=past[-1]['profile_s'];i['publisher_unconsumed_past']=None
 if max(abs(np.array(past[-1]['position'],np.float32)-d['target_p'][j]))>3e-6 or max(abs(np.array(past[-1]['velocity'],np.float32)-d['target_v'][j]))>3e-6:i['publisher_unconsumed_past']={'p':past[-1]['position'],'v':past[-1]['velocity'],'yaw':past[-1]['yaw']}
 # Payload equality cannot exclude a repeated identical pending publication; this is a nominal slot assumption, not queue identity proof.
 core,_=read(run/'gz-motor/observer-core.bin',CORE,b'P14RCORE',True);fusion,_=read(run/'gz-motor/observer-fusion.bin',FUSION,b'P14RFUS1',True);gyro,_=read(run/'gz-motor/observer-gyro.bin',CORE,b'P14RGYRO',True);fs=fusion[(fusion['core']['wall_ns']<=wall)&(fusion['core']['kind']==4)];ff=fs[-1];g=gyro[gyro['wall_ns']<=wall][-1];cc=core[core['wall_ns']<=wall][-1]
 operations=[]
 for row in core[(core['wall_ns']>ff['core']['wall_ns'])&(core['wall_ns']<=wall)]:
  x=row['data'];kind=int(row['kind'])
  if kind==1:operations.append({'kind':1,'sample_us':int(row['sample_us']),'delta_angle':x[64:67].tolist(),'delta_velocity':x[67:70].tolist(),'dt':float(x[70])})
  if kind==3:operations.append({'kind':3,'sample_us':int(row['sample_us']),'q':x[64:68].tolist(),'v':x[68:71].tolist(),'geo':row['geo'][3:6].tolist(),'bg':x[74:77].tolist(),'ba':x[77:80].tolist()})
 predicted_op_sample=max([int(ff['core']['ids'][0])]+[x['sample_us'] for x in operations if x['kind']==1]);predicted_fusion_sample=max([int(ff['core']['ids'][0])]+[x['sample_us']+int(ff['core']['ids'][0]-ff['core']['sample_us']) for x in operations if x['kind']==3])
 packet={'fusion_base64':base64.b64encode(ff.tobytes()).decode(),'past_operations':operations,'latest_completed_update_sample_us':predicted_op_sample,'latest_fusion_publication_sample_us':predicted_fusion_sample,'last_delayed_fusion_sample_us':int(fs[-1]['core']['ids'][1]),'initial_stage':int(cc['kind']),'pending_operation_condition':'past-started deterministic operation finishes before next4ms call; no future poststate read','max_past_wall_ns':int(cc['wall_ns']),'cutoff_wall_ns':wall}
 body,_=phread(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');body=body[(body['phase']==1)&(body['valid']==63)];epoch=round(wall-d['t'][j]*1e9);b0=body[max(0,np.searchsorted(body['wall_ns'],epoch)-1)];prefix=body[(body['wall_ns']<=wall)&(body['sim_ns']//1000>=i['sample_us']-400000)];Q=S@rot(prefix['base_q'])@B;quat=Rotation.from_matrix(Q).as_quat()[:,[3,0,1,2]];W=np.einsum('nji,nj->ni',Q,prefix['base_omega']@S.T);p=prefix['com_p']@S.T;v=prefix['com_v']@S.T;bp=p+np.einsum('nij,j->ni',Q,LEVER);bv=v+np.einsum('nij,nj->ni',Q,np.cross(W,LEVER));T=prefix['sim_ns']//1000;lookup={int(t):k for k,t in enumerate(T)}
 physical_prefix=[{'sample_us':int(t),'p':p[k].tolist(),'v':v[k].tolist(),'q':quat[k].tolist(),'w':W[k].tolist(),'body_p':bp[k].tolist(),'body_v':bv[k].tolist()} for k,t in enumerate(T)]
 lib=R/'data/p14r-20261027/offline-build-v2/libop.bin';op=Op(lib,packet);world=R/'uav_lab/.local/checkouts/px4-raptor/Tools/simulation/gz/worlds/default.sdf';sph=ET.parse(world).getroot().find('.//spherical_coordinates');world_ref=np.array([np.radians(float(sph.findtext('latitude_deg'))),np.radians(float(sph.findtext('longitude_deg'))),float(sph.findtext('elevation'))]);fused=ff['core'];delay=int(fused['sample_us']);assert delay in lookup;k=lookup[delay];align=mul(fused['data'][64:68],conjugate(quat[k]));ev=fused['data'][68:71]-bv[k];eg=op.sub(fused['geo'][3:6],op.add(world_ref,bp[k]));bg=cc['data'][13:16];ba=cc['data'][16:19];bgs=[];bas=[]
 for row in core[(core['kind']==1)&(core['wall_ns']<=wall)&(core['wall_ns']>=wall-400000000)]:
  now=int(row['sample_us']);a=lookup.get(now);b=lookup.get(now-4000)
  if a is None or b is None:continue
  dq=mul(conjugate(quat[b]),quat[a]);angle=.5*(W[a]+W[b])*.004;older=lookup.get(now-8000);specific=Q[a].T@(bv[a]-bv[b]-np.array([0,0,9.8])*.004);
  if older is not None:specific=.5*(specific+Q[b].T@(bv[b]-bv[older]-np.array([0,0,9.8])*.004));bgs.append((row['data'][64:67]-angle)/.004);bas.append((row['data'][67:70]-specific)/.004)
 lp=next(t.data for t in u.data_list if t.name=='vehicle_local_position' and t.multi_id==0);lidx=np.flatnonzero((lp['timestamp_sample']<=i['sample_us'])&(lp['timestamp']<=i['native_us']))[-1];ref=np.array([np.radians(lp['ref_lat'][lidx]),np.radians(lp['ref_lon'][lidx]),lp['ref_alt'][lidx]])
 i.update(physical_H0_NED_z=-float(b0['com_p'][2]),physical_D0_m=float(max(0,np.max(b0['com_p'][2]-body['com_p'][(body['wall_ns']>=b0['wall_ns'])&(body['wall_ns']<=wall),2]))),gyro_delay1=g['data'][:3].tolist(),gyro_delay2=g['data'][3:6].tolist(),observer=packet,physical_prefix=physical_prefix,observer_parameters={'world_geo':world_ref.tolist(),'LP_reference_geo':ref.tolist(),'fusion_attitude_alignment':align.tolist(),'fusion_velocity_error':ev.tolist(),'fusion_position_error_NED':eg.tolist(),'gyro_bias':bg.tolist(),'accel_bias':ba.tolist(),'sensor_gyro_bias':np.mean(bgs,axis=0).tolist(),'sensor_accel_bias':np.mean(bas,axis=0).tolist(),'prefix_samples':len(bgs),'future_template':'fused q/v/global target follows delayed predicted physicalbody plus held initial residual; source OutputPredictor exact, full EKF target dynamics not claimed','OP_lag_us':int(i['sample_us']-predicted_op_sample),'fusion_delay_us':int(fused['ids'][0]-fused['sample_us']),'fusion_period_us':8000})
 i['last_consumed_command']=i['pending_command'];i['pending_command']=np.asarray(speeds(np.array(i['previous'])),np.float32).astype(float).tolist();i['execution_pending_condition']='latest known NN publication consumes on next physics step; consumed command stored separately; extra-delay word remains explicit'
 old['initial']=i;old['identity']=run.parent.name;write(out/'input.json',old);write(out/'provenance.json',{'cutoff_wall_ns':wall,'last_core_wall_ns':int(cc['wall_ns']),'last_full_fusion_wall_ns':int(ff['core']['wall_ns']),'role':'all initial/history/parameter estimates from past prefix only; no future fusion or sensors copied','world_source':str(world.relative_to(R)),'world_sha256':sha(world),'input_sha256':sha(out/'input.json'),'library_sha256':sha(lib),'new_data_exposed':'passive diagnostic, not independent validation'});op.close();print('PACKED_SOURCE_OBSERVER',run.parent.name,i['observer_parameters'])
if __name__=='__main__':main()
