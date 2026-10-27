"""Static scientific deliverables. No model fitting or score changes."""
import sys,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import OUT,records

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
 summary=json.load(open(OUT/'evaluation-v1/summary.json'))['groups']['formal'];names=['M3','M4','M5','G','M14']
 fig,axes=plt.subplots(1,3,figsize=(12,4))
 for ax,comp in zip(axes,['tilt','height','task']):
  bottom=np.zeros(len(names))
  for label,color in [('DANGER_MISS','#c44'),('FALSE_ALARM','#e99d2b'),('UNKNOWN','#8e8e8e')]:
   vals=[sum(v for k,v in summary[n][comp]['comparisons'].items() if k==label or label=='UNKNOWN' and k.startswith('UNKNOWN')) for n in names]
   ax.bar(names,vals,bottom=bottom,label=label,color=color);bottom+=vals
  ax.set_title(comp+' /66 retrospective flights');ax.set_ylabel('Count');ax.set_ylim(0,18);ax.grid(axis='y',alpha=.2)
 axes[-1].legend(fontsize=8);fig.suptitle('Corrected feedback is not a reliable safety-admission model');fig.tight_layout()
 for ext in ['png','pdf']:fig.savefig(out/f'component-errors.{ext}',dpi=180)
 plt.close(fig)
 joint=json.load(open(OUT/'theory-v2/joint-attempt.json'));fig,ax=plt.subplots(figsize=(7,4))
 for r in joint['results']:
  ax.semilogy([x['calls'] for x in r['rows']],[x['action_interval_width_max'] for x in r['rows']],marker='o',ls='--' if r['box'] else '-',label=('independent box' if r['box'] else 'shared generators')+f", radius={r['radius']}")
 ax.axhline(2,color='k',alpha=.4);ax.set_xlabel('Control calls (4 ms each)');ax.set_ylabel('Max action interval width');ax.set_title('Conditioned reduced map only: source angular extension fails at step 1');ax.legend(fontsize=8);ax.grid(alpha=.2);fig.tight_layout()
 for ext in ['png','pdf']:fig.savefig(out/f'finite-joint-attempt.{ext}',dpi=180)
 plt.close(fig)
 x=next(r for r in records() if r['id']=='p13-F4-b1-A');d=dict(np.load(x['packed']/'measurement.npz'));t=d['profile_s'];q=d['attitude'];tilt=np.degrees(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)))
 fig,ax=plt.subplots(figsize=(8,4));sel=(t>=12.8)&(t<=min(t[-1],15));ax.plot(t[sel],tilt[sel],color='k',label='actual cached attitude (sampled)')
 for n in ['M5','G','M14']:
  p=x['prediction'] if n=='M5' else OUT/'candidate-v1/predictions'/x['id'];tr=np.load(p/(n+'.npz'))['trace'];ss=(tr[:,0]>=12.8)&(tr[:,0]<=15);ax.plot(tr[ss,0],tr[ss,7],label=n)
 ax.axhline(45,color='r',ls='--',label='45 deg');ax.set_xlabel('Original absolute task time (s)');ax.set_ylabel('Tilt (deg)');ax.set_title('F4 block1 single A: geometric correction does not remove danger miss');ax.legend(fontsize=8);ax.grid(alpha=.2);fig.tight_layout()
 for ext in ['png','pdf']:fig.savefig(out/f'F4-A-miss.{ext}',dpi=180)
 plt.close(fig)
if __name__=='__main__':main()
