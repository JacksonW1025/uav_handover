"""Mandatory perflight source identity, achievedread and jointinitial review."""
import sys,json,time,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p12c.features import load
from p12b.read_trace import load as reads
from p14h.snapshot import read

def analyze(target,out):
 target=Path(target).resolve();out=Path(out);limit(60);info=json.load(open(target/('information-v2.json' if (target/'information-v2.json').exists() else 'information.json')));analysis=R/info['source_analysis'] if info.get('source_analysis') else target/'analysis-v1';run=target/'run';d=load(run,analysis);events=[json.loads(l) for l in (run/'events.jsonl').read_text().splitlines()];releases=[e for e in events if e['event']=='p14h_resume_gate_release'];r=reads(run/'gz-motor/read-p12b.bin');rows=[]
 for e in releases:
  ns=e['actual_release_before_ns'];ix=np.flatnonzero((r['pre_read_wall_ns']>=ns)&r['read_updated'].astype(bool)&r['read_valid'].astype(bool));assert len(ix);j=int(ix[0]);prior=np.flatnonzero((r['pre_read_wall_ns']<ns)&r['gate_permit'].astype(bool));target_idx=e['target_index'];actual_idx=int(r['call_index_pre'][j]);expected=target_idx if e['side']=='BEFORE' else target_idx+2
  rows.append({'side':e['side'],'release_host_ns':ns,'intended_boundary_index':target_idx,'actual_first_valid_read_index':actual_idx,'expected_first_valid_read_index':expected,'achieved_intended_branch':actual_idx==expected,'first_valid_read_wall_ns':int(r['pre_read_wall_ns'][j]),'first_valid_read_sample_us':int(r['timestamp_sample'][j]),'publish_to_read_ms':(int(r['pre_read_wall_ns'][j])-ns)/1e6,'latest_prior_allowed_index':int(r['call_index_pre'][prior[-1]]),'actual_release_precedes_target_read_proved':actual_idx==target_idx if e['side']=='BEFORE' else False,'phase_status':'achieved' if actual_idx==expected else 'identifiable differentactualbranch; retained,no replacement','not_pure_capture_shift':True})
 a,h=read(run/'gz-motor/ekf-p14h.bin');A=json.load(open(analysis/'packed/prediction-input.json'))['plan']['full_source_windows_profile_s'][0][0];j=int(np.flatnonzero(d['t']<A-.004)[-1]);cut=int(d['run_wall_ns'][j]);q=int(np.flatnonzero(a['wall_ns']<=cut)[-1]);P=np.array(a['covariance'][q,:24,:24]);eig=np.linalg.eigvalsh(P.astype(float));cov={'cutoff_wall_ns':cut,'snapshot_wall_ns':int(a['wall_ns'][q]),'native_us':int(a['native_us'][q]),'latest_us':int(a['latest_us'][q]),'delayed_us':int(a['delayed_us'][q]),'fullP_diagonal':np.diag(P).tolist(),'crossP_frobenius':float(np.linalg.norm(P-np.diag(np.diag(P)))),'min_eigenvalue_numeric':float(eig[0]),'PSD_numeric_not_certified':bool(eig[0]>=-1e-6),'state25':a['state'][q,:25].tolist(),'full_future_EKF_restore':'unclosedaidingqueues/auxstates, no falsefullclosure'}
 np.savez_compressed(out/'initial-P.npz',P=P,state=a['state'][q,:25]);write(out/'result.json',{'actual_read_branches':rows,'all_intended_branches_achieved':all(x['achieved_intended_branch'] for x in rows),'snapshot':cov,'task_result':json.load(open(target/('information-v2.json' if (target/'information-v2.json').exists() else 'information.json'))),'preA_covariates':{k:np.asarray(d[k][j]).tolist() for k in ['position','velocity','attitude','omega','action','h_after','lp_sample','att_sample','sample_us','native_us']},'source':'observedafterflight, diagnosisonly; notinprestartselection','safe_to_continue_independent_config':'sourceidentity/data valid; actualbranch failures retained; scientificsuccess/failure no filtering'})
 record=run_child=[str(PY),str(R/'tools/p14h/guard.py'),'30','24',str(PY),str(R/'tools/p14r/pack_observer.py'),str(run),str(analysis),str(out/'source-initial')]
 with (out/'pack.log').open('w') as f:code=subprocess.run(record,stdout=f,stderr=subprocess.STDOUT).returncode
 assert code==0;print('P14H_REVIEW',target.name,'read_branches',[(r['side'],r['achieved_intended_branch'],r['actual_first_valid_read_index']) for r in rows])
def main():
 if sys.argv[1]=='child':analyze(sys.argv[2],sys.argv[3]);return
 out=register(sys.argv[2],'perflightactualbranch+P andinitial review, bounded60CPUself+30CPUpack child, 90subtree reservation',known_process_tree='one reviewworker +one guardedpack, no physicalstarts')
 r=run([PY,Path(__file__),'child',Path(sys.argv[1]).resolve(),out],out/'resource-worker',cpu=90,wall=120,scope='mechanism review boundedtwo-process tree')
 assert r['rc']==0
if __name__=='__main__':main()
