import json,csv
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pyulog import ULog
O=Path(__file__).resolve().parent;s=json.loads((O/'summary.json').read_text());fig,ax=plt.subplots(3,1,figsize=(7.2,7.1),sharex=True)
for arm,color,label in [('N4','#0072B2','Prepared GRU + actual previous action'),('N2','#D55E00','Zero GRU + actual previous action')]:
 r=s['arms'][arm];u=ULog(str(O/arm/'flight/flight.ulg'));d={z.name:z.data for z in u.data_list if z.multi_id==0};t0=r['entry_us'];a=d['vehicle_attitude'];l=d['vehicle_local_position'];p=d['research_actuator'];tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]']**2+a['q[2]']**2),-1,1)))
 for z,v,i in [(p,np.mean([p[f'control[{j}]'] for j in range(4)],axis=0),0),(a,tilt,1),(l,l['z']-r['state']['position'][2],2)]:
  t=(z['timestamp'].astype(float)-t0)/1e6;mask=(t>=-.3)&(t<=2);ax[i].plot(t[mask],v[mask],color=color,lw=1.4,label=label)
  with (O/(arm+'-'+str(i)+'.csv')).open('w') as f:
   w=csv.writer(f);w.writerow(['seconds_from_entry','value']);w.writerows(zip(t[mask],v[mask]))
for a,y in zip(ax,['Mean published motor command','Tilt (deg)','Descent from entry (m)']):a.set_ylabel(y);a.axvline(0,color='black',lw=.8,ls='--');a.grid(alpha=.22)
ax[0].legend(fontsize=8);ax[-1].set_xlabel('Time from actual memory-entry write (s)');fig.suptitle('Moving handover: isolating GRU preparation\nSame 0.6 m/s reference and previous-action initialization',fontsize=11);fig.tight_layout();fig.savefig(O/'T2-live-pair.pdf');fig.savefig(O/'T2-live-pair.png',dpi=180)
