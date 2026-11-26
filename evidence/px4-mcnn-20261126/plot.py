"""Generate the evidence overview from the archived native CSV windows."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from verify import read,tilt
import numpy as np

root=Path(__file__).resolve().parent
case=json.loads((root/"metrics.json").read_text())
pairs=[("t1_c","t1_n"),("t2_c","t2_n"),("t3_fresh","t3_stale"),("t4_release","t4_hold")]
titles=["T1 · straight braking","T2 · hover command continuity","T3 · retained reference at reentry","T4 · motor delivery deadline"]
labels=[("Classic","MCNN"),("Classic","MCNN"),("Fresh target","Retained target"),("Immediate","Hold")]
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"axes.spines.top":False,"axes.spines.right":False})
fig,axs=plt.subplots(2,4,figsize=(12.4,4.8),sharex=True,layout="constrained")
for j,(k0,k1) in enumerate(pairs):
 for k,label,col in zip((k0,k1),labels[j],("#34699a","#be5638")):
  t=case[k]["request_us"]
  att=read(root/k,"vehicle_attitude")
  pos=read(root/k,"vehicle_local_position")
  at=(np.array([int(r["timestamp"]) for r in att])-t)*1e-6
  pt=(np.array([int(r["timestamp"]) for r in pos])-t)*1e-6
  hi=[float(r["z"]) for r in pos]; x=[float(r["x"]) for r in pos]
  axs[0,j].plot(at,[tilt(r) for r in att],label=label,color=col,lw=1.4)
  z0,x0=case[k]["entry_xyz_m"][2],case[k]["entry_xyz_m"][0]
  second=x if j in (0,2,3) else hi
  origin=x0 if j in (0,2,3) else z0
  if j==1:
   axs[1,j].plot(pt,[100*(z0-v) for v in hi],color=col,lw=1.4)
  else:
   axs[1,j].plot(pt,[v-origin for v in second],color=col,lw=1.4)
  if j==3 and "first_four_application_us" in case[k]:
   for ax in axs[:,j]:ax.axvline((case[k]["first_four_application_us"]-t)*1e-6,color=col,ls=":",lw=1)
 axs[0,j].set_title(titles[j],loc="left",weight="bold",fontsize=9)
 axs[0,j].legend(loc="upper left",frameon=False,fontsize=8)
 axs[0,j].set_ylabel("Tilt (°)")
 axs[1,j].set_ylabel("Height change (cm)" if j==1 else "North displacement (m)")
 axs[1,j].set_xlabel("Time from request (s)")
 for ax in axs[:,j]:
  ax.axvline(0,color="#8b9297",lw=.6,zorder=0)
  ax.grid(axis="y",alpha=.22)
  ax.set_xlim(-.18,1.85)
fig.savefig(root/"paired-windows.png",dpi=200)
fig.savefig(root/"paired-windows.pdf")
