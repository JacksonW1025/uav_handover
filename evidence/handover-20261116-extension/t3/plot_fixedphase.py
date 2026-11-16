from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path('/tmp/handover-t3-semantics-20261116/flight-analysis');j=json.loads((P/'summary.json').read_text());plt.rcParams.update({'font.size':10,'font.family':'DejaVu Sans','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
f,ax=plt.subplots(2,2,figsize=(10,6));f.subplots_adjust(left=.08,right=.98,bottom=.12,top=.9,wspace=.28,hspace=.48)
for r,color,label in zip(j['cases'],['#187969','#bf4a32'],['Zero capture','Speed-matched capture']):
 d=np.genfromtxt(P/(r['case']+'-reference.csv'),delimiter=',',names=True);a=np.genfromtxt(P/(r['case']+'-physical.csv'),delimiter=',',names=True)
 ax[0,0].step(d['time_from_first_neural_s'],d['target_vx'],where='post',color=color,label=label)
 ax[0,1].plot(d['time_from_first_neural_s'],d['vx'],color=color,label=label)
 ax[1,0].plot(a['time_from_first_neural_s'],a['tilt_deg'],color=color,label=label)
 ax[1,1].plot(d['time_from_first_neural_s'],d['position_error_m'],color=color,label=label)
for x in ax.flat:x.grid(alpha=.18);x.axvline(0,color='.5',lw=.7);x.set_xlabel('Time from first neural publication (s)')
ax[0,0].set(xlim=(-.025,.25),ylabel='Adopted target vx (m/s)',title='Same requested wait; different target')
ax[0,1].set(xlim=(-.025,2),ylabel='Actual vx (m/s)',title='Vehicle velocity')
ax[1,0].set(xlim=(-.025,2),ylabel='Tilt (deg)',title='Native attitude response')
ax[1,1].set(xlim=(-.025,2),ylabel='Position error (m)',title='Error to adopted target')
ax[0,0].legend(frameon=False,fontsize=9)
f.suptitle('T3: fallback target semantics, same requested reference wait',fontsize=14)
for ext in ['png','pdf']:f.savefig(P/('fixedphase-mechanism.'+ext),dpi=240)
