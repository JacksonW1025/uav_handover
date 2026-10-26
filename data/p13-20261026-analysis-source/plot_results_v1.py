"""Scientific static figures, all preassigned blocks and model errors retained."""
import sys,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[2]

def save(fig,out,name):
 fig.savefig(out/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(out/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
def plots(agg,syn,out):
 out.mkdir(parents=True,exist_ok=False);cases=json.load(open(agg/'cases.json'))['rows'];rows=json.load(open(agg/'contrasts.json'))['rows'];done={x['id']:x for x in cases if x['status']=='FINISH'};arms=['NORMAL','A','B-short','B-medium','B-long','AB-short','AB-medium','AB-long','REPAIR-short','REPAIR-medium','REPAIR-long'];color={'NORMAL':'#808080','A':'#E69F00','B-short':'#0072B2','AB-short':'#D55E00','REPAIR-short':'#009E73'}
 fig,ax=plt.subplots(figsize=(12,4));z=np.full((6,11),np.nan);labels=[]
 for i,(f,b) in enumerate((f,b) for f in ['F2','F4'] for b in [1,2,3]):
  labels.append(f'{f} seed block {b}')
  for j,arm in enumerate(arms):
   rec=next((r for r in done.values() if r['family']==f and r['block']==b and r['arm']==arm),None)
   if rec:
    z[i,j]=0 if rec['task']=='SUCCESS' else 1 if rec['task']=='FAILURE' else 2
    if rec['censored']:ax.text(j,i,'C',ha='center',va='center',fontweight='bold')
 cmap=matplotlib.colors.ListedColormap(['#B8DFCD','#EF9A9A','#FFE082']);ax.imshow(z,vmin=0,vmax=2,cmap=cmap,aspect='auto');ax.set_xticks(range(11),arms,rotation=40,ha='right');ax.set_yticks(range(6),labels);ax.set_title('Assigned flight task OR: green success, red failure, yellow unknown; C = safety-censored');save(fig,out,'task-outcomes')
 # Each independent block is a line. Strategies, gaps and models do not add n.
 for fam in ['F2','F4']:
  fig,axs=plt.subplots(2,3,figsize=(12,7),sharex=True);keys=['COM_W_m_s','origin_L_m','origin_D_m','body_tilt_deg'];titles=['B-before direct COM downward speed (m/s)','B-before model-origin current loss L (m)','B-before historic max loss D (m)','B-before body tilt (deg)']
  for block in [1,2,3]:
   rr=sorted([r for r in rows if r['family']==fam and r['block']==block],key=lambda r:r['planned_gap_s']);x=[r['planned_gap_s'] for r in rr]
   for arm,col,ls in [('B','#0072B2','--'),('AB','#D55E00','-'),('REPAIR','#009E73',':')]:
    for k in range(4):
     yy=[r.get(arm+'_B_before_physical',{}).get(keys[k],np.nan) if r.get(arm+'_B_before_physical') else np.nan for r in rr];axs.flat[k].plot(x,yy,color=col,ls=ls,marker='o',alpha=.4+block*.18,label=arm if block==1 else None)
   axs.flat[4].plot(x,[r.get('AB_minus_B_before',{}).get('h_l2',np.nan) for r in rr],marker='o',label=f'block {block}')
   axs.flat[5].plot(x,[r.get('AB_minus_B_before',{}).get('filter_l2_rad_s',np.nan) for r in rr],marker='o',label=f'block {block}')
  for k,t in enumerate(titles+['AB vs B hidden difference (L2)','AB vs B filter difference (L2 rad/s)']):axs.flat[k].set_title(t,fontsize=10);axs.flat[k].grid(alpha=.2);axs.flat[k].set_xticks([.55,1.2,2.]);axs.flat[k].set_xlabel('Planned A-resume to B-stop interval (s)')
  axs.flat[0].legend();axs.flat[4].legend();fig.suptitle(f'{fam}: all three prespecified seed blocks; initial differences retained');fig.tight_layout();save(fig,out,'B-before-'+fam)
  # Every seed, the short-gap arms; never choose one favorable repeat.
  fig,axs=plt.subplots(3,3,figsize=(13,9),sharex=True)
  for block in [1,2,3]:
   for arm,col in color.items():
    rr=next((r for r in done.values() if r['family']==fam and r['block']==block and r['arm']==arm),None)
    if not rr:continue
    q=np.load(R/'data/p13-20261026-formal-analysis-v2'/rr['id']/'physics.npz');use=(q['t']>=12.8)&(q['t']<=20.)
    for j,key in enumerate(['LC','W','theta']):axs[block-1,j].plot(q['t'][use],q[key][use],color=col,lw=1.1,label=arm)
   for j in range(3):
    axs[block-1,j].axvspan(13.255,13.615,color='black',alpha=.07);axs[block-1,j].axvspan(14.165,14.525,color='black',alpha=.07);axs[block-1,j].grid(alpha=.2);axs[block-1,j].set_title(f'{fam} block {block}: '+['COM current loss L (m)','COM downward W (m/s)','Physical tilt (deg)'][j],fontsize=10)
  axs[0,0].legend(fontsize=8);axs[-1,1].set_xlabel('Original absolute task profile time (s), no response alignment');fig.tight_layout();save(fig,out,'short-gap-process-'+fam)
 pred=json.load(open(syn/'prediction-summary.json'))['models'];fig,axs=plt.subplots(1,3,figsize=(12,4));names=['M3','M4','M5']
 for j,part in enumerate(['tilt','height','task']):
  bottoms=np.zeros(3)
  for key,c in [('AGREEMENT','#009E73'),('DANGER_MISS','#D55E00'),('FALSE_ALARM','#E69F00'),('UNKNOWN','#888888')]:
   yy=[]
   for n in names:
    cs=pred[n]['whole_or_valid_witness_classification'][part]['counts'];yy.append(sum(v for k,v in cs.items() if k.startswith('UNKNOWN')) if key=='UNKNOWN' else cs.get(key,0))
   axs[j].bar(names,yy,bottom=bottoms,color=c,label=key);bottoms+=yy
  axs[j].set_title(part+' component, one flight denominator');axs[j].set_ylabel('Assigned finished flights');axs[j].set_ylim(0,max(1,len(done)));axs[j].grid(axis='y',alpha=.15)
 axs[-1].legend(fontsize=8);fig.tight_layout();save(fig,out,'prediction-components')
 # Honest mechanical unit distinction, paired common windows only.
 fig,axs=plt.subplots(1,3,figsize=(12,4));ks=['aerodynamic_command_TV_rad_s','LP_horizontal_tracking_integral_m_s','post_joint_squared_rad2_per_s'];titles=['Command total variation (rad/s)','LP tracking integral (m s)','Actual joint-square integral (rad²/s)']
 for fam,marker,col in [('F2','o','#0072B2'),('F4','s','#D55E00')]:
  for j,k in enumerate(ks):
   x=[];y=[];err=[]
   for r in rows:
    if r['family']!=fam:continue
    v=r['common_window_costs_v3']['REPAIR_minus_AB'][k];lo,hi=(v['lower'],v['upper']) if isinstance(v,dict) else (v,v);x.append(r['planned_gap_s']+(.015 if fam=='F4' else -.015));y.append((lo+hi)/2);err.append((hi-lo)/2)
   axs[j].errorbar(x,y,yerr=err,fmt=marker,color=col,label=fam,alpha=.65);axs[j].axhline(0,color='black',lw=.7);axs[j].set_title(titles[j]);axs[j].set_xlabel('Planned interval (s)');axs[j].grid(alpha=.2)
 axs[0].set_ylabel('REPAIR - AB, common valid window');axs[0].legend();fig.suptitle('Mechanical proxies, not electrical energy; full/censored task integrals never subtracted');fig.tight_layout();save(fig,out,'repair-common-costs')
 (out/'README.md').write_text('All figures use assigned cases and original time, no peak/capture alignment. Three seeds per condition, gaps/arms/models correlated. Physical COM and model-origin diagnostics remain distinct from LP task criterion. PDFs are standalone export figures.\n')
if __name__=='__main__':plots(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))
