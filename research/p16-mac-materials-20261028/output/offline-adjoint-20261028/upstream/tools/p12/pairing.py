import sys,json,argparse
from pathlib import Path
import numpy as np
from fractions import Fraction
sys.path.insert(0,'tools')
from p11.score import so3
from p12.execution import DTYPE
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description='Read-only P12 prestate feasibility; outputs a new file')
parser.add_argument('--analysis',type=Path,default=ROOT/'data/p12-20261026-analysis')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if args.output.exists():raise FileExistsError(args.output)
OUT=args.analysis
M=json.loads((OUT/'theory-v1/rational-matrices.json').read_text())
H=np.array([[float(Fraction(x)) for x in r] for r in M['H']]);X=np.array([[float(Fraction(x)) for x in r] for r in M['X']]);A=np.array([[float(Fraction(x)) for x in r] for r in M['A_abs']])
criteria={'position_m':.01,'velocity_m_s':.02,'SO3_deg':.5,'hidden_l2':.05,'previous_max':.03,'history_max':.03,'filter_max_rad_s':10.,'target_hold_T_s':.5,'target_reference_increment_m':.02,'one_call_action_bound':.2,'discrete_mismatch_allowed':0,'reason':'target reference Ep+.5Ev<=.02 (4% of position clip), source initial action increment<=.2 (10% full range), filter1% configured speed plus exact relation; no complete feedback domain claimed','frozen_before_pair_inspection':True}
# This feasibility criterion is declared before inspecting pilot pair results. Not a formal freeze.
cp=OUT/'pair-development-criteria.json'
if json.loads(cp.read_text())!=criteria:raise RuntimeError('development criteria identity differs')

def load(name):
 d=dict(np.load(OUT/(name+'-observation/synchronized.npz')))
 sends=[json.loads(s) for s in (ROOT/'data/p12-20261026-development'/name/'run/p11-sends.jsonl').read_text().splitlines()]
 t0=next(s['stream_t0_monotonic_s'] for s in sends if s['stream_t0_monotonic_s'] is not None)*1e9
 d['t']=(d['run_wall_ns'].astype(np.int64)-t0)/1e9
 h=dict(np.load(OUT/(name+'-native/history.npz')));d['mean']=h['history_before'];d['count']=h['count_before']
 rot=[];age=[]
 for motor in range(4):
  e=np.fromfile(ROOT/'data/p12-20261026-development'/name/f'run/gz-motor/execution-p12-{motor}.bin',DTYPE)
  j=np.searchsorted(e['end_ns'],d['run_wall_ns'],side='right')-1
  if np.any(j<0):raise RuntimeError('missing past execution state')
  rot.append(e['filter_after'][j]);age.append((d['run_wall_ns'].astype(np.int64)-e['end_ns'][j].astype(np.int64))/1000)
 d['rot']=np.array(rot).T;d['execution_age_us']=np.array(age).T
 return d

def compare(a,b):
 d=load(a);e=load(b);win=(d['t']>=12.895-.5)&(d['t']<12.895);i=np.flatnonzero(win)
 jj=np.searchsorted(e['t'],d['t'][i]);jj=np.clip(jj,1,len(e['t'])-1)
 jj=np.where(abs(e['t'][jj-1]-d['t'][i])<abs(e['t'][jj]-d['t'][i]),jj-1,jj)
 peak=lambda key:float(np.linalg.norm(d[key][i]-e[key][jj],axis=1).max())
 maxabs=lambda key:float(np.max(abs(d[key][i]-e[key][jj])))
 val={'position_m':peak('position'),'velocity_m_s':peak('velocity'),'SO3_deg':float(np.max(so3(d['attitude'][i],e['attitude'][jj]))),'hidden_l2':peak('h_before'),'previous_max':maxabs('previous'),'history_max':maxabs('mean'),'filter_max_rad_s':maxabs('rot')}
 bound=(abs(d['h_before'][i]-e['h_before'][jj])@H.T+abs(d['input'][i]-e['input'][jj])@X.T)@A.T
 val['one_call_action_bound']=float(min(2.,bound.max()));val['target_reference_increment_m']=val['position_m']+.5*val['velocity_m_s']
 discrete={}
 for key in ['count','committed','stale']:
  discrete[key]=int(np.sum(d[key][i]!=e[key][jj]))
 for key in ['lp_sample','att_sample']:
  discrete[key+'_age']=int(np.sum((d['sample_us'][i]-d[key][i])!=(e['sample_us'][jj]-e[key][jj])))
 discrete['native_sample_offset']=int(np.sum((d['native_us'][i]-d['sample_us'][i])!=(e['native_us'][jj]-e['sample_us'][jj])))
 gates={k:val[k]<=criteria[k] for k in val};gates['discrete']=not any(discrete.values())
 return {'arms':[a,b],'window_profile_s':[12.395,12.895],'rows':len(i),'timing_alignment':'same absolute profile; nearest observed call, no peak/capture alignment; timing mismatch retained','max_alignment_ms':float(np.max(abs(d['t'][i]-e['t'][jj]))*1000),'continuous':val,'discrete_mismatches':discrete,'gates':gates,'status':'FEASIBLE_SUBSYSTEM_PAIR' if all(gates.values()) else 'NOT_MATCHED','full_feedback_matching_certificate':False,'source_activation':'both arms use source T0; not an exact simulator/estimator/clock snapshot'}
pairs=[]
for a,b in [('dev03-native','dev05-native-repair'),('dev04-intermediate','dev06-intermediate-repair'),('dev08-common-native','dev09-common-native-repair')]:
 if (OUT/(b+'-native/history.npz')).exists():pairs.append(compare(a,b))
r={'schema':'p12-development-pair-feasibility-1','criteria':criteria,'pairs':pairs,'formal_starts':0,'threshold_relaxation':False,'interpretation':'source repair removes early activation semantic confound; independent SITL initial states may remain unmatched; failed subsystems do not justify strict causal combination claims'}
p=args.output;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
