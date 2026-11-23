import json
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
A=Path(__file__).parent;rs=json.loads((A/'f1-comparison.json').read_text())['rows'];fig,axes=plt.subplots(4,2,figsize=(13,12),layout='constrained');cols={'E1':'#437b60','E2':'#c55c43','E3':'#386fa4'}
for r in rs:
 j=r['spec']['repeat']-1;tr=r['trace'];ts=np.array(tr['t_state']);ta=np.array(tr['t_attitude']);s=ts<=2;a=ta<=2;e=np.array(tr['position_error']);label=r['arm'];color=cols[label]
 axes[0,j].plot(ta[a],np.array(tr['roll_deg'])[a],label=label,color=color);axes[1,j].plot(ta[a],np.array(tr['pitch_deg'])[a],color=color);axes[2,j].plot(ts[s],e[s,0],color=color);axes[3,j].plot(ts[s],e[s,1],color=color)
for j in range(2):
 axes[0,j].set_title(f'Repeat {j+1}');axes[0,j].legend()
 for i,y in enumerate(['Roll (deg)','Pitch (deg)','Signed x tracking error (m)','Signed y tracking error (m)']):axes[i,j].set(ylabel=y,xlabel='Seconds from request native lower bound');axes[i,j].axhline(0,color='grey',lw=.6);axes[i,j].grid(alpha=.2)
fig.savefig(A/'f1-signed-response.png',dpi=150)
