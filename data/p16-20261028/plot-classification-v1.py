"""Finite-grid labels. Censored height is UNKNOWN, never an exact full peak."""
import sys,json
from pathlib import Path
sys.path.insert(0,'tools')
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from p16.common import B
from p16.quality import curve_key
r=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False,parents=True);d=json.load(open(r/'delivery.json'));pool=json.load(open(B/'frozen/pool.json'));truth=json.load(open(r/'truth.json'));methods={'SITL truth':truth,'EE q0':json.load(open(B/'frozen/initial-predictions.json'))}
for name,p in [('G q8','G'),('R q8','R')]:methods[name]=json.load(open(B/f'policies/{p}/maps/q08.json'))['prediction']
for name,file in [('A_grid','A_grid-maps.json'),('A_cheap','A_cheap-maps.json')]:
 q=d['methods'][name]['first_persistent_joint_quality'];maps=json.load(open(r/file));chosen=maps[-1] if q is None else next(x for x in maps if x['query']==q);methods[f"{name} q{chosen['query']}"+(' (not attained)' if q is None else ' *')]=chosen['prediction']
colors=ListedColormap(['#b8b8b8','#66b981','#df7064']);code={'UNKNOWN':0,'SUCCESS':1,'FAIL':2};fig,axes=plt.subplots(4,3,figsize=(16,13))
for row,curve in enumerate(sorted({curve_key(c) for c in pool})):
 cells=sorted([c for c in pool if curve_key(c)==curve],key=lambda x:x['G'])
 for col,component in enumerate(['tilt','height','task']):
  ax=axes[row,col];a=np.array([[code[pr[c['id']][component]] for c in cells] for pr in methods.values()]);ax.imshow(a,cmap=colors,vmin=0,vmax=2,aspect='auto')
  ax.set_xticks(range(len(cells)),[f"{c['G']:.2f}" for c in cells]);ax.set_yticks(range(len(methods)),list(methods) if col==0 else []);ax.set_title(curve+' | '+('LP loss' if component=='height' else component))
  for j,c in enumerate(cells):
   for k,(method,pr) in enumerate(methods.items()):
    text={'SUCCESS':'S','FAIL':'F','UNKNOWN':'?'}[pr[c['id']][component]]
    if k==0 and truth[c['id']]['prefix_failed_before_B'] is True and component=='task':text+='A'
    ax.text(j,k,text,ha='center',va='center',fontsize=9)
  if row==3:ax.set_xlabel('Recovery interval G (s)')
fig.legend(handles=[Patch(color=colors(i),label=l) for i,l in enumerate(['UNKNOWN','SUCCESS class','FAIL witness/class'])],loc='lower center',ncol=3);fig.suptitle('Finite grid; * first persistent joint-quality point; FA = failure already before B',y=.995);fig.tight_layout(rect=[0,.035,1,.98]);fig.savefig(out/'finite-grid-classes.png',dpi=150);plt.close(fig)
# Actual observed peaks are lower bounds on censored records, not full-trajectory maxima.
fig,axes=plt.subplots(2,4,figsize=(16,7))
for k,curve in enumerate(sorted({curve_key(c) for c in pool})):
 cells=sorted([c for c in pool if curve_key(c)==curve],key=lambda x:x['G'])
 for row,(field,limit,unit) in enumerate([('peak_tilt',45,'deg'),('peak_loss',1,'m LP loss')]):
  ax=axes[row,k]
  for c in cells:
   y=truth[c['id']][field];complete=truth[c['id']]['complete'];ax.plot(c['G'],y,'ko' if complete else 'k^',ms=5)
   if not complete:ax.annotate('',xy=(c['G'],y+(1.5 if row==0 else .10)),xytext=(c['G'],y),arrowprops=dict(arrowstyle='->',color='k'))
  for name,p in [('EE0',methods['EE q0']),('G8',methods['G q8']),('R8',methods['R q8'])]:ax.plot([c['G'] for c in cells],[p[c['id']].get(field,np.nan) for c in cells],'--',label=name)
  ax.axhline(limit,color='r',lw=1);ax.set_title(curve);ax.set_ylabel(unit);ax.grid(alpha=.2)
  if row==1:ax.set_xlabel('G (s)')
axes[0,0].legend();fig.suptitle('Circle = complete measured peak; triangle + arrow = censored lower bound; dashed = numeric model proxy',fontsize=10);fig.tight_layout(rect=[0,0,1,.95]);fig.savefig(out/'peaks-with-censoring.png',dpi=150);plt.close(fig)
