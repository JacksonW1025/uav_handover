#!/usr/bin/env python3
"""Locate a failed prospective total-effect scale; never changes release criteria."""
import json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c_platform.accept import task_features
from p11.models import tilt

def main(out):
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True);D=R/'data/p12c-20261026-development';off=D/'prep-safe_event-b1-off';on=D/'prep-safe_event-b1-on';a,plan,ma,ea=task_features(off);b,_,mb,eb=task_features(on);end=min(ea,eb);sel=(a['t']>=0)&(a['t']<=end);t=a['t'][sel];ao=a['tilt'][sel];bo=np.interp(t,b['t'],b['tilt']);diff=ao-bo;k=int(np.argmax(abs(diff)));truthoff=np.array([tilt(q) for q in a['truth_q'][sel]]);truthon=np.interp(t,b['t'],[tilt(q) for q in b['truth_q']]);nearest=int(np.argmin(abs(b['t']-t[k])));ia=int(np.flatnonzero(sel)[k]);source=[]
 for name,parent,d in [('off',off,a),('on',on,b)]:
  n=json.load(open(parent/'analysis/native/native-audit.json'));epoch=float(d['run_wall_ns'][0]-d['t'][0]*1e9);source.append({'arm':name,'captures':[{'profile_interval_s':[(c0-epoch)/1e9 for c0 in c['capture_host_interval_ns']],'sample_us':c['sample_us'],'phase':c['phase'],'guard_age_us':c['guard_age_us'],'activation':c['activation']} for c in n['captures']]})
 arrays={'profile_s':t,'controller_tilt_difference_deg':diff,'held_truth_tilt_difference_deg':truthoff-truthon,'off_controller_tilt_deg':ao,'on_controller_tilt_interp_deg':bo,'off_held_truth_tilt_deg':truthoff,'on_held_truth_tilt_interp_deg':truthon};np.savez_compressed(out/'all-valid-prefix.npz',**arrays)
 doc={'schema':'p12c-dynamic-total-effect-diagnostic-1','admission_unchanged':'NOT_RELEASED; actual predefined controller-cache response exceeds5deg; alternative future streams used only diagnostic, never substitute admission metric','maximum_controller_tilt_difference_deg':float(abs(diff[k])),'maximum_at_profile_s':float(t[k]),'controller_tilts_off_on_deg':[float(ao[k]),float(bo[k])],'held_truth_tilt_difference_same_time_deg':float((truthoff-truthon)[k]),'held_truth_difference_max_all_prefix_deg':float(abs(truthoff-truthon).max()),'at_maximum_cache_ages_us':{'off_LP':int(a['sample_us'][ia]-a['lp_sample'][ia]),'off_att':int(a['sample_us'][ia]-a['att_sample'][ia]),'on_LP':int(b['sample_us'][nearest]-b['lp_sample'][nearest]),'on_att':int(b['sample_us'][nearest]-b['att_sample'][nearest]),'off_truth_att':int(a['sample_us'][ia]-a['truth_q_sample'][ia]),'on_truth_att':int(b['sample_us'][nearest]-b['truth_q_sample'][nearest])},'at_maximum_W_LP_off_on_m_s':[float(a['W'][ia]),float(b['W'][nearest])],'source_capture_intervals':source,'raw_initial_differences':'see independent partial-engineering-review prestate, no fitted correction or phase alignment','scope':'causes not uniquely identified; physical held truth is asynchronously sampled too; scientific success in both arms does not establish timewise equivalence; new SITL0'};(out/'diagnostic.json').write_text(json.dumps(doc,indent=2)+'\n');print('DIFF_AT',doc['maximum_at_profile_s'],doc['maximum_controller_tilt_difference_deg'],doc['held_truth_difference_max_all_prefix_deg'])
if __name__=='__main__':main(Path(sys.argv[1]))
