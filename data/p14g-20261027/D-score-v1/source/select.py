"""Model-discrimination test selection. Child only sees past inputs+plans.
Finite model prediction sets, NOT certified future physical outer sets.
"""
import sys,json,time,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.model import forecast
from p14g.delivery import Word
from p14g.common import write,limit

def features(r,doc):
 a,b=doc['plan']['full_source_windows_profile_s'][0];t=r['trace'][:,0];stale=r['trace'][:,34].astype(bool);hit=np.flatnonzero(~stale & np.r_[False,stale[:-1]] & (t>=b-1e-6));idx=int(hit[0]) if len(hit) else int(min(len(t)-1,np.searchsorted(t,b)));window=(t>=b)&(t<=b+.5);cache=r['cache_samples'][idx];sample=doc['initial']['sample_us']+int(round((t[idx]-doc['initial']['profile_s'])/.004))*4000;vec=np.r_[r['trace'][idx,8:12],(sample-cache)/1000,np.max(r['trace'][window,7]),np.max(r['states'][window,2]-doc['initial']['physical_H0_NED_z'])];return vec,{'predicted_resume_s':float(t[idx]) if len(hit) else None,'first_action_profile_s':float(t[idx]),'stop':r['stop'],'full_feature_window':bool(t[-1]>=b+.5-1e-6)}

def main():
 inp,out=map(Path,sys.argv[1:3]);out.mkdir();assert not any((Path('/home/car/uav_handover')/'data').iterdir()) and not any((Path('/home/car/uav_handover')/'export').iterdir());limit(450);P=dict(np.load(inp/'policy.npz'));lib=inp/'libop.bin';pool=json.load(open(inp/'pool.json'));scales=np.array([.1]*4+[4.,4.,5.,.2]);words=[Word(),Word(.002,0,poll_period_s=.006),Word(0,.004,poll_period_s=.010),Word(0,0,producer_order='POST')];rows=[];cache={};start=time.perf_counter()
 for item in pool:
  identity=item['id'];name=item['case'];offset=item['offset_ms'];d=json.load(open(inp/(name+'.json')));a,b=d['plan']['full_source_windows_profile_s'][0];noevent=not len(d['plan']['windows_profile_s']);packet=copy.deepcopy(d)
  if not noevent:
   packet['plan']['windows_profile_s'][0][1]+=offset/1000;packet['plan']['full_source_windows_profile_s'][0][1]+=offset/1000
  end=packet['plan']['full_source_windows_profile_s'][0][1]+.5;key=name if noevent else identity
  if key in cache:
   rows.append(dict(cache[key],id=identity,alias_of=cache[key]['id']));continue
  models={};meta={}
  for model in ['F','T','FT']:
   values=[];details=[]
   for word in ([Word()] if model=='F' else words):
    q=copy.deepcopy(packet)
    if model=='T':q['initial']['p14g_innovation']['mode']='held'
    result=forecast(q,{},P,word=word,observer_library=lib,limit=end);v,detail=features(result,q);values.append(v);details.append(detail)
   z=np.array(values);models[model]={'lower':z.min(axis=0).tolist(),'upper':z.max(axis=0).tolist(),'points':z.tolist(),'scope':'finite conditional model/schedule hypothesis set, not certified future EKF/physical uncertainty'};meta[model]=details
  F=models['F'];T=models['T'];lo=np.maximum(np.array(F['lower']),np.array(T['lower']));hi=np.minimum(np.array(F['upper']),np.array(T['upper']));gap=np.maximum(0,lo-hi)/scales;separation=float(np.linalg.norm(gap));f0=np.array(F['points'][0]);danger=min((45-f0[6])/45,1-f0[7]);row={'id':identity,'case':name,'offset_ms':offset,'planned_A_end_s':packet['plan']['full_source_windows_profile_s'][0][1],'no_event_control':noevent,'models':models,'model_details':meta,'separation':separation,'standardized_axis_gaps':gap.tolist(),'nominal_danger_margin':float(danger),'actual_future_used':False,'physical_configuration_key':key};rows.append(row);cache[key]=row;print('D_CANDIDATE',identity,round(separation,4),flush=True)
 unique=list(cache.values());ranks={'uniform':[r['id'] for r in sorted(unique,key=lambda x:(x['case'],x['offset_ms']))],'nominal_danger':[r['id'] for r in sorted(unique,key=lambda x:(round(x['nominal_danger_margin'],12),x['case'],x['offset_ms']))],'set_separation':[r['id'] for r in sorted(unique,key=lambda x:(-round(x['separation'],12),x['case'],x['offset_ms']))]};write(out/'ranking.json',{'rows':rows,'rankings':ranks,'pool_size':len(rows),'distinct_physical_configurations':len(unique),'future_labels_visible':False,'elapsed_s':time.perf_counter()-start,'normal_alias_policy':'all7normal measurement bookmarks use same original task andoriginalfeaturewindow; one physical test, not7independent experiments','interpretation':'discrimination among declared finite hypothesis sets only; requires independent observation to identify physical mechanism. Min hull gap is conservative for these finite sets, not uncertainty-certified.'})
if __name__=='__main__':main()
