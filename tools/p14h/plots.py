"""Scientific figures from final evidence only; no fitting or event alignment."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p13.physics import read,BODY
from p12c.features import load

def main():
 evidence=Path(sys.argv[1]);out=register(sys.argv[2],'report figures, full four blocks retained; absolute task origin, no capture/peak alignment');import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 rows=json.load(open(evidence/'observed.json'))['rows'];colors={'BEFORE':'tab:blue','AFTER':'tab:orange'};fig,ax=plt.subplots(2,2,figsize=(10,7));points={}
 for r in rows:
  c=r['candidate'];points.setdefault((c['D'],c['G']),[]).append(r);color=colors[r['side']]
  if r['resume_action'] is not None:ax[0,1].scatter(r['actual_read'][0]['publish_to_read_ms'],r['resume_action'][2],c=color)
  ax[1,0].scatter(c['D'],45-r['peak_tilt'],c=color);ax[1,1].scatter(c['G'],1-r['measured_LP_loss'],c=color)
 for (D,G),rs in points.items():
  color=colors[rs[0]['side']] if len({r['side'] for r in rs})==1 else 'gray';ax[0,0].scatter(D,G,c=color);text=rs[0]['id'].split('-')[1] if len(rs)==1 else str(len(rs))+' runs (4 BEFORE/4 AFTER)';ax[0,0].annotate(text,(D,G),xytext=(6,10),textcoords='offset points',fontsize=8)
 for a,(x,y) in zip(ax.ravel(),[('A duration (s)','Recovery interval (s)'),('Publish to read (ms)','First resumed action[2]'),('A duration (s)','Tilt margin (deg)'),('Recovery interval (s)','Frozen LP loss margin (m)')]):a.set_xlabel(x);a.set_ylabel(y);a.grid(alpha=.25)
 fig.suptitle('P14H: blue BEFORE, orange AFTER; observed prefixes retained');fig.tight_layout();fig.savefig(out/'parameters-branches-margins.png',dpi=160);plt.close(fig)
 fig,axes=plt.subplots(4,2,figsize=(11,11),sharex=True)
 for k,seed in enumerate([142710301,142710302,142710303,142710304]):
  for r in rows:
   if r['seed']!=seed or not any(m in r['methods'] for m in ['branch','continuous']):continue
   n=int(r['id'].split('-')[1][1:]);target=B/'runs'/r['id'];analysis=R/r['analysis_path'];obs=load(target/'run',analysis);i=json.load(open(B/f'evaluation-e{n:02d}-v1/past-packet/input.json'))['initial'];doc=json.load(open(B/f'evaluation-e{n:02d}-v1/past-packet/input.json'));a=doc['plan']['windows_profile_s'][0][0];epoch=round(int(obs['run_wall_ns'][0])-obs['t'][0]*1e9);body,_=read(target/'run/gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');body=body[(body['phase']==1)&(body['valid']==63)&(body['wall_ns']>=epoch)&(body['wall_ns']<=int(obs['run_wall_ns'][-1]))];t=(body['wall_ns'].astype(np.int64)-epoch)/1e9-a;L=-body['com_p'][:,2]-i['physical_H0_NED_z'];D=np.maximum.accumulate(np.maximum(L,0));color=colors[r['side']];mask=(t>=-.05)&(t<=2.2);axes[k,0].plot(t[mask],-body['com_v'][mask,2],c=color,label=r['side']);axes[k,1].plot(t[mask],L[mask],c=color,label='L '+r['side']);axes[k,1].plot(t[mask],D[mask],c=color,ls='--',alpha=.5)
  for j in range(2):axes[k,j].axvspan(0,.34,color='gray',alpha=.12);axes[k,j].axvspan(.99,1.35,color='gray',alpha=.12);axes[k,j].grid(alpha=.25);axes[k,j].set_title('Seed '+str(seed));axes[k,j].legend(fontsize=7)
  axes[k,0].set_ylabel('COM downward W (m/s)');axes[k,1].set_ylabel('COM loss L / history D (m)')
 for a in axes[-1]:a.set_xlabel('Absolute profile time relative to planned A (s)')
 fig.suptitle('Direct physical velocities/heights; initial differences retained; shaded planned gaps');fig.tight_layout();fig.savefig(out/'four-block-residuals.png',dpi=150);plt.close(fig)
 print('PLOTS_COMPLETE')
if __name__=='__main__':main()
