"""Frozen selected forecast and all-prefix successor audit; scoring future stays
separate from prediction input saved during the actual legal decision.
"""
import sys,json,numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p15.common import *
from p15.model import rollout
from p13.physics import read,BODY,rot
from p13.physical_model import S,B as BODY_B
from p12.execution import DTYPE

def main():
 target=Path(sys.argv[1]).resolve();out=register(sys.argv[2],'frozen selected-candidate complete nominal timecourse and actual successor errors; future used only scoring');run=target/'run';input=json.load(open(run/'p15-selection-input.json'));chosen=json.load(open(run/'p15-selection.json'));candidate=chosen['executed_candidate'];context=dict(input['context'],full_task_forecast=True);P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));pred=rollout(input['snapshot'],candidate,context,input['parameters'],P,input.get('update'));write(out/'forecast.json',pred);np.savez_compressed(out/'forecast.npz',trace=np.asarray(pred['full_prefix']));analysis=next(p for p in [target/'analysis-v2',target/'analysis-v1'] if (p/'result.json').exists());meas=json.load(open(analysis/'result.json'));raw=dict(np.load(analysis/'observation/synchronized.npz'));events=[json.loads(l) for l in (run/'events.jsonl').read_text().splitlines()];epoch=next(e['run_wall_ns'] for e in events if e['event']=='p12_confirmed_native_stream_anchor');t=(raw['run_wall_ns'].astype(np.int64)-epoch)/1e9;z=np.asarray(pred['full_prefix']);sel=(t>=z[0,0])&(t<=z[-1,0]);ti=t[sel];oi=np.flatnonzero(sel);expected=np.stack([np.interp(ti,z[:,0],z[:,k]) for k in [1,2,3,4]],axis=1);H0=context['H0_LP'];observed=np.column_stack([raw['position'][oi,2]+H0,np.maximum(context.get('D_LP',0),np.maximum.accumulate(raw['position'][oi,2]+H0)),raw['velocity'][oi,2],np.degrees(np.arccos(np.clip(1-2*(raw['attitude'][oi,1]**2+raw['attitude'][oi,2]**2),-1,1)))])
 def risk(a,lim):return 'FAIL' if np.any(a>lim) else 'UNKNOWN' if pred['stop'] is not None else 'SUCCESS'
 pr=dict(tilt=risk(z[:,4],45),height=risk(z[:,2],1));pr['task']='FAIL' if context.get('prefix_failed') or 'FAIL' in pr.values() else 'UNKNOWN' if 'UNKNOWN' in pr.values() else 'SUCCESS';errors={}
 for k,(name,tol) in enumerate([('LP_L_m',.1),('LP_D_m',.1),('LP_W_m_s',.15),('tilt_deg',2.5)]):
  er=abs(expected[:,k]-observed[:,k]);ids=np.flatnonzero(er>tol);errors[name]=dict(full_common_RMSE=float(np.sqrt(np.mean(er**2))),max_abs=float(er.max()),first_exceed_s=float(ti[ids[0]]) if len(ids) else None,threshold=tol)
 phases={};A=context['A_start'];ar=A+context['A_duration'];B=A+context['A_duration']+candidate['G'];br=B+candidate['D']
 for name,a,b in [('Apre',A-.5,A),('Ahold',A,ar),('recovery',ar,B),('Bpre',B-.2,B),('Bhold',B,br),('Brecovery',br,br+2),('tail',br+2,context['task_end'])]:
  ix=(ti>=a)&(ti<=b);phases[name]=dict(interval=[a,b],observed_rows=int(ix.sum()),RMSE={key:float(np.sqrt(np.mean((expected[ix,k]-observed[ix,k])**2))) if np.any(ix) else None for k,key in enumerate(['L','D','W','tilt'])})
 windows={}
 for width in [.5,2.]:
  use=(ti>=input['snapshot']['profile_s'])&(ti<=input['snapshot']['profile_s']+width);windows[str(width)]=dict(rows=int(use.sum()),RMSE={key:float(np.sqrt(np.mean((expected[use,k]-observed[use,k])**2))) if np.any(use) else None for k,key in enumerate(['L','D','W','tilt'])})
 eventrows=[];exs=[np.fromfile(run/f'gz-motor/execution-p12-{k}.bin',DTYPE) for k in range(4)];from p12b.read_trace import load as load_reads
 direct=load_reads(run/'gz-motor/read-p12b.bin');body,header=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');body=body[(body['phase']==1)&(body['valid']==63)&(body['wall_ns']>=epoch)];physicalH0=float(body['com_p'][np.searchsorted(body['wall_ns'],epoch),2]);physicalD=np.maximum.accumulate(physicalH0-body['com_p'][:,2]);actualevents=[];stale=raw['stale'].astype(bool);changes=np.flatnonzero(np.diff(stale.astype(int))!=0)+1
 for j in changes:
  if t[j]>=A-.05:actualevents.append(dict(kind='capture' if stale[j] else 'resume',profile_s=float(t[j]),sample_us=int(raw['sample_us'][j]),native_us=int(raw['native_us'][j])))
 for name,at in [('Apre',A-.004),('Aresume_plan',ar),('Bpre',B-.004),('Bresume_plan',br),('taskend',context['task_end'])]+[(f'{e["kind"]}-{n}',e['profile_s']) for n,e in enumerate(actualevents[:6])]:
  if at>t[-1]:eventrows.append(dict(name=name,at=at,status='NOT_REACHED'));continue
  j=max(0,int(np.searchsorted(t,at,side='right')-1));wall=int(raw['run_wall_ns'][j]);k=max(0,int(np.searchsorted(body['wall_ns'],wall,side='right')-1));p=body[k];executions=[]
  for a in exs:
   ii=max(0,int(np.searchsorted(a['end_ns'],wall,side='right')-1));executions.append({n:(float(a[n][ii]) if a.dtype[n].kind=='f' else int(a[n][ii])) for n in ['sample_us','sim_us','end_ns','command','filter_before','filter_after','joint','thrust']})
  di=max(0,int(np.searchsorted(direct['pre_read_wall_ns'],wall,side='right')-1));read_state={n:int(direct[n][di]) for n in ['call_index_pre','force_sync_pre','gate_permit','read_updated','read_valid','timing_initialized_pre','last_valid_read_post']};L=float(physicalH0-p['com_p'][2]);histD=float(max(0,np.max(physicalH0-body['com_p'][:k+1,2])));eventrows.append(dict(name=name,planned_s=at,actual_source_s=float(t[j]),status='OBSERVED',execution=executions,read_state=read_state,pending_transport='UNKNOWN identity, no fabricated commandFIFO',COM_H_m=float(p['com_p'][2]),origin_H_m=float(p['origin_p'][2]),COM_L_m=L,COM_D_m=histD,COM_W_m_s=-float(p['com_v'][2]),physical_step=int(p['step']),sim_ns=int(p['sim_ns']),body_world_omega=p['base_omega'].tolist(),COM_minus_origin=(p['com_p']-p['origin_p']).tolist(),LP_p=raw['position'][j].tolist(),LP_v=raw['velocity'][j].tolist(),LP_q=raw['attitude'][j].tolist(),h=raw['h_after'][j].tolist(),previous=raw['action'][j].tolist(),mean=raw['input'][j,18:].tolist(),count=0 if raw['committed'][j] else 1,LP_age_us=int(raw['sample_us'][j]-raw['lp_sample'][j]),att_age_us=int(raw['sample_us'][j]-raw['att_sample'][j]),sample_us=int(raw['sample_us'][j]),native_us=int(raw['native_us'][j]),committed=bool(raw['committed'][j]),source_time_ns=wall,physical_available='after exit only, no ranking injection'))
 Berr=None
 if pred['Bpre'] is not None and t[-1]>=B:
  j=max(0,int(np.searchsorted(t,B)-1));b=pred['Bpre'];Berr=dict(L_m=b['L']-(raw['position'][j,2]+H0),W_m_s=b['W']-raw['velocity'][j,2],h_L2=float(np.linalg.norm(np.array(b['h'])-raw['h_after'][j])),previous_L2=float(np.linalg.norm(np.array(b['previous'])-raw['action'][j])),mean_L2=float(np.linalg.norm(np.array(b['mean'])-raw['input'][j,18:])),count_prediction=b['count'],count_actual=0 if raw['committed'][j] else 1)
 summary=dict(id=target.name,predicted=pr,actual=meas['risks'],censored=meas['censored'],prediction_stop=pred['stop'],full_time_errors=errors,windows=windows,phases=phases,Bpre_errors=Berr,actual_events=actualevents,initial_available_by_ns=input['snapshot']['available_by_ns'],input_sha256=sha(run/'p15-selection-input.json'),future_inputs_used=False,role='frozen recipe conditional selected forecast, actual legal decision state; model observed prelaunch during development, new search not refit. Full horizon computed postflight from only that immutable saved past input; not task0 forecast',projection_changed_search=chosen.get('score_projection'),model_cost_s=pred['model_CPU_s']);write(out/'summary.json',summary);write(out/'event-states.json',eventrows);print('P15_EVALUATED',target.name,pr,meas['risks'])
if __name__=='__main__':main()
