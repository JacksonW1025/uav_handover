"""Past-only fixed-model initial uncertainty diagnostic; zero new flights or fitting."""
import sys,json,copy
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p13.isolated import predict
from p9_model import write,sha
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
# Fixed beforehand from declared 0.1 m/s effect scale; other magnitudes are
# explicitly exploratory initial uncertainty, never a confidence region.
variants=[('nominal',None,0),('COM_W_minus0.1','physical_COM_v',-.1),('COM_W_plus0.1','physical_COM_v',.1),('coupled_W_minus0.1','coupled_W',-.1),('coupled_W_plus0.1','coupled_W',.1),('h0_minus0.001','h',-.001),('h0_plus0.001','h',.001),('filter_minus1','rotor_filter',-1.),('filter_plus1','rotor_filter',1.)]
for i in [7,8,9]:
 target=next((R/'data/p13-20261026-development').glob(f'dev{i:02d}-*'))
 src=target/'analysis-v1/packed-physical/prediction-input.json'
 if not src.exists():src=R/'data/p13-20261026-development-predictions-v1'/target.name/'packed/prediction-input.json'
 base=json.load(open(src)); traces={};meta={}
 for label,key,delta in variants:
  d=copy.deepcopy(base);ini=d['initial']
  if key=='physical_COM_v':ini[key][2]+=delta
  elif key=='coupled_W':
   ini['physical_COM_v'][2]+=delta;ini['velocity'][2]+=delta
  elif key=='h':ini[key][0]=float(np.clip(ini[key][0]+delta,-1,1))
  elif key=='rotor_filter':ini[key]=np.clip(np.array(ini[key])+delta,0,1000).tolist()
  dst=out/target.name/label;packed=dst/'packed';packed.mkdir(parents=True);write(packed/'prediction-input.json',d)
  r=predict(packed,R/'data/p13-20261026-freeze/models',dst/'prediction');meta[label]=r
  traces[label]=np.load(dst/'prediction/M5.npz')['trace'];print('SENSITIVITY',target.name,label,flush=True)
 nom=traces['nominal'];B=base['plan']['full_source_windows_profile_s'][1][0]
 for label,key,delta in variants:
  t=traces[label];end=min(t[-1,0],nom[-1,0]);sel=(nom[:,0]<=end);g=nom[sel,0];calc=lambda j:np.interp(g,t[:,0],t[:,j])-nom[sel,j]
  rows.append({'id':target.name,'variant':label,'initial_key':key,'delta':delta,'M5_stop':meta[label]['models']['M5']['stop'],'common_model_prefix_end_s':float(end),'max_tilt_difference_deg':float(max(abs(calc(7)))),'max_COM_H_difference_m':float(max(abs(calc(52)))),'max_COM_W_difference_m_s':float(max(abs(calc(53)))),'B_before_covered':bool(B<=end),'B_before_COM_W_difference_m_s':float(np.interp(B,t[:,0],t[:,53])-np.interp(B,nom[:,0],nom[:,53])) if B<=end else None,'B_before_COM_H_difference_m':float(-np.interp(B,t[:,0],t[:,52])+np.interp(B,nom[:,0],nom[:,52])) if B<=end else None})
write(out/'summary.json',{'schema':'p13-initial-sensitivity-1','rows':rows,'frozen_model_sha256':sha(R/'data/p13-20261026-freeze/models/models.json'),'scope':'fixed model diagnostic using development past-only inputs and predeclared symmetric uncertainty variations; not an actual intervention, not formal prediction scores, not a proved reachable set, no initial-state adjustment of blocked experimental contrasts','heldout_results_used_for_fitting':False,'SITL_starts':0})
