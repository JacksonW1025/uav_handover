from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(3,1,figsize=(8.1,7.4),sharex=True)
colors={'C2':'#24689B','N':'#BD4939','PRE':'#34846B'}
for arm,label in [('C2','Continue classical'),('N','Switch during motion'),('PRE','Enter RAPTOR before motion')]:
 d=np.genfromtxt(P/(arm+'-trajectory.csv'),delimiter=',',names=True); c=colors[arm]
 for ax,key in zip(axs,['tilt_deg','descent_from_profile_m','vz']):
  ax.plot(d['profile_s'],d[key],label=label,c=c,lw=1.5)
 for ax in axs:ax.set_xlim(0,9);ax.grid(alpha=.18);ax.axvline(2.875,color='#777777',linestyle=':',lw=.9)
axs[0].axhline(35,c='#777777',ls='--',lw=.9);axs[0].axhline(45,c='#999999',ls='--',lw=.9)
axs[0].set_ylabel('Tilt (deg)');axs[1].set_ylabel('Descent from profile start (m)');axs[2].set_ylabel('Vertical velocity, NED (m/s)')
axs[2].set_xlabel('Time from profile native lower bound (s)');axs[0].legend(frameon=False,ncol=1)
fig.suptitle('T1: same build and reference, different takeover timing')
fig.tight_layout()
for ext in ['png','pdf']:fig.savefig(P/('three-arm-profile.'+ext),dpi=220)
