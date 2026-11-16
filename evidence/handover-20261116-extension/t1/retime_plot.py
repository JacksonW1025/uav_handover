from pathlib import Path
import numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
f,ax=plt.subplots(3,1,figsize=(7.2,7),sharex=True)
for key,c,label in [('q115','#BD4939','Original time scale 1.15'),('q125','#24689B','Slower time scale 1.25')]:
 d=np.genfromtxt(P/(key+'-retime.csv'),delimiter=',',names=True)
 for a,k in zip(ax,['velocity_error_axis1','tilt_deg','descent_from_stop_m']):a.plot(d['normalized_phase_s'],d[k],c=c,label=label)
for a in ax:a.set_xlim(4,7);a.axvline(5,c='#888888',ls=':',lw=.9);a.grid(alpha=.18)
ax[0].axhline(-1,c='#999999',ls='--');ax[1].axhline(35,c='#999999',ls='--');ax[0].legend(frameon=False)
ax[0].set_ylabel('Unclipped velocity error\n(m/s, target-frame axis 1)');ax[1].set_ylabel('Tilt (deg)');ax[2].set_ylabel('Descent from stop (m)');ax[2].set_xlabel('Normalized path phase: time / scale (s)');f.tight_layout()
for x in ['png','pdf']:f.savefig(P/f'time-scale-comparison.{x}',dpi=200)
