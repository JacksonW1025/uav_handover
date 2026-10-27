"""Correctly named pre-B phase and clip diagnostics; no forecast future inputs."""
import sys,json,numpy as np
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p15.common import B,write
from p12b.read_trace import load

def clip_table(t,raw,clipped,limit):
 rows=[]
 for j in range(3):
  certain=abs(raw[:,j])>limit+1e-5;near=abs(abs(raw[:,j])-limit)<=1e-5;ix=np.flatnonzero(certain);rows.append(dict(axis=j,certain_clipped_calls=int(certain.sum()),sampleclock_duration_s=float(certain.sum()*.004),boundary_uncertain_calls=int(near.sum()),first_profile_s=float(t[ix[0]]) if len(ix) else None,last_profile_s=float(t[ix[-1]]) if len(ix) else None,source_limit=limit,source_input_at_limit_calls=int(np.sum(abs(clipped[:,j])>=limit-1e-7))))
 return rows

def main():
 target=Path(sys.argv[1]);tapdir=Path(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(exist_ok=False,parents=True);analysis=next(p for p in [target/'analysis-v2',target/'analysis-v1'] if (p/'result.json').exists());raw=dict(np.load(analysis/'observation/synchronized.npz'));ev=[json.loads(l) for l in (target/'run/events.jsonl').read_text().splitlines()];epoch=next(e['run_wall_ns'] for e in ev if e['event']=='p12_confirmed_native_stream_anchor');t=(raw['run_wall_ns'].astype(np.int64)-epoch)/1e9;inp=json.load(open(target/'run/p15-selection-input.json'));sel=json.load(open(target/'run/p15-selection.json'));c=sel['executed_candidate'];ctx=inp['context'];b=ctx['A_start']+ctx['A_duration']+c['G'];z=np.load(tapdir/'taps.npz')['taps'];j=max(0,int(np.searchsorted(t,b)-1));k=max(0,int(np.searchsorted(z[:,0],b)-1));q=z[k,17:21];a=raw['attitude'][j];angle=float(np.degrees(2*np.arccos(np.clip(abs(np.dot(q,a))/(np.linalg.norm(q)*np.linalg.norm(a)),-1,1))));direct=load(target/'run/gz-motor/read-p12b.bin');di=int(np.flatnonzero(direct['timestamp_sample']==raw['sample_us'][j])[0]);Bpre=dict(model_profile_s=float(z[k,0]),actual_profile_s=float(t[j]),planned_B=b,strictly_before_B=bool(z[k,0]<b and t[j]<b),LP_p_error_m=(z[k,11:14]-raw['position'][j]).tolist(),LP_v_error_m_s=(z[k,14:17]-raw['velocity'][j]).tolist(),SO3_error_deg=angle,gyro_error=(z[k,21:24]-raw['omega'][j]).tolist(),h_L2=float(np.linalg.norm(z[k,46:62]-raw['h_after'][j])),previous_L2=float(np.linalg.norm(z[k,62:66]-raw['action'][j])),mean_L2=float(np.linalg.norm(z[k,66:70]-raw['input'][j,18:])),model_count=int(z[k,70]),actual_count=0 if raw['committed'][j] else 1,model_index=int(z[k,71]),actual_index=int(direct['call_index_pre'][di])+1,not_sameinitial_or_strict_discretematch=True,original_Bpre_field='old evaluate.py firstmodelcall at/after B kept in oldsummary, v2 here uses two explicit pre-B rows. No time shift/fitting.')
 yaw=raw['target_yaw'];cs=np.cos(yaw);sn=np.sin(yaw);dp=raw['position']-raw['target_p'];dv=raw['velocity']-raw['target_v'];ep=np.column_stack([cs*dp[:,0]+sn*dp[:,1],sn*dp[:,0]-cs*dp[:,1],-dp[:,2]]);vv=np.column_stack([cs*dv[:,0]+sn*dv[:,1],sn*dv[:,0]-cs*dv[:,1],-dv[:,2]]);phases={}
 for name,a,end in [('Ahold',ctx['A_start'],ctx['A_start']+ctx['A_duration']),('recovery',ctx['A_start']+ctx['A_duration'],b),('Bhold',b,b+c['D']),('Brecovery',b+c['D'],b+c['D']+2)]:
  use=(t>=a)&(t<end);phases[name]=dict(actual_rows=int(use.sum()),position=clip_table(t[use],ep[use],raw['input'][use,:3],.5),velocity=clip_table(t[use],vv[use],raw['input'][use,12:15],1.))
 write(out/'result.json',dict(id=target.name,Bpre=Bpre,actual_clip=phases,meaning='source targetyaw error axes, no LPvelocity rotation by physical/estimated yaw difference. 1e-5 boundary is uncertainty reporting, not a changedclip/safetythreshold. Duration sampleclock; native/host remain separate.',future_actual_scoring_only=True))
 print('P15_EXTRA_METRICS',target.name)
if __name__=='__main__':main()
