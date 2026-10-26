#!/usr/bin/env python3
"""Use only required arms for each predeclared contrast; never substitute missing NORMAL."""
import json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import write
from p12c.features import load,compare
F=R/'data/p12-cont-20261026-formal';D=R/'data/p12-cont-20261026-delivery-v2'
cases=json.load(open(D/'cases.json'));rows=[];pairs=[]
for block in range(1,5):
 for ph in [1,2]:
  ids={b:f'b{block}-ph{ph}-{b}' for b in ['NORMAL0','NORMAL1','A','B','AB','REPAIR']}
  for label,req in [('A-N',['A','NORMAL0','NORMAL1']),('B-N',['B','NORMAL0','NORMAL1']),('AB-N',['AB','NORMAL0','NORMAL1']),('AB-A-B+N',['AB','A','B','NORMAL0','NORMAL1']),('REPAIR-AB',['REPAIR','AB'])]:
   row={'block':block,'phase':ph,'family':'F4' if block==2 else 'F2','contrast':label,'required':[ids[b] for b in req]}
   if not all(ids[b] in cases for b in req):row.update(status='INCOMPLETE_NO_SUBSTITUTION',missing=[ids[b] for b in req if ids[b] not in cases]);rows.append(row);continue
   complete=all(not cases[ids[b]]['censored'] for b in req);row['status']='COMPLETE_REQUIRED_ARMS' if complete else 'CENSORED_FULL_PEAK_NOT_ESTIMABLE';row['effects']={}
   for metric in ['max_tilt_deg','max_altitude_loss_m']:
    y={b:cases[ids[b]]['measurement']['whole'][metric] for b in req}
    value=y['REPAIR']-y['AB'] if label=='REPAIR-AB' else y['AB']-y['A']-y['B']+(y['NORMAL0']+y['NORMAL1'])/2 if label=='AB-A-B+N' else y[label.split('-')[0]]-(y['NORMAL0']+y['NORMAL1'])/2
    row['effects'][metric]=value if complete else None
   if label=='REPAIR-AB':
    ab=load(F/ids['AB']/'run',F/ids['AB']/'analysis');rp=load(F/ids['REPAIR']/'run',F/ids['REPAIR']/'analysis');doc=json.load(open(F/ids['AB']/'analysis/packed/prediction-input.json'));first=doc['plan']['common_first_gap_profile_s'];end=min(doc['plan']['nominal_horizon_profile_s'],ab['t'][-1],rp['t'][-1]);grid=np.arange(first,end,.004);table=np.asarray(doc['plan']['profile']['table']);jt=np.clip(np.floor((grid-doc['plan']['profile']['table_t0_s'])/.004+1e-8).astype(int),0,len(table)-1);ref=table[jt,:3];cost={}
    for name,d in [('AB',ab),('REPAIR',rp)]:
     j=np.searchsorted(d['t'],grid,side='right')-1;e=np.linalg.norm(d['position'][j]-ref,axis=1);cost[name]={'squared_tracking_integral_m2s':float(.004*np.sum(e*e)),'tracking_peak_m':float(e.max()),'tracking_rms_m':float(np.sqrt(np.mean(e*e))),'full_task_result':cases[ids[name]]['task_outcome'],'world_height':cases[ids[name]]['absolute_world_height'],'recovery':cases[ids[name]]['measurement']['joint_recovery_after_final_capture']}
    row['common_window_profile_s']=[first,end];row['common_cost']=cost;row['prestate']=compare(ab,rp,[first-.5,first]);row['strict_pair']=False;row['scope']='same frozen block/assignment, observed initial uncertainty retained; partial block supports this predeclared two-arm contrast only, not full six-arm inference';pairs.append(row)
   rows.append(row)
write(D/'available-predeclared-contrasts.json',rows);write(D/'repair-common-window-and-prestate.json',pairs)
print('AVAILABLE_CONTRASTS',sum(r['status']=='COMPLETE_REQUIRED_ARMS' for r in rows),'repair pairs',len(pairs))
