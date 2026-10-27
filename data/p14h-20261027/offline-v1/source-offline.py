"""Finite source branch/difference experiment. Child only sees past packet+plan."""
import sys,json,copy,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p14h.model import forecast
from p14h.delivery import Word

def mutate(doc,axis,delta):
 d=copy.deepcopy(doc);w=d['plan']['windows_profile_s'];full=d['plan']['full_source_windows_profile_s'];a,b=w[0];i=d['initial']
 if axis=='release':
  reads=[i['profile_s']+.004*k for k in range(1,600) if (i['call_index']+k-1)%2==0];boundary=next(t for t in reads if t>b+.0002);P=boundary+delta;d['plan']['p14h_cells']=[{'index':0,'publication_s':P,'delivery_s':P,'boundary_s':boundary}]
 elif axis=='duration':w[0][1]=b+delta
 elif axis=='interval':
  if len(w)<2:raise ValueError('singleA has no B; not inventing second event')
  dur=w[1][1]-w[1][0];w[1]=[w[1][0]+delta,w[1][0]+delta+dur]
 return d

def compute(inp,job,out):
 out.mkdir();limit(30);d=json.load(open(inp/(job['case']+'.json')));d=mutate(d,job['axis'],job['delta_s']) if job['axis']!='base' else d;P=dict(np.load(inp/'policy.npz'));start=time.perf_counter();r=forecast(d,{},P,word=Word(),observer_library=inp/'libop.bin');np.savez_compressed(out/'trace.npz',**{k:v for k,v in r.items() if isinstance(v,np.ndarray)});tr=r['trace'];s=r['states'];H0=d['initial']['physical_H0_NED_z'];lp0=d['initial']['LP_H0_NED_z'];metrics=[]
 for gi,(a,b) in enumerate(d['plan']['windows_profile_s']):
  for win in [.064,.5,2.]:
   m=(tr[:,0]>=b)&(tr[:,0]<=b+win);inds=np.flatnonzero(m)
   if not len(inds):metrics.append({'gap':gi,'window_s':win,'status':'NOT_REACHED'});continue
   z=inds[0];metrics.append({'gap':gi,'window_s':win,'status':'FULL' if tr[-1,0]>=b+win-.004 else 'TRUNCATED','first_action':tr[z,8:12].tolist(),'peak_tilt_deg':float(max(tr[m,7])),'LP_D_m':float(max(tr[m,46]-lp0)),'COM_D_m':float(max(s[m,2]-H0)),'last_W':float(s[inds[-1],5]),'count':len(inds)})
 rows={k:v for k,v in r.items() if not isinstance(v,np.ndarray)};rows.update(job=job,metrics=metrics,elapsed_s=time.perf_counter()-start,whole_tilt_peak=float(max(tr[:,7])),whole_LP_D=float(max(tr[:,46]-lp0)),whole_COM_D=float(max(s[:,2]-H0)),predicted_input_source='past initial+predeclared plan only; held initial fused-target residual, no decayclaim',full_requested_horizon=d['plan']['horizon_profile_s'],actual_end_profile_s=float(tr[-1,0]));write(out/'result.json',rows)

def main():
 if sys.argv[1]=='child':compute(Path(sys.argv[2]),json.load(open(sys.argv[3])),Path(sys.argv[4]));return
 out=register(sys.argv[1],'H1/H2 samebranch and crossboundary finite localresponse; originalinitials and held sourceOP, no futureactual',budget_CPU_s=2400);inp=out/'inputs';inp.mkdir()
 import shutil
 cases=json.load(open(R/'config/p14h/protocol-v1.json'))['cases']
 for n,c in cases.items():shutil.copyfile(R/c['input'],inp/(n+'.json'))
 shutil.copyfile(R/'data/p13-20261026-freeze/models/policy.npz',inp/'policy.npz');shutil.copyfile(R/'data/p14r-20261027/offline-build-v2/libop.bin',inp/'libop.bin')
 axes=json.load(open(R/'config/p14h/protocol-v1.json'))['offline_axes'];jobs=[]
 for n in cases:
  jobs.append({'case':n,'axis':'base','delta_s':0.,'role':'reference'})
  if n=='d04':continue
  for axis,key in [('release','release_offset_ms'),('duration','A_duration_delta_ms'),('interval','recovery_interval_delta_ms')]:
   if axis=='interval' and n in ['d02','d03']:continue
   ds=set(axes[key]);ds.update([-.75,-.25,.25,.75,-1,1,-.5,.5])
   for delta in sorted(ds):jobs.append({'case':n,'axis':axis,'delta_s':delta*.001,'role':'finite difference and held-out step validation; not dataholdout'})
 write(out/'jobs.json',jobs);used=0
 for j,job in enumerate(jobs):
  if used+30>2400:write(out/'not-computed.json',{'remaining':jobs[j:],'reason':'offline axes CPU budget'});break
  jf=out/f'job-{j:03d}.json';write(jf,job);target=out/f'{j:03d}';row=run([PY,Path(__file__),'child',inp,jf,target/'result'],target,cpu=30,wall=40);used+=row['CPU_s'];print('P14H_OFFLINE',j,row['rc'],round(used,2),flush=True)
 write(out/'execution.json',{'attempted':j+1,'expected':len(jobs),'CPU_s':used,'alljobs_preserved':True})
if __name__=='__main__':main()
