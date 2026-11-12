import json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
A=Path(__file__).parent;R=A.parents[1];sys.path.insert(0,str(R/'tools'));from output_chain import read_trace
D=json.loads((A/'f1-comparison.json').read_text());rows=[r for r in D['rows'] if r['arm']!='E1'];evidence={};fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained');fig2,ax2=plt.subplots(2,2,figsize=(13,8),layout='constrained')
for ax,ap,r in zip(axes.flat,ax2.flat,rows):
 z=json.loads((A/(r['case']+'-a1')/'score.json').read_text());run=Path(z['run']);anchor=r['anchor_request_lower_us'];end=min(r['native_end_us'],anchor+650000);u=ULog(str(run/'flight.ulg'),message_name_filter_list=['research_actuator']);d=next(x.data for x in u.data_list if x.name=='research_actuator');t=d['actuator_timestamp'].astype(np.int64);ix=(t>=anchor-40000)&(t<=end);tt=(t[ix]-anchor)/1e6;v=np.column_stack([d[f'control[{i}]'][ix] for i in range(4)]);physics=[]
 for i in range(4):ax.plot(tt,v[:,i],label=f'Motor {i}')
 for file in sorted((run/'gz-motor').glob('motor-*.bin')):
  i,m,tail=read_trace(file);sel=(m['sim_us']>=anchor-40000)&(m['sim_us']<=end);tm=(m['sim_us'][sel].astype(np.int64)-anchor)/1e6;val=m['ref_motor_input'][sel];ap.plot(tm,val,label=f'Motor {i}');physics.append({'motor':i,'t_from_request_s':tm.tolist(),'applied_reference_input':val.tolist()})
 evidence[r['case']]={'command_t_s':tt.tolist(),'command_controls':v.tolist(),'owner':d['owner'][ix].astype(int).tolist(),'physics_reference':physics,'note':'research_actuator commands versus motor plugin ref_motor_input; physics reference is commanded rotor input, not measured rotor speed'}
 for a in [ax,ap]:
  a.axvline((r['chain']['first_four_application_us']-anchor)/1e6,color='black',ls=':',label='First all-four application');a.axvline((r['chain']['first_read_us']-anchor)/1e6,color='purple',ls='--',label='First valid reference read');a.set(title=r['case'],xlabel='Seconds from request native lower bound');a.grid(alpha=.2);a.legend(fontsize=7)
 ax.set(ylabel='Published actuator control [0,1]');ap.set(ylabel='Motor physics reference input (rad/s)')
fig.savefig(A/'f1-four-motor-commands.png',dpi=150);fig2.savefig(A/'f1-four-motor-physics-input.png',dpi=150);(A/'f1-motor-curves.json').write_text(json.dumps(evidence,indent=2)+'\n')
