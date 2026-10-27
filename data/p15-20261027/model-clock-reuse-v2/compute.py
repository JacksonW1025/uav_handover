"""Finite frozen-model prefix reuse cost, never a physicalprefixfork claim."""
import json,sys,numpy as np
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p15.common import B,write,sha
sys.path.insert(0,str(Path(__file__).resolve().parent))
from model_clock import rollout
from p15.map import successor_snapshot
D=Path(__file__).resolve().parent
x=json.load(open(B/'runs/p15-d05-F2-AB-mild-v2/run/p15-map-prior-input.json'));s=x['snapshot'];ctx=x['context'];M=x['parameters'];P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));base=dict(id='prefix-AB',prefix='AB',D=.30,G=1.2);e=rollout(s,base,ctx,M,P);ss=successor_snapshot(s,e);ss['model_time_origin']=e['successor']['model_time_origin'];rows=[]
for duration in [.24,.30,.38]:
 for recovery in [1.2,1.8]:
  start=ss['profile_s']+recovery-1.;c=dict(id=f'C-D{duration}-R{recovery}',prefix='B',D=duration,G=recovery);ct=dict(ctx,A_start=start-ctx['A_duration']-recovery,D_LP=e['successor']['D'],prefix_failed=e['successor']['prefix_failure_latch']);tail=rollout(ss,c,ct,M,P);fullctx=dict(ctx,additional_windows=[[start,start+duration]],full_task_forecast=True,task_end=tail['full_prefix'][-1][0]);full=rollout(s,base,fullctx,M,P);joint=np.vstack([e['full_prefix'],np.asarray(tail['full_prefix'])[1:]]);z=np.asarray(full['full_prefix']);er=float(np.max(abs(joint-z))) if joint.shape==z.shape else None;he=float(np.max(abs(np.array(full['successor']['h'])-tail['successor']['h'])));rows.append(dict(query=c,prefix_source='same actual preA decisioninput, declarationmodel only',full_CPU_s=full['model_CPU_s'],incremental_CPU_s=tail['model_CPU_s'],same_rows=joint.shape==z.shape,trajectory_max_abs=er,h_max_abs=he,D_not_reset=tail['successor']['D']>=e['successor']['D'],stop_full=full['stop'],stop_tail=tail['stop']))
write(D/'result.json',dict(schema='P15-model-prefix-reuse-cost-v1',input_sha256=sha(B/'runs/p15-d05-F2-AB-mild-v2/run/p15-map-prior-input.json'),prefix_CPU_s=e['model_CPU_s'],rows=rows,K6_full_recompute_CPU_s=sum(r['full_CPU_s'] for r in rows),K6_anchor_plus_reuse_CPU_s=e['model_CPU_s']+sum(r['incremental_CPU_s'] for r in rows),physical_anchor_cost='one original devflight already charged inprogramme; no physical snapshotfork or free realprefixreuse',coverage='same frozen L15 pointmodel, no realjointdomain or safetycertificate',status='PASS' if all(r['same_rows'] and r['trajectory_max_abs']<1e-10 and r['h_max_abs']<1e-10 and r['D_not_reset'] for r in rows) else 'NOT_PASSED'))
print('MODEL_REUSE_COMPLETE',[(r['same_rows'],r['trajectory_max_abs']) for r in rows])
