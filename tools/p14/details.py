"""Supplement independent crossing/recovery/component metrics, same scores."""
import sys,json,collections
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import records,write,OUT
from p14.evaluate import crossing,stages
from p12c.features import load
from p13.physics import read,BODY

def settled(t,p,v,w,r,s,start):
 good=(np.linalg.norm(p-r,axis=1)<=.2)&(np.linalg.norm(v-s,axis=1)<=.1)&(np.linalg.norm(w,axis=1)<=.1)&(t>=start)
 since=None
 for k in range(len(t)):
  if not good[k] or k and t[k]-t[k-1]>.020:since=None
  if good[k]:
   if since is None:since=t[k]
   if t[k]-since>=2:return float(since)
 return None

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);res=[]
 for r in records():
  doc=json.load(open(r['packed']/'prediction-input.json'));a=r['analysis'];d=load(r['target']/'run',a);t=d['t'];plan=doc['plan'];obs=json.load(open(r['measured']));end=min(obs['observed_profile_end_s'],plan['nominal_horizon_profile_s']);base=plan['common_first_gap_profile_s'];mask=(t>=base)&(t<=end)
  origin=float(np.interp(base,t,d['position'][:,2]));height=d['position'][:,2]-origin
  s,ev=stages(d,plan,r['id'],end);observed_settle=settled(t[t<=end],d['position'][t<=end],d['velocity'][t<=end],d['omega'][t<=end],d['target_p'][t<=end],d['target_v'][t<=end],plan['stream_end_profile_s'])
  body,_=read(r['target']/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');body=body[body['phase']==1]
  row={'id':r['id'],'group':r['group'],'observed_fulltopic_components':obs['whole'],'observed_cached_height_crossing':crossing(t[mask],height[mask],1),'observed_cached_recovery_start':observed_settle,'models':{}}
  for name in ['M3','M4','M5','G','M14']:
   pp=OUT/'candidate-v1/predictions'/r['id'] if name in ['G','M14'] else r['prediction'];tr=np.load(pp/(name+'.npz'))['trace'];pt=tr[:,0];meta=json.load(open(pp/'prediction.json'))['models'][name];known=np.isfinite(tr).all(axis=1);tr=tr[:np.flatnonzero(~known)[0]] if not known.all() else tr;pt=tr[:,0];m=(pt>=base)&(pt<=end);z0=np.interp(base,pt,tr[:,3]);predcross=crossing(pt[m],tr[m,3]-z0,1)
   actualcross=row['observed_cached_height_crossing'];td=None if actualcross is None or predcross is None else [predcross[0]-actualcross[1],predcross[1]-actualcross[0]]
   settle=settled(pt,tr[:,1:4],tr[:,4:7],tr[:,39:42],tr[:,28:31],tr[:,31:34],plan['stream_end_profile_s'])
   btime=ev['B_plan'];B=None
   if end>=btime and pt[-1]>=btime and name in ['M5','G','M14']:
    ix=int(np.searchsorted(t,btime)-1);k=int(np.searchsorted(body['wall_ns'],d['run_wall_ns'][ix],side='right')-1);k0=int(np.searchsorted(body['wall_ns'],round(d['run_wall_ns'][ix]-t[ix]*1e9),side='right')-1)
    realL=body['com_p'][k0,2]-body['com_p'][k,2];realW=-body['com_v'][k,2];predL=np.interp(btime,pt,tr[:,52])-np.interp(0,pt,tr[:,52]);predW=np.interp(btime,pt,tr[:,53]);realD=max(0,float(np.max(body['com_p'][k0,2]-body['com_p'][k0:k+1,2])));predD=max(0,float(np.max(tr[(pt>=0)&(pt<btime),52]-np.interp(0,pt,tr[:,52]))))
    B={'COM_L_error_m':float(predL-realL),'COM_W_error_m_s':float(predW-realW),'COM_D_error_m':float(predD-realD),'actual_L':float(realL),'actual_W':float(realW),'different_source_times_retained':True}
   row['models'][name]={'height_first_witness':predcross,'height_prediction_minus_cached_witness_interval_s':td,'recovery_start_s':settle,'recovery_comparison':'BOTH_SETTLED' if settle is not None and observed_settle is not None else 'UNKNOWN_OR_NOT_SETTLED','recovery_error_s':None if settle is None or observed_settle is None else settle-observed_settle,'B_before_physical_errors':B,'prediction_stop':meta.get('stop')}
  write(out/r['id']/'details.json',row);res.append(row)
 write(out/'summary.json',{'records':res,'scope':'crossings use cache and original A height baseline; canonical fulltopic scoring remains separate. All new results retrospective. Recovery original P0 criteria with2s dwell; absence is not success.','new_SITL':0})
if __name__=='__main__':main()
