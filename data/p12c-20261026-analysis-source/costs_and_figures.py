#!/usr/bin/env python3
"""Descriptive full-task costs, recovery sign witnesses and all-valid-prefix figures."""
import sys,json,os
from pathlib import Path
import numpy as np
os.environ.setdefault('MPLCONFIGDIR','/tmp/p12c-mpl-cache')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c_platform.accept import task_features
from p12.execution import DTYPE
P=R/'data/p12c-20261026-preparation';O=R/'data/p12c-20261026-delivery/costs-and-process'
def main():
 O.mkdir(exist_ok=False);rows=json.load(open(P/'protocol.json'))['rows'];records=[];data={}
 for row in rows:
  parent=R/'data/p12c-20261026-development'/row['id']
  if not (parent/'result.json').exists():continue
  d,plan,m,end=task_features(parent);data[row['id']]=(row,d,plan,m,end);epoch=float(d['run_wall_ns'][0]-d['t'][0]*1e9);first=plan['common_first_gap_profile_s'];B=plan['full_source_windows_profile_s'][1 if row['family']=='F4' else 2][0];cost={}
  for label,lo,hi in [('full_task0_valid',0,end),('common_first_A_to_valid_end',first,end)]:
   sums={'joint_square_integral_rad2_s':0.,'command_total_variation_rad_s':0.,'absolute_thrust_impulse_N_s':0.};phys_durations=[]
   for motor in range(4):
    e=np.fromfile(parent/f'run/gz-motor/execution-p12-{motor}.bin',DTYPE);t=(e['end_ns'].astype(float)-epoch)/1e9;sel=(t>=lo)&(t<=hi);v=e[sel];sums['joint_square_integral_rad2_s']+=float(np.sum(v['scaled_joint']**2*v['dt']));sums['command_total_variation_rad_s']+=float(abs(np.diff(v['command'])).sum());sums['absolute_thrust_impulse_N_s']+=float(np.sum(abs(v['thrust'])*v['dt']));phys_durations.append(float(v['dt'].sum()))
   sel=(d['t']>=lo)&(d['t']<=hi);t=d['t'][sel];err=d['track'][sel];active=np.linalg.norm(d['position'][sel,:2]-d['target_p'][sel,:2],axis=1);dt=np.diff(t);cost[label]={'interval_profile_s':[lo,hi],'full_task_complete':not m['censored'],**sums,'physical_integrated_duration_each_motor_s':phys_durations,'task_horizontal_error_integral_m_s':float(np.sum((err[1:]+err[:-1])*dt/2)),'active_reference_error_integral_m_s':float(np.sum((active[1:]+active[:-1])*dt/2)),'scope':'sampled mechanical proxies, not electrical energy; motor rectangular integral uses actual physics dt and fixed host-window membership; boundary uncertainty <=one physical step, no selected recovery alignment'}
  table=json.load(open(R/'data/p12c-20261026-delivery/event-tables'/row['id']/'event-states.json'));brow=next(z for z in table['rows'] if z['label']=='B_before');resume=table['events'][0].get('resume_profile_s');sign=None
  if resume is not None:
   sel=np.flatnonzero((d['t']>=resume)&(d['t']<B)&(d['W']<=0))
   if len(sel):k=int(sel[0]);sign={'profile_s':float(d['t'][k]),'LP_sample_us':int(d['lp_sample'][k]),'LP_W_m_s':float(d['W'][k]),'scope':'first sampled non-downward LP W after A resume, not full sustained tracking/history recovery'}
  records.append({'id':row['id'],'class':row['class'],'seed':row['sim_seed'],'on':row['observe'],'costs':cost,'B_before':brow,'A_resume_to_B_s':None if resume is None else float(B-resume),'first_non_downward_LP_after_A_resume_before_B':sign,'frozen_final_recovery':m['joint_recovery_after_final_capture'],'warning':'final stationary capture recovery is separate from A/B moving recovery; recovered height does not erase D'})
 (O/'costs-and-states.json').write_text(json.dumps({'schema':'p12c-costs-and-process-1','records':records,'new_repair_flights':0,'repair_evidence_source':'old P12b only, unchanged; no new formal or repair improvement claim','no_causal_inference_from_raw_difference':True},indent=2)+'\n')
 F=R/'docs/figures/p12c';F.mkdir(parents=True,exist_ok=True);fig,axes=plt.subplots(3,1,figsize=(10,9),sharex=True)
 colors={'NORMAL':'#6b7280','SAFE_EVENT':'#2563eb','BOUNDARY':'#dc2626'}
 for ident,(r,d,plan,m,end) in data.items():
  if r['class']=='NORMAL':continue
  sel=(d['t']>=12.5)&(d['t']<=min(18,end));label=f"{r['class']} seed{r['block']} {'on' if r['observe'] else 'off'}";style='-' if r['observe'] else '--';t=d['t'][sel];axes[0].plot(t,d['L_world'][sel],style,color=colors[r['class']],alpha=.7,label=label);axes[1].plot(t,d['W'][sel],style,color=colors[r['class']],alpha=.7);axes[2].plot(t,d['tilt'][sel],style,color=colors[r['class']],alpha=.7)
 axes[0].axhline(1,color='k',ls=':',lw=1)
 for ax in axes:
  ax.axvspan(12.895,13.255,color='gray',alpha=.15);ax.axvspan(13.805,14.165,color='#dc2626',alpha=.08);ax.axvspan(15.135,15.495,color='#2563eb',alpha=.08);ax.grid(alpha=.2)
 axes[0].set_ylabel('World model-origin loss L (m)');axes[1].set_ylabel('LP down velocity W (m/s)');axes[2].set_ylabel('Controller-cache tilt (deg)');axes[2].set_xlabel('Absolute task profile time (s)');axes[0].legend(fontsize=8,ncol=2);fig.suptitle('Preparation only: different source families and intervals; no new repair or formal blocks');fig.tight_layout();fig.savefig(F/'residual-descent.png',dpi=160);plt.close(fig)
 fig,axes=plt.subplots(3,1,figsize=(10,9),sharex=True)
 review=json.load(open(P/'acceptance-partial-v2.json'))
 for pair in review['pairs']:
  if pair['status']!='COMPARED_ALL_VALID':continue
  _,a,_,_,ea=data[pair['off']];_,b,_,_,eb=data[pair['on']];sel=(a['t']>=0)&(a['t']<=min(ea,eb));t=a['t'][sel];label=f"{pair['class']} block{pair['block']}"
  for ax,k in zip(axes,['tilt','L_world','W']):ax.plot(t,a[k][sel]-np.interp(t,b['t'],b[k]),label=label,alpha=.8)
 for ax,limit,label in zip(axes,[5,.2,.2],['Tilt off-on (deg)','World loss off-on (m)','LP W off-on (m/s)']):
  ax.axhline(limit,color='k',ls='--',lw=.8);ax.axhline(-limit,color='k',ls='--',lw=.8);ax.set_ylabel(label);ax.grid(alpha=.2)
 axes[0].legend(fontsize=8,ncol=2);axes[-1].set_xlabel('All mutually valid task0-to-end profile time (s)');fig.suptitle('Prespecified dynamic scales: no peak/event alignment, no selected short prefix');fig.tight_layout();fig.savefig(F/'noninterference-full-prefix.png',dpi=160);plt.close(fig);print('COSTS_FIGURES',len(records),'no new flight')
if __name__=='__main__':main()
