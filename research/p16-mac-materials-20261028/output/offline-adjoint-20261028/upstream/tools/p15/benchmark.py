"""Before-flight finite compute benchmark on an exposed H row, no new labels."""
import json,sys,time,numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p15.common import *
from p15.state import parse
from p15.model import rank
from p11.pack import source_plan
from p12b.read_trace import load
from p12.execution import DTYPE

def main():
 out=register(B/'benchmark-v1','existing completed H listener row plus prior plan tests online compute bound; no new future data');run=R/'data/p14h-20261027/runs/p14h-d01-F4-A-before-s142710201/run';lines=[json.loads(l) for l in (run/'logs/commands.log').read_text().splitlines()];s=next(parse(x['output']) for x in lines if 'TOPIC: research_p11' in x['output']);r=load(run/'gz-motor/read-p12b.bin');j=np.flatnonzero((r['timestamp']==s['timestamp'])&(r['timestamp_sample']==s['timestamp_sample']))[0];s.update(call_index=int(r['call_index_pre'][j])+1,force_sync=2,history=s['policy_input'][18:],history_count=0 if s['gru_committed'] else 1,direct={k:int(r[k][j]) for k in r},execution=[],LP_W_m_s=s['velocity'][2],tilt_deg=0)
 for k in range(4):
  a=np.fromfile(run/f'gz-motor/execution-p12-{k}.bin',DTYPE);a=a[a['end_ns']<=s['read_wall_ns']];s['execution'].append({n:float(a[-1][n]) if a.dtype[n].kind=='f' else int(a[-1][n]) for n in a.dtype.names})
 cfg=json.load(open(run/'config.json'));events=[json.loads(l) for l in (run/'events.jsonl').read_text().splitlines()];org=next(e for e in events if e['event']=='p1_reference_origin');p=source_plan(cfg,org['origin_ned_m'],org['yaw_rad']);s['profile_s']=p['common_first_gap_profile_s']-1.;ctx=dict(H0_LP=-s['position'][2],D_LP=0,prefix_failed=False,A_start=p['common_first_gap_profile_s'],A_duration=.30,task_end=p['stream_end_profile_s'],reference_table=p['profile']['table'],table_t0=p['profile']['table_t0_s'],yaw=p['profile']['yaw']);pool=[dict(c,prefix='AB') for c in json.load(open(R/'config/p15/candidate-pool-v1.json'))['candidates']];st=time.perf_counter();result=rank(s,pool,ctx,json.load(open(R/'config/p15/model-v1.json')),dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz')),'M3',np.random.default_rng(1));result['wall_s']=time.perf_counter()-st;write(out/'result.json',result);write(out/'input.json',dict(snapshot=s,context=ctx));print('P15 benchmark',result['CPU_s'],result['wall_s'],result['selected'])
if __name__=='__main__':main()
