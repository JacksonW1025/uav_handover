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
 eventrows=[dict(status='PHYSICS_UNAVAILABLE',reason='P13bufferlostduringGazeboSIGKILL; no COM reconstructed')];actualevents=[];stale=raw['stale'].astype(bool);changes=np.flatnonzero(np.diff(stale.astype(int))!=0)+1
 for j in changes:
  if t[j]>=A-.05:actualevents.append(dict(kind='capture' if stale[j] else 'resume',profile_s=float(t[j]),sample_us=int(raw['sample_us'][j]),native_us=int(raw['native_us'][j])))
 Berr=None
 if pred['Bpre'] is not None and t[-1]>=B:
  j=max(0,int(np.searchsorted(t,B)-1));b=pred['Bpre'];Berr=dict(L_m=b['L']-(raw['position'][j,2]+H0),W_m_s=b['W']-raw['velocity'][j,2],h_L2=float(np.linalg.norm(np.array(b['h'])-raw['h_after'][j])),previous_L2=float(np.linalg.norm(np.array(b['previous'])-raw['action'][j])),mean_L2=float(np.linalg.norm(np.array(b['mean'])-raw['input'][j,18:])),count_prediction=b['count'],count_actual=0 if raw['committed'][j] else 1)
 summary=dict(physical_record_missing=True,scope='complete controller task and frozen LPprediction, physicalCOMunknown; olderrorretained',id=target.name,predicted=pr,actual=meas['risks'],censored=meas['censored'],prediction_stop=pred['stop'],full_time_errors=errors,windows=windows,phases=phases,Bpre_errors=Berr,actual_events=actualevents,initial_available_by_ns=input['snapshot']['available_by_ns'],input_sha256=sha(run/'p15-selection-input.json'),future_inputs_used=False,role='frozen recipe conditional selected forecast, actual legal decision state; model observed prelaunch during development, new search not refit. Full horizon computed postflight from only that immutable saved past input; not task0 forecast',projection_changed_search=chosen.get('score_projection'),model_cost_s=pred['model_CPU_s']);write(out/'summary.json',summary);write(out/'event-states.json',eventrows);print('P15_EVALUATED',target.name,pr,meas['risks'])
if __name__=='__main__':main()
