"""C->N RINI4 source copy/select/reset operator in the event-map interface.
Classic position reset is asynchronous to the arbitration flag. Rate integral
is not invented as zero. Inactive classic states do not drive N-only flow.
"""
import copy,sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha

def cn(state,classic_action,shadow_h,fresh_reference=None):
 out=dict(state);C=getattr(shadow_h,'ctx',None);const=lambda v:C.constant(v) if C is not None else np.array(v);out.update(owner='N',h=shadow_h,previous=classic_action,mean=const([.32]*4),count=0,index=0,timing_initialized=False,external_seen=False,force_sync=2,classic_position_reset_pending=True,classic_rate_integral=state.get('classic_rate_integral','UNKNOWN_HELD_INACTIVE'))
 if fresh_reference is None:out.update(reference_p=state['LP'],reference_v=const([0,0,0]),reference_yaw=state['estimated_yaw'],stale=True)
 else:out.update(reference_p=fresh_reference[0],reference_v=fresh_reference[1],reference_yaw=fresh_reference[2],stale=False,external_seen=True)
 return out

def inactive_classic_position_callback(state):
 out=dict(state);C=getattr(state.get('h'),'ctx',None);out.update(classic_velocity_integral=C.constant([0,0,0]) if C is not None else np.zeros(3),classic_position_reset_pending=False);return out

def main():
 from pyulog import ULog
 from p11.observe import network
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));rows=[]
 sources=[R/'research/state/MemoryInit.hpp',R/'research/state/ActuatorGate.hpp',R/'research/state/ActionMap.hpp',R/'uav_lab/.local/checkouts/px4-raptor/src/modules/mc_raptor/mc_raptor.cpp',R/'uav_lab/.local/checkouts/px4-raptor/src/modules/mc_pos_control/MulticopterPositionControl.cpp',R/'uav_lab/.local/checkouts/px4-raptor/src/modules/mc_rate_control/MulticopterRateControl.cpp']
 for number in ['d02','d03','d04']:
  target=next((R/'data/p14r-20261027/runs').glob('p14r-'+number+'-*'));u=ULog(str(target/'run/flight.ulg'),['research_memory']);m=next(x.data for x in u.data_list if x.name=='research_memory');entry=np.flatnonzero((m['kind']==2)&(m['entry_mode']==4));assert len(entry)==1;j=int(entry[0]);f=lambda prefix,n,k:np.array([m[f'{prefix}[{a}]'][k] for a in range(n)],float);h=f('gru_before_entry',16,j);classic=f('classic_action',4,j);after=f('gru',16,j);prev=f('previous_action',4,j);steps=np.flatnonzero((m['timestamp']>=m['timestamp'][j])&(m['kind']==1)&m['active']);k=int(steps[0]);n=int(steps[1]);x=f('policy_input',22,k);hn,raw,action=network(P,h,x)
  row={'case':number,'entry_timestamp_us':int(m['timestamp'][j]),'entry_sample_us':int(m['timestamp_sample'][j]),'RINI':4,'entry_result':int(m['entry_result'][j]),'shadow_h_copy_max':float(max(abs(after-h))),'classic_previous_copy_max':float(max(abs(prev-classic))),'first_input_mean_vs_classic_max':float(max(abs(x[18:]-classic))),'first_committed_h_replay_max':float(max(abs(hn-f('gru',16,k)))),'first_action_vs_next_previous_max':float(max(abs(action-f('previous_action',4,n)))),'classic_action_age_us':int(m['timestamp'][j]-m['classic_actuator_timestamp'][j]),'scope':'observed real C->N plus later stop/capture/resume; first NN output validation, not every publication consumed','continuous_body_filter':'no assignment in handover source; actual physics and consumption retain their step timeline','classic_integrals':{'velocity':'source reset at next disabled-position callback, not synchronous arbitration; NCO0','rate':'held when rates disabled, unobserved initial value carried as opaque inactive state; no N-only output dependence'},'classic_reference':'outgoing position setpoint cleared at position-disable callback; incoming neural captures current LP if no valid fresh external message','NN_mean_reset':'source .66*2-1=.32, count0; first observe overwrites it with copied classic previous','timing_reset':'last observation/control/original flags false, intermediate index0; same-call initialization gate exception, then normal PH1','all_criteria_pass':bool(max(abs(after-h))==0 and max(abs(prev-classic))==0 and max(abs(hn-f('gru',16,k)))<1e-5 and max(abs(action-f('previous_action',4,n)))<1e-5)}
  write(out/(number+'.json'),row);rows.append(row)
 write(out/'summary.json',{'operator':'C->N RINI4, joint copy/select/reset with async inactive-classic callback','source_hashes':{str(p.relative_to(R)):sha(p) for p in sources},'records':rows,'all_pass':all(r['all_criteria_pass'] for r in rows),'new_handover_claim':'real entry in all3 valid records; no new mid-motion handover experiment claimed','N_to_C':'separate missing active classic flow/first integrator coordination; not silently covered'})
if __name__=='__main__':main()

# N->C side of the same map interface. This is a jump, not a substitute for
# the classic active controller/allocator flow. Its missing-latent check is
# explicit, so an observed N state never manufactures a cold classic reset.
def nc(state, incoming_reference, nco=0):
 out=dict(state);out.update(owner='C',neural_active=False,classic_reference=incoming_reference,exit_memory_capture_pending=True,neural_shadow_teacher_mode=4,allocation_flag_enabled=True)
 if nco!=0:raise ValueError('only source NCO0 jump audited in this finite extension')
 out['classic_velocity_integral']=state.get('classic_velocity_integral','SOURCE_ZERO_AFTER_DISABLED_CALLBACK')
 out['classic_rate_integral']=state.get('classic_rate_integral','UNKNOWN_HELD_WITHIN_PARAMETER_LIMITS')
 out['classic_attitude_reference']=state.get('classic_attitude_reference','UNKNOWN_HELD_REFERENCE_MODEL')
 required=['classic_attitude_reference','classic_rate_integral','classic_velocity_integral','classic_allocator_state','classic_cached_gyro_derivative']
 missing=[k for k in required if k not in state or isinstance(state[k],str)]
 return {'joint_state':out,'event':'N_TO_C','quality':'CONDITIONAL_CLASSIC_FLOW_INPUT' if not missing else 'TOP_FOR_ACTIVE_CLASSIC_FLOW','missing':missing,'continuous_physical_filter_D_unchanged':True,'source_rule':'no generic reset at mode request; velocity reset on disabledMPC callback, rate/reference-model states held; Raptor exits then runs teacher-forced shadow, next C->N RINI4 uses its evolved h'}
