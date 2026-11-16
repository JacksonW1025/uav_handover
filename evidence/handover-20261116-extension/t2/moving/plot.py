import json,hashlib,platform
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent;d=json.loads((P/'results.json').read_text());names=['reset','action_only','gru_only','both'];colors=['#777777','#2876a6','#a5762c','#27846d'];labels=['Reset both','Action only','GRU only','Both recorded']
summary={'native_checks':sum(c['validation']['checked'] for c in d['cases']),'max_error':max(c['validation']['max_abs_error'] for c in d['cases']),'frames':sum(len(c['frames']) for c in d['cases']),'first_entry':[],'all_nonentry_both_smallest':True,'later_frames_synthetic_intervention':True,'frame_table':[]}
for c in d['cases']:
 for i,f in enumerate(c['frames']):
  v=f['variants'];both=np.array(v['both']['output_motor']);g={n:{key:float(np.linalg.norm(np.array(v[n][key])-np.array(v['both'][key]))) for key in ['encoded','reset_gate','update_gate','gru_next']} for n in names}
  row={'case':c['name'],'offset_s':f['offset_s'],'metrics':{n:{k:v[n][k] for k in ['max_motor_delta','motor_delta_l2','motor_collective_delta','output_delta_from_observed_l2','clip_components']} for n in names},'gate_distances_to_observed':g}
  summary['frame_table'].append(row)
  if i==0:summary['first_entry'].append(row)
  else:summary['all_nonentry_both_smallest'] &= v['both']['max_motor_delta']<=min(v[n]['max_motor_delta'] for n in names)
(P/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
f,ax=plt.subplots(2,3,figsize=(11.4,6.6));short=['Moving tight turn','Early entry, before tight turn','Cruise 1 m/s; zero-speed capture','Decelerating; zero-speed capture','Cruise re-entry; zero-speed capture','Hover re-entry']
for a,c,title in zip(ax.flat,d['cases'],short):
 t=[r['offset_s'] for r in c['frames']]
 for n,col,label in zip(names,colors,labels):a.plot(t,[r['variants'][n]['max_motor_delta'] for r in c['frames']],marker='o',ms=3,lw=1.2,label=label,c=col)
 a.set(title=title,xlabel='Recorded time since entry (s)',ylabel='Counterfactual motor change',ylim=(0,.75));a.grid(alpha=.15)
ax[0,0].legend(fontsize=8,frameon=False);f.suptitle('Same recorded physical/reference inputs, different history at each sampled frame',fontsize=13);f.tight_layout();f.savefig(P/'T2-motion-replay.pdf');f.savefig(P/'T2-motion-replay.png',dpi=220)
(P/'manifest.json').write_text(json.dumps({'host':platform.node(),'sha256':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in P.iterdir() if x.is_file() and x.name!='manifest.json'}},indent=2)+'\n');print(json.dumps({k:summary[k] for k in ['native_checks','max_error','frames','all_nonentry_both_smallest']}))
