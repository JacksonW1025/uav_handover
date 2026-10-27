"""Final evidence/map/cost index. Existing attempts and analyses are immutable.
Large raw/derived arrays are retained locally with hashes, never pruned.
"""
import sys,json,datetime
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p14.common import write,sha
B=R/'data/p14r-20261027'
def read(p):return json.load(open(B/p))
def jobs(folder):
 rows=[]
 for f in sorted((B/folder).glob('*/tube.json')):
  x=json.load(open(f));rows.append({'path':str(f.relative_to(B)),'first_precision_call':x['first_precision_loss']['call'] if x['first_precision_loss'] else None,'first_domain_call':x['first_domain_loss']['call'] if x['first_domain_loss'] else None,'elapsed_s':x['elapsed_s'],'regions':list(x['regions']),'job':x['job']})
 return rows

def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False);ledger=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];starts=[r for r in ledger if r['event']=='START_INTENT'];finishes=[r for r in ledger if r['event']=='FINISH'];assert len(starts)==6 and len(finishes)==5
 rows=[];raw={}
 for r in starts:
  target=B/'runs'/r['id'];run=target/'run'
  for p in [run/'flight.ulg',run/'p11-sends.jsonl']+list((run/'gz-motor').glob('*.bin')):
   if p.exists():raw[str(p.relative_to(R))]=sha(p)
  rows.append({'id':r['id'],'ordinal':r['ordinal'],'source':r['source'],'information':json.load(open(target/'information.json')) if (target/'information.json').exists() else {'status':'QUARANTINED'},'source_replay':read(f"source-replay-d{r['ordinal']:02d}-v1/result.json")})
 write(out/'raw-hashes.json',{'files':raw,'retention':'all original raw files retained, including d01invalid. Header complete alone does not establish coverage.'})
 # All local full arrays/checkpoints/runtime copies used by the round, uniformly.
 local={str(p.relative_to(R)):sha(p) for p in B.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix in ['.npz','.bin'] and 'rootfs' not in p.parts and not str(p.relative_to(R)) in raw}
 write(out/'local-array-runtime-hashes.json',{'files':local,'scope':'ordinary snapshots, full derived arrays and all failed-set checkpoints; local only, no downsampling/deletion'})
 old=R/'data/p14-motion-20261027/inputs-v3/old-input-hashes.json';checks={p:sha(R/p)==h for p,h in json.load(open(old)).items()};assert all(checks.values())
 write(out/'historical-preservation.json',{'old_raw_inputs':checks,'old_git_paths':'no old reports/data/freezes edited; maintained current generator/runner/patch/test changes separately reviewed','preexisting_dirty':'start-state.json retained; AGENTS/old receipts not staged','CLI':'old symlink text kept, shared Lab target is not a historical binary snapshot; actual pre-change/runtime-v1/runtime-v2 ordinary copies retained','A4':'NOT_PROVEN_EXCLUDED'})
 basejobs=jobs('C-joint-v6');innov=jobs('C-innovation-v1');relations=jobs('C-relations-v8');cont=read('C-continue-v1/result.json');cpu=read('C-no-compression-full-v1/resource-stop-confirmed.json');height=read('height-constraint-v1/result.json');storage=read('storage-v2/result.json');composition=read('compose-v2/composition.json');classic=read('classic-kernel-v5/result.json');clock=read('A-clock-reach-v2/summary.json');score=read('registered-score-v1/summary.json')['summaries']['PRE-phase0.0-jointdelay0.0'];stage=read('initial-stage-v1/result.json')
 C={'full_two_clock_union':basejobs,'innovation_contrasts':innov,'source_graph_relations':relations,'no_compression_original':cpu,'checkpoint_validation':read('C-continue-v1/validation-audit.json'),'continued':{k:v for k,v in cont.items() if k not in ['rows','compression','capture_alias']},'continued_selected_rows':[x for x in cont['rows'] if x['call'] in [128,140,141,180,196,197]],'full_initial_joint_event_depth':0,'single_quarter_scope':'one source staged-history quarter/d02publisher clock, ideal model future. Information valid through140 (resume+.192s); source domain through196 (resume+.416s), domain loss197. B/pre/.5s/2s not reached. Whole pre-checkpoint tilt prefix not fully saved by resource-stopped job; do not assert whole-prefix tilt safety from resumed rows alone.','zero_radius':'algorithmic independent remainders/gamma/libm assumption and real-chart/source-float center difference; not physical uncertainty or certified actual rounding'}
 write(out/'C-final-summary.json',C)
 # Component wall times are not exclusive CPU and may overlap. Keep failed work.
 measured={};unmeasured=[]
 for p in B.glob('*/execution.json'):
  x=json.load(open(p));rr=x.get('rows',[]) if isinstance(x,dict) else x
  if isinstance(rr,list):
   values=[r.get('elapsed_s',r.get('wall_s')) for r in rr]
   if all(v is not None for v in values):measured[str(p.relative_to(B))]=sum(values)
   else:unmeasured.append(str(p.relative_to(B)))
 for p in B.glob('*/isolation.json'):
  x=json.load(open(p))
  if 'elapsed_s' in x:measured[str(p.relative_to(B))]=x['elapsed_s']
  else:unmeasured.append(str(p.relative_to(B)))
 for p in ['B-bundles-v1/summary.json','storage-v1/result.json','storage-v2/result.json','compose-v1/composition.json','compose-v2/composition.json','C-liveness-v1/tube.json','C-continue-v1/result.json','C-continue-v1/validation-result.json']:
  if (B/p).exists():measured[p]=read(p).get('elapsed_s',0)
 measured['C-no-compression-full-v1/resource-stop-confirmed.json']=cpu['last_post_call']['elapsed_s']
 measured['classic-kernel-v5/build.json']=read('classic-kernel-v5/build.json')['elapsed_s']
 for name in ['offline-build-v1','offline-build-v2']:
  m=read(name+'/manifest.json');measured[name+'/manifest.json']=sum(x['elapsed_s'] for x in m['commands'])
 p13=[json.loads(l) for l in (R/'data/p13-20261026-preparation/attempts.jsonl').read_text().splitlines()];start=datetime.datetime.fromisoformat(read('start-state.json')['time_utc']);wall=(datetime.datetime.now(datetime.timezone.utc)-start).total_seconds();newwall=sum(r.get('elapsed_s',0) for r in ledger if r['event'] in ['PHYSICAL_END','PHYSICAL_UNCERTAIN']);oldwall=sum(r.get('elapsed_s',0) for r in p13 if r['event']=='PHYSICAL_END')
 costs={'new_START_INTENT':len(starts),'new_physical_process_wall_s':newwall,'historical_P13_starts':sum(r['event']=='START_INTENT' for r in p13),'historical_P13_physical_process_wall_s':oldwall,'end_to_end_modeling_wall_s':wall,'measured_component_wall_s':measured,'component_sum_not_exclusive_CPU':sum(measured.values()),'unmeasured_component_records':unmeasured,'unmeasured':'early build/replay/test CPU and historical P11-P14 development labor not fully logged; retained UNKNOWN, never zero-filled','scope':'all failed builds/diagnostics/sets lie inside end-to-end modeling interval. Parallel component walls are not summed into an exclusive wall or CPU claim. New raw diagnostics require6flights, no substitute test-reduction experiment.','support_point_proxy':{'24_nominal_model_wall_s':read('B-bundles-v1/summary.json')['elapsed_s'],'24_direct_flight_proxy_s':24*float(np.median([r['elapsed_s'] for r in ledger if r['event']=='PHYSICAL_END'])),'not_equivalent_goal':'point trajectories do not establish continuous joint safety coverage'},'net_cost_benefit':'NOT_ESTABLISHED'};write(out/'cost.json',costs)
 machine={'schema':'p14r-method-refinement-conclusion-2','baseline':'69ca54ff3029df671de740cf0a4ab4495b03b44a','starts':6,'valid_records':5,'quarantined':1,'unused':2,'further_starts':'NONE_PLANNED; do not consume quota','records':rows,'A':{'actual_source_OP':'31fields continuous bitexact after55s on all6prefixes, d01 remains quarantined','initial_stage':stage,'future_model':'actual OP with source-shaped synthetic IMU and held past fusion template; full EKF innovation and future variable scheduling not closed','historical_conditional_brackets':{'captures':clock['capture_tested'],'capture_missed':clock['capture_missed'],'resumes':clock['resume_tested'],'resume_missed':clock['resume_missed'],'future_host_bounds_certified':False},'future_injections':'diagnostics only, not autonomous score'},'B':{'old_support_count':66,'old_points_propagated':24,'new_joint_domain':'d02/d03 staged histories, two clock fibers x4quarters; observed endpoints retained but interior reachability/futurecoverage not established'},'C':C,'score_primary':score,'handover':{'real':'C->N entry plus N dropout/resume; first3valid passive entry actions independently replayed','active_classic':'source Position/Attitude/Rate kernels and same-interface N->C jump implemented, full active classic flow remains TOP','first_raw_torque_repair':classic,'not_claimed':'whole N->C movement safety or physical torque/allocation continuity'},'conditional_height_relation':height,'storage':{k:v for k,v in storage.items() if k not in ['layout','center']},'nominal_composition_depth':4,'interval_complete_joint_event_depth':0,'A4':'NOT_PROVEN_EXCLUDED','cost_benefit':'NOT_ESTABLISHED','verdict':'keep source event/state map, moving nominal and joint-history representation. Source graph and no-compression tests identify useful directions; do not use current full-task predictor or outer tube as a safety screening guarantee. Future observation temporal conditions and tractable certified remainder propagation are the next bottlenecks.'};write(out/'machine-conclusion.json',machine)
 edge={'schema':'moving-correlated-event-map-4','input':{'mode':'N_ACTIVE after real C->N RINI4','joint_region':'C-joint-v6 two publisher-clock fibers x4quarters; staged observed endpoint histories, not simultaneous whole simulator snapshots','event':'stop -> strict timeout capture -> full hold -> latest valid resume -> recovery -> next event','source':'source-inputs-v3/d02,d03 (full OP packets and all history/execution/queue state)','state':['COMp/v/q/omega/rotorphase','physical vs estimatedq/LPframe/bias','OP ring+indices+corrections','gyroDFII','h/previous/mean/count','filter/pending/consumed','reference/capture','publisher/transport/readslot','native/sample/commit','COM and LP H0/L/D/W/failure latch'],'conditions':'declared source physical and local observer model; future fusion/EKF/SERVO/source float/geodesy budgets unclosed; persistent nominal words not all legal switching'},'output':{'nominal':'compose-v2 full array and4serialized successors','full_joint_tube':'C-joint-v6; TOP at each named domain loss','longer_single_quarter':'C-no-compression-full-v1 resume checkpoint -> C-continue-v1 rows93..197; no safe successor at197','conditional_height':'height-constraint-v1/result.json; all-prefix sufficient reserve, not LP/tilt guarantee','partial_prefix_margins':'local saved prefixes only; original killed prefix has incomplete tilt-row archive','storage':'storage-v2 factor, nonlinear remainder and numerical certification remain conditional','cost':str(out.relative_to(B)/'cost.json')},'composition':{'nominal_depth':4,'split_max_difference':max(max(r['split_run_vs_uninterrupted'].values()) for r in composition['rows']),'full_joint_interval_depth':0,'D_and_history_not_reset':True,'loss':'retain valid prefix and TOP, nominal diagnosis may continue separately'},'evidence_categories':['source/math conditional','empirical diagnostic','actual-record support'],'new_flights':6,'unused_starts':2};write(out/'map-edge.json',edge)
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 figs=R/'docs/figures/p14r';figs.mkdir(parents=True,exist_ok=True)
 events=read('event-tables-v2/summary.json');fig,ax=plt.subplots(1,2,figsize=(10,3.5))
 for n in ['d02','d03','d05','d06']:
  rr=sorted([x for x in next(z for z in events if z['id']==n)['rows'] if x.get('status')=='REACHED' and x['stage']!='observed-neural-end'],key=lambda x:x['profile_s']);t=[x['profile_s'] for x in rr];ax[0].plot(t,[x['COM_L_m'] for x in rr],'.-',label=n);ax[1].plot(t,[x['COM_W_down_m_s'] for x in rr],'.-',label=n)
 ax[0].axhline(1,color='k',ls='--');ax[0].set_ylabel('COM loss L (m), task0 anchor');ax[1].set_ylabel('Direct COM downward W (m/s)')
 for x in ax:x.set_xlabel('Task profile time (s), checkpoints');x.legend();x.grid(alpha=.3)
 fig.tight_layout();fig.savefig(figs/'event-residuals.png',dpi=160);plt.close(fig)
 fig,ax=plt.subplots(1,2,figsize=(10,3.5));zero=read('C-metrics-v1/0/result.json')['rows']
 for tag in ['round_libm','nonlinear','clip_crossing']:ax[0].semilogy([r['call']*.004 for r in zero],[r['category_radius']['previous'].get(tag,0)+1e-18 for r in zero],label=tag)
 ax[0].set(xlabel='Horizon (s)',ylabel='Zero-set algorithm action radius');ax[0].legend();ax[0].grid(alpha=.3)
 for folder,label in [('C-joint-v6/0/tube.json','Quarter, reduction512'),('C-relations-v8/1/tube.json','Quarter + source relations')]:
  x=read(folder);ax[1].semilogy([r['call']*.004 for r in x['rows']],[r['action_width_max']+1e-18 for r in x['rows']],label=label)
 ax[1].semilogy([r['call']*.004 for r in cont['rows']],[r['action_width_max'] for r in cont['rows']],label='No-reduction resumed93..197');ax[1].axhline(.2,color='k',ls='--');ax[1].set(xlabel='Horizon (s)',ylabel='Action outer width');ax[1].legend(fontsize=8);ax[1].grid(alpha=.3);fig.tight_layout();fig.savefig(figs/'tube-decomposition.png',dpi=160);plt.close(fig)
 write(out/'figures.json',{str(p.relative_to(R)):sha(p) for p in figs.glob('*.png')});print('P14R_FINAL_DELIVERY',len(starts),len(finishes),'measured component walls',sum(measured.values()))
if __name__=='__main__':main()
