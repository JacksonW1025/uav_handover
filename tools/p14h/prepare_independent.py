"""Materialize the frozen selection without changing the common trajectory."""
import sys,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from run_experiment import p5_profile,Experiment
from types import SimpleNamespace

def main():
 out=register(sys.argv[1],'independent 4 seedblocks xthree predeclared methods; selected pool unchanged, exact same task profile, model/source freeze pending publication');sel=B/'selection-v3';choice=json.load(open(sel/'selection.json'));base=json.load(open(R/'config/p14h/p14h-d01-F4-A-before-s142710201.json'));ref=p5_profile(base['p5'],base['p5']['conditions']['p11-case']);jobs=json.load(open(sel/'jobs.json'));rows=[]
 for n,item in enumerate(choice['rows']):
  c=item['candidate'];D,G=c['D'],c['G'];cfg=copy.deepcopy(base);spec=cfg['p5']['conditions']['p11-case'];spec['gaps']['windows_s']=[[0,D],[D+G,D+G+.36]];spec['post_gap_s']=round(ref['cruise_s']-spec['pre_gap_s']-(D+G+.36),9);spec['description']='P14H independent fixed common trajectory; D/G/release side only from frozen finite pool; no result-based case replacement';cfg['p11']['event_mask']=[0,1];cfg['p14h']['resume_side']=c['side'];cfg['p14h']['role']='independent fixed-rule evaluation';p=p5_profile(cfg['p5'],spec)
  # post_gap is a profile-construction input compensated into cruise_s, not
  # an independent motion segment. Verify actual source profile outputs too.
  assert all(p[k]==ref[k] for k in p if k not in ['gaps','post_gap_s']),'common trajectory changed'
  ns=lambda pr:SimpleNamespace(cfg={'p1_speed_m_s':spec['speed_m_s']},pcfg=pr)
  original,current=ns(ref),ns(p);assert Experiment.profile_duration(original)==Experiment.profile_duration(current)
  times=np.arange(-.02,Experiment.profile_duration(original)+p['end_hold_s']+.008,.004)
  assert all(Experiment.p1_profile(original,float(t))==Experiment.p1_profile(current,float(t)) for t in times),'actual motion table changed'
  ident=f'p14h-e{n+1:02d}-{c["id"].lower()}-s{item["seed"]}';path=R/'config/p14h'/f'{ident}.json';write(path,cfg);deltas=[]
  for case in ['d01','d02','d03','d04']:
   def pred(side):
    j=next(k for k,j in enumerate(jobs) if j['case']==case and j['D']==D and j['G']==G and j['side']==side);return json.load(open(sel/f'{j:03d}/result/result.json'))
   before,after=pred('BEFORE'),pred('AFTER');deltas.append(dict(initial=case,action_after_minus_before=(np.array(after['first_action'])-before['first_action']).tolist(),tilt_after_minus_before=after['peak_tilt_deg']-before['peak_tilt_deg'],LP_D_after_minus_before=after['LP_D_m']-before['LP_D_m'],COM_D_after_minus_before=after['COM_D_m']-before['COM_D_m']))
  rows.append(dict(id=ident,seed=item['seed'],side=c['side'],candidate=c,methods=item['methods'],config=str(path.relative_to(R)),config_sha256=sha(path),kind='p5_gap',condition='p11-case',treatment='P11-Z',budget_class='independent',prestart_prediction=dict(model='H1 source-producer-queue with held future fused-target residual; nominal not coverage certificate',source=str((sel/'selection.json').relative_to(R)),prior_initials='all four diagnostic pre-A packets; future independent initial unknown',nominal_predictions=item['nominal_predictions'],conditional_response_directions=deltas,branch='first A resume release BEFORE targeted read, AFTER next permitted read; actual new phase/source initial may differ and is scored, not filtered',premises='nominal 4ms IMU/control, recovered initial downsample state, PRE_COMPLETE producer; transport/producer interposition and future fused errors remain coverage obligations',selection_reason=item['methods'],future_independent_data_used=False),original_source='P14R F4 fixed6s cruise / P13 F4, P14H new D/G/side pool',task_trajectory_exactly_equal=True))
 write(out/'plan.json',dict(rows=rows,starts_cap=12,per_method_credit=4,seed_blocks=4,randomized_order_frozen=True,selection_rules_sha256=sha(sel/'rules.json'),selection_sha256=sha(sel/'selection.json'),same_seed_not_same_initial=True,analysis_layer='deterministic path/serialization/scoring repairs versioned, preserve old results and recheck affected records; no thresholds/model/ranking/selection change',experimental_layer='controller, recorder, physics plugin, weight, runtime config, candidate order, guards, source model/parameters frozen before push',stopping='critical source/identity/time/safety anomaly pauses affected queues; inactive preinitial skips are retained initial differences with strict active source-scope tests; scientific task failure counted and independent queue continues',scope='new mechanism development exposed; independent frozen rule evaluation uses 4 new seed blocks, no population efficiency claim',remaining_budget='4 mechanisms already used; exact planned unique independent starts count, no replacement'))
 print('INDEPENDENT_PLAN',len(rows))
if __name__=='__main__':main()
