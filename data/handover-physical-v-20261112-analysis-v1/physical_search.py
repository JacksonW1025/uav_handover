"""Few-case, prospective physical-V vs speed guidance; fixed history/process.
Four entry phases on one coupled 3D S-turn plus continuous yaw sweep.
Two selectors get the SAME local time-compression operator. Shared choice = one flight.
"""
import json,sys,copy,time
from pathlib import Path
import numpy as np
from execute import R,A,B,run,dump
sys.path.insert(0,str(R/'tools'));from handover_100.design import geometry
O=R/'data/handover-advanced-20261112-offline-v1';sys.path.insert(0,str(O));import directional_analysis as d
d.OLD=A;d.B=B
load=lambda p:json.loads(p.read_text())
knots=[[0,[0,0,0],[0,0,0]],[1.5,[1.05,.45,-.3],[1.4,.6,-.4]],[2.2,[2.05,1.05,-.6],[1.4,1.3,-.4]],[2.9,[2.6,2.15,-.65],[-.2,1.8,.35]],[3.6,[1.9,3.05,-.15],[-1.6,.6,.65]],[4.3,[.8,2.55,.15],[-.9,-1.5,-.2]],[5.5,[.2,1.2,-.2],[0,0,0]],[18,[.2,1.2,-.2],[0,0,0]]]
base={'source':'offboard','seed':20261110,'duration_s':20.,'knots':knots,'yaw_sweep_deg':120.,'reference_kind':'native_capture_after_classic_stream_end','planned_gaps':True,'initial_yaw_deg':0.,'altitude_m':3.5,'state_parameters':{'MC_RAPTOR_RINI':0,'MC_RAPTOR_RTGT':0,'MC_RAPTOR_RTDEC':2.,'MC_RAPTOR_RREC':0.,'MC_RAPTOR_NCO':0},'handover_reference':'native','native_quiet_before_request_s':.08,'profile':'coupled_3d_turn','reference_mode':'native','family':'physical','policy_scope':'fixed x500 policy; no training','single_seed_limit':True}

def fly(s,k):
 n=s['case'];p=B/f'round-{k:02d}-plan.json';dump(p,{'batch':str(B.relative_to(R)),'created_ns':time.time_ns(),'cases':{n:s}});run(p);f,tr=d.one(n,s);dump(A/(n+'-feedback.json'),f);dump(A/(n+'-early-trace.json'),tr)
 # Per-axis states and actual activated memory/target remain in per-case audit/ULog.
 row={'case':n,'spec':s,'V_growth':f['original_growth'],'speed_error_entry_m_s':tr['ev_m_s'][0],'tilt_entry_deg':f['entry_tilt_deg'],'omega_entry_rad_s':f['entry_omega_rad_s'],'feature':f};dump(A/(n+'-selection-feature.json'),row);return row

def main():
 protocol={'created_ns':time.time_ns(),'goal':'Does empirical physical V provide different prospective guidance than entry speed error on coupled 3D turning/yawing states? No preset winner.','seed':20261110,'max_launches':6,'history_fixed':'RINI0; RTGT0/RREC0/NCO0; fixed policy','process_fixed':'end reference at selected phase; wait .08s; normal N request/ACK; no reference resumed','physical':'3D S-shaped turn with climb/descent reversal plus 120deg yaw sweep; four entry phases','selectors':{'V':'mean of positive residual maxima V(t)-V(t0)*exp(-.5*(t-t0)) in first100/120/160ms','simple':'norm of actual velocity minus actual network target velocity at first owner-window native sample'},'child_operator':'compress all translation knot times and switch phase by .92, divide knot velocities by .92; yaw reference remains original120deg/4s, so yaw phase also changes relative to translation. Same operator for both selectors.','shared_choice':'if both choose same parent, launch one shared child and report no selection distinction','interpretation':'early rollout feedback, not pre-switch certificate; matched configuration does not guarantee identical actual state; no single-factor causal claims','safety':'unchanged existing protections; evidence/infrastructure failures retained; no retries'}
 dump(B/'protocol.json',protocol);dump(A/'planned-geometry.json',geometry(base,origin=(0,0,-3.5)))
 rows=[]
 for i,phase in enumerate([2.35,2.75,3.15,3.55],1):
  s=copy.deepcopy(base);n=f'{i:03d}_coupled_phase_{int(phase*100):03d}';s.update(case=n,label=n,switches=[[phase,'N']],search_role='shared_physical_pilot',rationale='同一三维紧弯+爬降换向+转头，在不同运动阶段接管；实际多轴速度姿态角速逐例核实，H/P固定。');rows.append(fly(s,i))
 v=sorted(rows,key=lambda r:(-r['V_growth'],r['case']))[0];speed=sorted(rows,key=lambda r:(-r['speed_error_entry_m_s'],r['case']))[0];tilt=sorted(rows,key=lambda r:(-r['tilt_entry_deg'],r['case']))[0]
 choice={'created_ns':time.time_ns(),'V_parent':v['case'],'speed_parent':speed['case'],'tilt_diagnostic_parent':tilt['case'],'candidates':[{k:r[k] for k in ['case','V_growth','speed_error_entry_m_s','tilt_entry_deg','omega_entry_rad_s']} for r in rows],'same_choice':v['case']==speed['case'],'operator':protocol['child_operator']};dump(A/'prospective-selection.json',choice);print('SELECTION',choice,flush=True)
 children=[]
 for j,(label,parent) in enumerate([('V',v)]+([] if v['case']==speed['case'] else [('speed',speed)]),5):
  s=copy.deepcopy(parent['spec']);n=f'{j:03d}_child_{label}';s['knots']=[[t*.92,p,[x/.92 for x in vel]] for t,p,vel in s['knots']];s['switches']=[[s['switches'][0][0]*.92,'N']];s.update(case=n,label=n,parent_case=parent['case'],search_role='prospective_'+('shared' if choice['same_choice'] else label),rationale='事前保存选父后，以两选择器完全相同的8%时间压缩物理算子生成；历史和参考接续参数不变。');children.append(fly(s,j))
 dump(A/'search-results.json',{'pilots':rows,'selection':choice,'children':children,'actual_launches':len(rows)+len(children)});print('FINISHED',len(rows)+len(children),flush=True)
if __name__=='__main__':main()
