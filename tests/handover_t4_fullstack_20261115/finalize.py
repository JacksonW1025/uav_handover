import json,sys,hashlib,csv
from pathlib import Path
import numpy as np
from pyulog import ULog
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__import__('os').environ['HANDOVER_RESEARCH_ROOT']);A=Path(__file__).parent;sys.path.insert(0,str(R/'tools'));from output_chain import read_trace
d=json.loads((A/'evidence.json').read_text());fig,axs=plt.subplots(2,2,figsize=(10,6),layout='constrained')
for col,r in enumerate(d):
 run=R/'data/handover-t4-fullstack-20261115'/r['case']/'flight';u=ULog(str(run/'flight.ulg'),message_name_filter_list=['research_output']);b=u.get_dataset('research_output').data;t=r['first_N_publication'];ix=np.flatnonzero((b['timestamp']>=t-12000)&(b['timestamp']<=t+50000));r['bridge_rows']=[{k:float(v[i]) for k,v in b.items()} for i in ix]
 for m in r['motors']:
  _,tr,tail=read_trace(run/'gz-motor'/f"motor-{m['motor']}.bin");m['first_published_N_sample_ever_applied']=bool(np.any(tr['applied_sample_us']==r['first_N_sample']))
  assert all(x['bridge_value_error']==0 for x in m['rows']);assert m['tail_bytes']==0
  x=np.array([x['sim_us']-t for x in m['rows']])/1000;y=[x['owners'][0] if len(x['owners'])==1 else 0 for x in m['rows']];axs[0,col].step(x,y,where='post',label=f"motor {m['motor']}",alpha=.7)
 m=r['motors'][0];x=np.array([x['sim_us']-t for x in m['rows']])/1000;axs[1,col].step(x,[x['input'] for x in m['rows']],where='post',label='applied motor0');axs[1,col].step((b['timestamp'][ix].astype(float)-t)/1000,b['motor_speed[0]'][ix],where='post',label='bridge motor0');axs[0,col].set_title(r['case']);axs[0,col].set_yticks([1,2],['neural','classic'])
 for ax in axs[:,col]:ax.axvline(4,color='red',ls=':',label='normal first step +4ms');ax.set_xlim(-12,36);ax.grid(alpha=.2);ax.set_xlabel('ms from first N publication')
axs[0,0].set_ylabel('Physically applied source');axs[1,0].set_ylabel('Motor input (rad/s)');axs[1,1].legend(fontsize=7);fig.savefig(A/'handoff-lineage.png',dpi=150)
(A/'evidence.json').write_text(json.dumps(d,indent=2)+'\n')
for r in d:
 run=R/'data/handover-t4-fullstack-20261115'/r['case']/'flight';rows=list(csv.DictReader((run/'relay.csv').open()));lo=r['first_N_publication']-60000;hi=r['first_N_publication']+60000
 with (A/(r['case']+'-relay-window.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(x for x in rows if lo<=int(x['sim_us'])<=hi)
print([(r['case'],[m['first_published_N_sample_ever_applied'] for m in r['motors']]) for r in d])
