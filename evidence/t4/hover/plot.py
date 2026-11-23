from pathlib import Path
import json, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent
j=json.loads((P/'raw-audit.json').read_text())['delivery']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(1,2,figsize=(10,3.7))
for i,(r,c,label) in enumerate(zip(j,['#bb5141','#2979a1'],['Deadline release','Fresh-active release'])):
 rows=r['motors'][0]['window'];pub=r['first_publication_us']
 x=np.array([(v['sim_us']-pub)/1000 for v in rows]);age=np.array([(v['sim_us']-v['sample_us'])/1000 for v in rows])
 sel=x<=36
 axs[0].step(x[sel],age[sel],where='post',color=c,label=label,lw=2)
 for m in r['motors']:
  y=4-i*5-m['motor']*.18
  for v in m['window']:
   dt=(v['sim_us']-pub)/1000
   if dt<=32:
    classic=v['owner']==[2]
    axs[1].scatter(dt,y,marker='s' if classic else 'o',color='#aeb7bf' if classic else c,s=26)
 first=r['motors'][0]['first_N_delay_us']/1000
 axs[1].annotate(f'first N: +{first:g} ms',(first,4-i*5),xytext=(first+1,4-i*5+.7),color=c,fontsize=9)
axs[0].set(xlabel='Time from first N publication (ms)',ylabel='Applied sample age (ms)',xlim=(0,36),ylim=(0,65),title='Old-command hold is removed')
axs[0].legend(frameon=False,fontsize=9);axs[0].grid(axis='y',alpha=.18)
axs[1].set(xlabel='Time from first N publication (ms)',yticks=[3.73,-1.27],yticklabels=['Deadline\n4 motors','Fresh-active\n4 motors'],xlim=(-1,36),ylim=(-2.3,5.3),title='Measured physical-step command source')
axs[1].grid(axis='x',alpha=.18)
fig.text(.07,.015,'Two new hover flights; same 60 ms hold budget, original PX4 protections. Squares: classic; circles: neural.',fontsize=9)
fig.subplots_adjust(left=.07,right=.99,bottom=.19,wspace=.35)
for ext in ['pdf','png']:fig.savefig(P/('delivery-comparison.'+ext),dpi=220)
# Matching of request-time state (not pretending full initial state identity).
a,b=[next(e for e in r['events'] if e['event']=='explore_pre_switch') for r in j]
qa,qb=np.array(a['quaternion']),np.array(b['quaternion'])
match={'position_delta_m':float(np.linalg.norm(np.array(a['position'])-b['position'])),'velocity_delta_m_s':float(np.linalg.norm(np.array(a['velocity'])-b['velocity'])),'attitude_geodesic_delta_deg':float(2*np.degrees(np.arccos(np.clip(abs(np.dot(qa,qb)/np.linalg.norm(qa)/np.linalg.norm(qb)),0,1))))}
(P/'matching.json').write_text(json.dumps(match,indent=2)+'\n');print(match)
