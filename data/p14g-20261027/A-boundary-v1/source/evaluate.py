"""Scoring is separate from isolated ranking/forecast. No threshold fitting."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *
from p12.score import score
from p12c.features import load
from p13.physics import read as pread,BODY
from p14_motion.analyze import episodes

def cscore(out):
 register(out,'C full5 exposed records, originalv2trivalues, LPcacheheight; score all affected candidatewords');rows=[];baseline_check={}
 for name,c in cases().items():
  folder=B/'C-v2/predictions'/name;run=R/c['raw_run'];adapt=out/name/'input';adapt.mkdir(parents=True);meta={'models':{}}
  for file in sorted(folder.glob('*.npz')):
   data=dict(np.load(file));info=json.load(open(file.with_suffix('.json')));tr=data['trace'].copy();tr[:,1:7]=tr[:,42:48]
   if info['stop']:tr=tr[tr[:,0]<info['stop']['profile_s']]
   np.savez_compressed(adapt/file.name,trace=tr);meta['models'][file.stem]={'stop':info['stop'],'height_modelled':True,'compute_s':info['elapsed_s']}
   if file.stem=='held':
    old=np.load(OLD/'registered-points-v1/predictions'/name/'PRE-phase0.0-jointdelay0.0.npz');baseline_check[name]=float(np.nanmax(abs(data['trace']-old['trace'])));assert baseline_check[name]==0
  write(adapt/'prediction.json',meta);r=score(adapt,run.parent/'analysis-v1/packed',run.parent/'analysis-v1/measured/measurement.json',out/name/'score');rows.append({'id':name,'models':r['models']})
 sums={}
 for model in rows[0]['models']:
  sums[model]={}
  for part in ['tilt','height','task']:
   truth=[x['models'][model]['risk']['observed'][part] for x in rows];pred=[x['models'][model]['risk']['predicted'][part] for x in rows];cmp=[x['models'][model]['risk']['comparisons'][part] for x in rows];sums[model][part]={'actual_fail':truth.count('FAILURE'),'actual_unknown':truth.count('UNKNOWN'),'miss':cmp.count('DANGER_MISS'),'false_alarm':cmp.count('FALSE_ALARM'),'prediction_UNKNOWN':pred.count('UNKNOWN'),'eligible':sum(x['models'][model]['risk']['classification_eligible'][part] for x in rows),'full_trajectory':sum(x['models'][model]['risk']['full_trajectory_eligible'][part] for x in rows),'classifications':dict(zip(cases(),cmp))}
 write(out/'summary.json',{'rows':rows,'summaries':sums,'held_P14R_reproduction_maxabs':baseline_check,'independent_units':5,'exposure':'all retrospective, modelwords/windows notextra records'})

def dscore(out):
 register(out,'H3 retrospective observedoffset0anchors only, rankings already sealedwithoutfuture');rankfile=B/'D-v2/ranking/ranking.json';ranking=json.load(open(rankfile));actual=[];scales=np.array([.1]*4+[4,4,5,.2])
 for name,c in cases().items():
  record=next(x for x in ranking['rows'] if x['case']==name and x['offset_ms']==0);run=R/c['raw_run'];d=load(run,run.parent/'analysis-v1');packet=doc(name);b=packet['plan']['full_source_windows_profile_s'][0][1];hit=np.flatnonzero(~d['stale'].astype(bool)&np.r_[False,d['stale'][:-1].astype(bool)]&(d['t']>=b));j=int(hit[0]) if len(packet['plan']['windows_profile_s']) and len(hit) else int(np.searchsorted(d['t'],b));window=(d['t']>=b)&(d['t']<=b+.5);body,_=pread(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');body=body[(body['phase']==1)&(body['valid']==63)];q=np.searchsorted(body['wall_ns'],d['run_wall_ns'][window],side='right')-1;physical_loss=-body['com_p'][q,2]-packet['initial']['physical_H0_NED_z'];from p11.models import tilt
  observed=np.r_[d['action'][j],[(int(d['sample_us'][j])-int(d['att_sample'][j]))/1000,(int(d['sample_us'][j])-int(d['lp_sample'][j]))/1000],max(tilt(v) for v in d['attitude'][window]),float(max(physical_loss))];model_fit={}
  for m,z in record['models'].items():
   lo=np.array(z['lower']);hi=np.array(z['upper']);outside=np.maximum(0,np.maximum(lo-observed,observed-hi))/scales;model_fit[m]={'observed_inside_all_feature_hull':bool(np.all(outside<=1e-10)),'normalized_distance_to_hull':float(np.linalg.norm(outside)),'outside_axes':np.flatnonzero(outside>1e-10).tolist()}
  # The exact NORMAL alias may be represented by offset-8 but same physicaltest.
  representative=record.get('alias_of',record['id']);positions={k:v.index(representative)+1 for k,v in ranking['rankings'].items()};actual.append({'id':name,'representative':representative,'observed_features':observed.tolist(),'model_fits':model_fit,'ranking_position':positions,'actual_resume_s':float(d['t'][j]) if len(packet['plan']['windows_profile_s']) else None,'task_outcome':json.load(open(run.parent/'analysis-v1/measured/measurement.json'))['task_outcome'],'no_counterfactual_labels':True})
 ranks={}
 for k,order in ranking['rankings'].items():
  representatives={r['representative']:r for r in actual};ranks[k]={'top5_ids':order[:5],'executed_anchor_count_in_top5':sum(x in representatives for x in order[:5]),'new_unexecuted_in_top5':sum(x not in representatives for x in order[:5]),'retrospective_anchor_positions':{r['id']:r['ranking_position'][k] for r in actual},'danger_found_in_top5_observed_anchors_only':sum(representatives[x]['task_outcome']=='FAILURE' for x in order[:5] if x in representatives),'caveat':'unexecutedcandidate outcome/model-discriminability is UNKNOWN, notfailure orsuccess; 5biasedexposed anchors cannot establish rankingefficiency'}
 write(out/'result.json',{'ranking_sha256_before_scoring':sha(rankfile),'actual_anchors':actual,'rank_comparison':ranks,'H3':'INSUFFICIENT independent evidence; actual hull misses denote model inadequacy, notmechanism proof. Selected highest separation canbeNORMAL, differentobjectivefromfindingdanger.','proposed_test_rule':'freeze selector unchanged, compare one topdiscrimination diagnostic vsone topdanger case withmatched initial-source strata, independently collectfusion/cache/firstaction; no executionauthorizedhere'})
if __name__=='__main__':
 {'C':cscore,'D':dscore}[sys.argv[1]](Path(sys.argv[2]))
