"""Retrospective mechanism check of pre-fixed samefamily/G B/AB pairs.
Uses actual recipient truth explicitly; never a policy forecast or query update.
"""
import sys,json
from pathlib import Path
sys.path.insert(0,'tools')
from p16.common import B,write,now
from p16.reuse import gate,EPS_H,EPS_T
r=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False,parents=True);truth=json.load(open(r/'truth.json'));pool=json.load(open(B/'frozen/pool.json'));initial=json.load(open(B/'frozen/initial-predictions.json'));seed=json.load(open(r/'seed2.json'))['truth'];records=[]
for name,t in [('main',truth),('seed2_fixed6',seed)]:
 for c in pool:
  if c['prefix']!='B' or c['id'] not in t:continue
  rc=next(x for x in pool if x['family']==c['family'] and x['G']==c['G'] and x['prefix']=='AB')
  if rc['id'] not in t:continue
  a,b=t[c['id']],t[rc['id']];ac,bc=a.get('capture_suffix'),b.get('capture_suffix');item=dict(dataset=name,donor=c['id'],receiver=rc['id'],actual_recipient_inputs_used=True,for_selection=False,scope='posthoc mechanism only; does not add to onlineR acceptedclasses or savings',donor_B_reached=a['B_plan_reached'],receiver_B_reached=b['B_plan_reached'],receiver_prefix_failed=b['prefix_failed_before_B'])
  if not ac or not bc or not ac.get('available',False) or not bc.get('available',False):item.update(status='MISSING_OR_NOT_REACHED_CAPTURE',state_gate=None);records.append(item);continue
  ok,why=gate(ac.get('signature'),bc.get('signature'));item.update(status='OBSERVED_EMPIRICAL_CONDITION_CHECK',state_gate=ok,condition=why,donor_branch=ac['branch_compatible'],receiver_branch=bc['branch_compatible'],domain_including_nominalword=ok and ac['branch_compatible'] and bc['branch_compatible'],both_suffix_complete=bool(a['complete'] and b['complete']))
  ma=initial[c['id']].get('capture_suffix');mb=initial[rc['id']].get('capture_suffix')
  if ma and mb:
   loss_prediction=max(0.,mb['delta_loss']+ac['delta_loss']-ma['delta_loss']);tilt_prediction=mb['peak_tilt']+ac['peak_tilt']-ma['peak_tilt'];item.update(receiver_actual_suffix_loss=bc['delta_loss'],receiver_actual_suffix_tilt=bc['peak_tilt'],diagnostic_local_prediction_loss=loss_prediction,diagnostic_local_prediction_tilt=tilt_prediction,suffix_loss_residual=bc['delta_loss']-loss_prediction,suffix_tilt_residual=bc['peak_tilt']-tilt_prediction,empirical_height_budget=EPS_H,empirical_tilt_budget=EPS_T,residual_is_exact_only_when_both_complete=bool(a['complete'] and b['complete']),actual_receiver_L=bc['L_before'],actual_receiver_D=bc['D_before'],actual_receiver_prefix_tilt=bc['prefix_tilt'])
  records.append(item)
write(out/'pairs.json',dict(time=now(),records=records,source='prefixed24 main andfixed6 seed2, samefamily/G/suffixhash pairs, not new groups',status='RETROSPECTIVE_MECHANISM_ONLY',parameters_changed=False,original_online_R_scores_unchanged=True))
