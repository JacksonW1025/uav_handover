from pathlib import Path
import numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
f,ax=plt.subplots(4,1,figsize=(7.3,8),sharex=True)
for arm,c,label in [('FF','#24689B','Classical + acceleration feedforward'),('NOFF','#BD4939','Classical, acceleration omitted')]:
 d=np.genfromtxt(P/(arm+'-feedforward.csv'),delimiter=',',names=True);tr=np.genfromtxt(P/(arm+'-tracking.csv'),delimiter=',',names=True);t=d['normalized_phase']
 ax[0].plot(t,np.hypot(d['output_ax'],d['output_ay']),c=c,label=label)
 ax[1].plot(t,d['tilt_deg'],c=c);ax[1].plot(t,d['attitude_setpoint_tilt_deg'],c=c,ls=':',alpha=.6)
 ax[2].plot(tr['normalized_phase'],tr['horizontal_position_error'],c=c)
 ax[3].plot(t,d['descent_from_stop_m'],c=c)
for a in ax:a.set_xlim(4,7);a.axvline(5,c='#888888',ls=':',lw=.8);a.grid(alpha=.18)
ax[0].legend(frameon=False,fontsize=9);ax[0].set_ylabel('Requested horizontal\nacceleration (m/s²)');ax[1].set_ylabel('Tilt (deg)\nsolid actual, dotted target');ax[2].set_ylabel('Horizontal position\nerror (m)');ax[3].set_ylabel('Descent from stop (m)');ax[3].set_xlabel('Normalized path phase: time / scale (s)');f.tight_layout()
for e in ['pdf','png']:f.savefig(P/('classic-feedforward-comparison.'+e),dpi=200)
