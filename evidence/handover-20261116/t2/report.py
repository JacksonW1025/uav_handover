import json,hashlib,platform,sys,datetime
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path('/tmp/handover3h-t2-20261116');d=json.loads((p/'fixed-frame.json').read_text());s=json.loads((p/'sensitivity.json').read_text());names=['reset','action_only','gru_only','both'];labels=['Reset both','Actual action only','Prepared GRU only','Both prepared'];summary={}
for n in names:
 vals=[r['variants'][n]['max_motor_change_from_logged_action_input'] for r in d['records']];summary[n]={'mean':float(np.mean(vals)),'min':min(vals),'max':max(vals),'values':vals}
summary['baseline']={'native_checks':sum(r['native_validation']['checked'] for r in d['records']),'native_max_error':max(r['native_validation']['max_abs_error'] for r in d['records']),'example_error':d['example_max_abs_error'],'all_input_frames':5,'counterfactuals':20,'interpolation_evaluations':125}
summary['action_reset_gru_change']=[r['variants']['gru_only']['gru_delta_from_observed'] for r in d['records']]
summary['computing_host']=platform.node();summary['execution_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();summary['clipped_action_components_total']=sum(v['action_clip_components'] for r in d['records'] for v in r['variants'].values());(p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'axes.spines.right':False,'axes.spines.top':False})
f,ax=plt.subplots(1,2,figsize=(10.2,3.9));cols=['#888888','#2876a6','#a5762c','#28866d']
for i,(n,label,col) in enumerate(zip(names,labels,cols)):
 vals=summary[n]['values'];ax[0].scatter(i+np.linspace(-.08,.08,5),vals,c=col,s=30);ax[0].plot([i-.2,i+.2],[summary[n]['mean']]*2,c=col);ax[0].text(i,max(vals)+.012,f"{summary[n]['mean']:.3f}",ha='center',color=col)
ax[0].set(xticks=range(4),xticklabels=['Reset\nboth','Action\nonly','GRU\nonly','Both'],ylim=(0,.26),ylabel='First-inference motor change (normalized)',title='Same state and reference; change only history');ax[0].grid(axis='y',alpha=.15)
m=np.array([[np.mean([r['max_motor_delta'] for r in s['rows'] if r['gru_fraction']==h and r['action_fraction']==a]) for a in [0,.25,.5,.75,1]] for h in [0,.25,.5,.75,1]])
im=ax[1].imshow(m,origin='lower',cmap='YlOrRd',vmin=0,vmax=.25);ax[1].set(xticks=range(5),yticks=range(5),xticklabels=['0','.25','.5','.75','1'],yticklabels=['0','.25','.5','.75','1'],xlabel='Fraction of recorded previous action',ylabel='Fraction of prepared GRU',title='Controlled interpolation (mean of five frames)')
for y in range(5):
 for x in range(5):ax[1].text(x,y,f'{m[y,x]:.3f}',ha='center',va='center',fontsize=8,color='white' if m[y,x]>.16 else 'black')
f.colorbar(im,ax=ax[1],fraction=.045,pad=.04,label='Motor change');f.tight_layout();f.savefig(p/'T2-fixed-frame.pdf');f.savefig(p/'T2-fixed-frame.png',dpi=240)
files=['t2_fixed_frame.py','t2_sensitivity.py','fixed-frame.json','sensitivity.json','summary.json','T2-fixed-frame.pdf','T2-fixed-frame.png','report.py'];manifest={'host':platform.node(),'files':{x:hashlib.sha256((p/x).read_bytes()).hexdigest() for x in files},'replay_sha256':hashlib.sha256(Path('/home/car/uav_handover/tools/p3_memory.py').read_bytes()).hexdigest()};(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(summary,indent=2))
