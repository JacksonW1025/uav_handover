"""Independent P15 all-prefix source/data and decision-causality audit.
Scientific failures and censored heights use explicit three-valued denominators.
"""
import sys,json,numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p15.common import *
from p12.observe import analyze as observe
from p12.execution import audit as execution
from p12b.audit import audit as native_audit
from p13.physics import analyze as physical
from p12b.read_trace import load as reads
from p14r.observer import audit as observer
from p14h.terminal_e11_repair import verify
from p14h.snapshot import read as snapread
from p11.models import tilt

def main():
 target=Path(sys.argv[1]).resolve();run=target/'run';out=register(target/('analysis-v2' if (target/'analysis-v1').exists() else 'analysis-v1'),'P15 source replay/phase/execution/physics and live decision audit, fullprefix metrics');ev=[json.loads(l) for l in (run/'events.jsonl').read_text().splitlines()];t0=next(e['run_wall_ns'] for e in ev if e['event']=='p12_confirmed_native_stream_anchor');end=next((e['monotonic_ns'] for e in ev if e['event']=='p5_stream_ended'),None);failure=next((e for e in ev if e['event']=='failure'),None);s=observe(run,out/'observation');ex=execution(run,out/'execution');na=native_audit(run,out/'native');ph=physical(run,out/'physics');from p11.pack import measure
 measured=measure(run,out/'observation/synchronized.npz',out/'measured');raw=dict(np.load(out/'observation/synchronized.npz'));d=reads(run/'gz-motor/read-p12b.bin');active=d['active'].astype(bool);ds=d['timestamp_sample'][active].astype(np.int64);samples=raw['sample_us'];direct_ok=np.array_equal(ds[(ds>=samples[0])&(ds<=samples[-1])],samples)
 # Original strict observation result retained; only auxiliary Timing trailing
 # loss is qualified by complete canonical P11/direct identity, never an interior gap.
 allowed=all(v for k,v in s['gates'].items() if k!='all_control_calls') and not s['problems'] and direct_ok
 try:
  if not json.load(open(run/'config.json')).get('p14r',{}).get('observer_trace'):
   assert not (run/'gz-motor/observer-core.bin').exists();ob={'status':'UNOBSERVED_BY_CONFIG','scope':'d01 interface only; no sourceOP inference'};opok=True;write(out/'observer-unobserved.json',ob)
  else:ob=observer(run,target/'observer-audit-v1');opok=True
 except RuntimeError:ob=json.load(open(target/'observer-audit-v1/audit.json'));vr=verify(target);write(out/'producer-endpoint-qualification.json',vr);opok=vr['new_qualified_status']=='PASS_CAUSAL_TERMINAL_ENDPOINT'
 p,h=snapread(run/'gz-motor/ekf-p14h.bin');pok=h['errors']==h['dropped']==0 and len(p)>0 and np.isfinite(p['covariance'][:,:24,:24]).all()
 times=(raw['run_wall_ns'].astype(np.int64)-t0)/1e9;last=(end or (failure or {}).get('monotonic_ns',int(raw['run_wall_ns'][-1])));use=(raw['run_wall_ns']>=t0)&(raw['run_wall_ns']<=last);pos=raw['position'][use];q=raw['attitude'][use];tt=times[use];assert len(tt);H0=-float(raw['position'][max(0,np.searchsorted(times,0)-1),2]);L=pos[:,2]+H0;D=np.maximum.accumulate(L);th=np.degrees(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)));complete=end is not None
 def outcome(a,threshold):return 'FAIL' if np.any(a>threshold) else 'SUCCESS' if complete else 'UNKNOWN'
 risks=dict(tilt=outcome(th,45),height=outcome(D,1));risks['task']='FAIL' if 'FAIL' in risks.values() else 'SUCCESS' if all(v=='SUCCESS' for v in risks.values()) else 'UNKNOWN'
 def crossing(a,v):
  ids=np.flatnonzero(a>v)
  if not len(ids):return None
  j=int(ids[0]);return [float(tt[max(0,j-1)]),float(tt[j])]
 decision=json.load(open(run/'p15-decision-state.json')) if (run/'p15-decision-state.json').exists() else None;selection=json.load(open(run/'p15-selection.json')) if (run/'p15-selection.json').exists() else None;realized=json.load(open(run/'p15-realized-plan.json')) if (run/'p15-realized-plan.json').exists() else None
 live=[]
 if decision:
  j=np.flatnonzero((raw['sample_us']==decision['timestamp_sample'])&(raw['native_us']==decision['timestamp']));assert len(j)==1;ix=int(j[0]);fieldmap={'position':'position','velocity':'velocity','attitude':'attitude','angular_velocity':'omega','gru_after':'h_after','previous_action_after':'action'}
  for source,key in fieldmap.items():
   if key not in raw:continue
   er=float(np.max(abs(np.array(decision[source])-raw[key][ix])));live.append(dict(field=source,max_abs=er,tolerance=5.2e-6));assert er<=5.2e-6,'live rounded listener mismatch '+source
  assert decision['run_wall_ns']<=decision['read_wall_ns']<=decision['available_by_ns'];assert decision['available_by_ns']<=next(e['monotonic_ns'] for e in ev if e['event']=='p15_decision_requested');assert all(x['end_ns']<=decision['available_by_ns'] for x in decision['execution'])
 gates=dict(source_replay=allowed,source_active_samples_4ms=bool(np.all(np.diff(ds)==4000)),execution=ex['status']=='PASS',native=na['status']=='PASS',physics=ph['status']=='PASS',observer=opok,fullP=pok,live_state=decision is not None,selection=selection is not None,realized=realized is not None,unchanged=json.load(open(target/'execution-result.json'))['candidate_unchanged'])
 B=realized['B_planned_start'] if realized else None;before=tt<B if B is not None else np.ones(len(tt),bool);prefix_fail=bool(np.any(th[before]>45) or np.any(D[before]>1));j=max(0,min(len(tt)-1,int(np.searchsorted(tt,B or tt[-1])-1)))
 result=dict(status='PASS' if all(gates.values()) else 'NOT_PASSED',gates=gates,risks=risks,censored=not complete,complete=complete,first_crossing=dict(tilt=crossing(th,45),height=crossing(D,1)),peak_tilt_deg=float(th.max()),LP_D_m=float(D.max()),prefix_failed_before_B=prefix_fail,B_plan_reached=bool(B is not None and tt[-1]>=B),Bpre=dict(profile_s=float(tt[j]),LP_L_m=float(L[j]),LP_D_m=float(D[j]),LP_W_m_s=float(raw['velocity'][use][j,2]),tilt_deg=float(th[j])),decision_precision=live,decision=decision,selected=selection['executed_candidate'] if selection else None,observed_horizon_s=[float(tt[0]),float(tt[-1])],outcome_scope='LP controller read state and full stream prefix; direct physicalCOM separately stored, original frozen runner abort side by side',original_runner_failure=failure,original_observation_status=s['status'],raw_hashes={'flight.ulg':sha(run/'flight.ulg'),'body':sha(run/'gz-motor/physics-p13-body.bin')},no_future_ranking=decision is not None,physical_live_not_used=True)
 result['controller_read_prefix_risks']=result['risks'];result['risks']={k:('FAIL' if measured['whole'][field]>threshold else 'UNKNOWN' if measured['censored'] else 'SUCCESS') for k,field,threshold in [('tilt','max_tilt_deg',45),('height','max_altitude_loss_m',1)]};result['risks']['task']='FAIL' if 'FAIL' in result['risks'].values() else 'UNKNOWN' if 'UNKNOWN' in result['risks'].values() else 'SUCCESS';result['original_frozen_flight_outcome']=measured['frozen_flight_outcome'];result['primary_task_measurement']=measured;result['censored']=measured['censored'];result['complete']=not measured['censored']
 write(out/'result.json',result);np.savez_compressed(out/'prefix.npz',t=tt,L=L,D=D,tilt=th,LP=pos,velocity=raw['velocity'][use],h=raw['h_after'][use],action=raw['action'][use]);print('P15_ANALYSIS',result['status'],risks)
 if not all(gates.values()):raise RuntimeError('P15 data gates '+str([k for k,v in gates.items() if not v]))
if __name__=='__main__':main()
