"""Separate frozen score-v2 common-window labels from full-forward nominal risk.
Old scores are preserved. Lateness at an observed failure remains a reported
failure-time miss even when the full forecast crosses the threshold later.
"""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p12.score import bundle
from p11.models import tilt

def bracket(t,y,threshold):
 ix=np.flatnonzero(y>threshold)
 if not len(ix):return None
 j=int(ix[0]);return [float(t[max(0,j-1)]),float(t[j])]

def main():
 out=register(sys.argv[1],'analysis-only scope separation: old P12v2 risk uses observed_end common window; full-forward classifications and first-cross brackets computed separately, no threshold/model/old-grade change',thresholds={'tilt_deg':45,'LP_loss_m':1},no_fit=True);rows=[];plan=json.load(open(B/'independent-plan-v2/plan.json'))
 for n,row in enumerate(plan['rows']):
  target=B/'runs'/row['id'];info=json.load(open(target/'information.json'));analysis=R/info['source_analysis'] if info.get('source_analysis') else target/'analysis-v1';packed=analysis/'packed';obs=dict(np.load(packed/'measurement.npz'));doc=json.load(open(packed/'prediction-input.json'));m=json.load(open(analysis/'measured/measurement.json'));a=doc['plan']['common_first_gap_profile_s'];end=doc['plan']['horizon_profile_s'];ot=obs['profile_s'];mask=(ot>=a)&(ot<=end);ot=ot[mask];angles=np.array([tilt(q) for q in obs['attitude'][mask]]);oz0=float(np.interp(a,obs['profile_s'],obs['position'][:,2]));loss=obs['position'][mask,2]-oz0;observed={'tilt':bracket(ot,angles,45),'height':bracket(ot,loss,1)};ev=B/f'evaluation-e{n+1:02d}-v1';meta=json.load(open(ev/'score-input/prediction.json'));old=json.load(open(ev/'score/score.json'))['models'];models={}
  for name in ['held','source-queue']:
   tr=np.load(ev/'score-input'/(name+'.npz'))['trace'];good=(tr[:,0]>=a)&(tr[:,0]<=end);v=tr[good];z0=float(np.interp(a,tr[:,0],tr[:,3]));height=v[:,3]-z0;full=bool(meta['models'][name]['stop'] is None and tr[-1,0]>=end-.008);r=bundle(float(max(v[:,7])),float(max(height)),full,m['whole']['max_tilt_deg'],m['whole']['max_altitude_loss_m'],not m['censored'],True);pred={'tilt':bracket(v[:,0],v[:,7],45),'height':bracket(v[:,0],height,1)};models[name]=dict(full_forward_risk=r,old_common_window_risk=old[name]['risk'],first_cross_brackets=pred,observed_first_cross_brackets=observed,delay_intervals_s={c:None if pred[c] is None or observed[c] is None else [pred[c][0]-observed[c][1],pred[c][1]-observed[c][0]] for c in ['tilt','height']},common_prefix_misses_retained=old[name]['risk']['comparisons'],forward_tilt_peak=float(max(v[:,7])),forward_LP_loss=float(max(height)))
  rows.append(dict(id=row['id'],models=models,censored=m['censored'],scope='common score limited to min(observed end, task end); full_forward uses only declared planned horizon; actual future only scoring'))
 write(out/'result.json',dict(rows=rows,old_scores_not_rewritten=True,denominator='12 flights /4seed blocks; height observed6fail+6unknown, fullobservations2; event windows/model versions not extra independent samples',interpretation='full-task positive prediction can still be too late at the real failure time. Preserve all3 height common-prefix misses and1 task common-prefix miss; do not hide them with full task OR.'))
 print('RISK_SCOPE',[(r['id'].split('-')[1],r['models']['source-queue']['full_forward_risk']['comparisons'],r['models']['source-queue']['delay_intervals_s']['height']) for r in rows])
if __name__=='__main__':main()
