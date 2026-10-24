"""Final scientific figure from disclosed D33 rows; no measurement changes."""
import csv,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
out=Path(__file__).resolve().parent/'reviewed-figures';out.mkdir(exist_ok=False);source=Path(__file__).resolve().parent/'final-disclosure/D33-main-task-costs.csv';rows=list(csv.DictReader(source.open()));assert len(rows)==33
arms=['P9-Z','P9-C','P9-R','P9-CR'];fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
for ax,key,label,lim in [(axes[0,0],'max_tilt_deg','Peak tilt (deg)',45),(axes[0,1],'max_altitude_loss_m','Altitude loss (m)',1),(axes[1,0],'max_lag_m','Maximum lag (m)',4.5)]:
 for k,c in enumerate(sorted({r['cluster'] for r in rows})):
  rr=[r for r in rows if r['cluster']==c]
  if len(rr)==4:
   rr=[next(r for r in rr if r['arm']==a) for a in arms];x=np.arange(4)+(k-4)*.014;y=[float(r[key]) for r in rr];ax.plot(x,y,c='0.8',lw=.7)
   for xi,yi,r in zip(x,y,rr):ax.scatter(xi,yi,c=f'C{k}',marker='o' if r['complete_window']=='True' else '^',s=23)
  else:
   for r in rr:
    full=r['complete_window']=='True';ax.scatter(arms.index(r['arm']),float(r[key]),c='black',marker='D' if full else '^',s=34,label='Partial D07/D08: complete' if full else 'Partial D07/D08: censored')
 ax.set(xticks=range(4),xticklabels=arms,ylabel=label);ax.axhline(lim,c='black',lw=.7);h,l=ax.get_legend_handles_labels();unique=dict(zip(l,h));ax.legend(unique.values(),unique.keys(),fontsize=7)
ax=axes[1,1];bottom=np.zeros(4)
for state,label,col in [('SUCCESS','Cost success','#009E73'),('FAILURE','Cost failure','#D55E00'),('CENSORED','Censored','#E69F00'),('UNOBSERVED_FINAL_RESUME','Final resume unobserved','#999999')]:
 y=np.array([sum(r['arm']==a and r['cost_outcome']==state for r in rows) for a in arms]);ax.bar(range(4),y,bottom=bottom,label=label,color=col);bottom+=y
ax.set(xticks=range(4),xticklabels=arms,ylabel='Main runs (Z/R/CR=8; C=9)');ax.legend(fontsize=8)
fig.suptitle('D33 main: seven complete four-arm clusters; partial D07/D08 in black\nHistorical162/164/169 excluded from this panel and disclosed separately; triangles = censored',fontsize=10)
fig.savefig(out/'D33-final.png',dpi=180);fig.savefig(out/'D33-final.pdf');plt.close(fig)
write(out/'input-manifest.json',{str(p.relative_to(ROOT)):sha(p) for p in [source,Path(__file__).resolve()]});write(out/'output-manifest.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='output-manifest.json'})
