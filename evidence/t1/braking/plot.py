from pathlib import Path
import numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
d=np.genfromtxt(P/'PRE-dynamics.csv',delimiter=',',names=True);n=np.genfromtxt(P/'N-dynamics.csv',delimiter=',',names=True);t=d['phase_s'];f,ax=plt.subplots(5,1,figsize=(7.4,9),sharex=True)
ax[0].plot(t,d['vel_targetframe_0'],label='Actual velocity',c='#24689B');ax[0].plot(t,d['reference_vel_targetframe_0'],label='Reference velocity',c='#D07D28');ax[0].set_ylabel('Target-frame axis 1\nvelocity (m/s)')
ax[1].plot(t,d['error_velocity_0'],label='Unclipped error',c='#24689B');ax[1].plot(t,d['input_velocity_0'],label='Network input',c='#BD4939',ls='--');ax[1].set_ylabel('Velocity error\n(m/s)')
ax[2].plot(t,d['control_spread'],label='Motor-command spread',c='#34846B');ax[2].set_ylabel('Command range\n(max minus min)')
ax[3].plot(t,d['tilt_deg'],label='Pre-entered RAPTOR',c='#34846B');ax[3].plot(n['phase_s'],n['tilt_deg'],label='Moving handover',c='#BD4939',ls='--');ax[3].axhline(35,c='#777777',ls=':');ax[3].set_ylabel('Tilt (deg)')
ax[4].plot(t,d['az_down_est80ms'],label='Vertical acceleration, down',c='#24689B');ax[4].set_ylabel('Estimated acceleration\n(m/s²; 80 ms secant)');ax[4].set_xlabel('Time from profile native lower bound (s)')
for a in ax:a.set_xlim(4.9,6.7);a.axvspan(5.380,5.708,alpha=.09,color='#BD4939');a.axvline(5.75,c='#777777',ls=':',lw=.8);a.grid(alpha=.18);a.legend(loc='upper left',frameon=False,fontsize=8)
f.tight_layout()
for x in ['png','pdf']:f.savefig(P/f'braking-input-response.{x}',dpi=200)
