#!/usr/bin/env python3
"""Pre-register and run a frozen P4 batch on one candidate (P2/P3 run kinds, same checks, plus P4 run conditions).

Groups are KIND:CONDITION:TREATMENT:N with P2 kinds (p2_c_to_n, p2_baseline_raptor; conditions M1, M2) and P3 kinds
(p3_sequence, p3_baseline_raptor; conditions D2, R, M3), all from one config (default config/p4.json). Repetitions
interleave the groups. Every run gets its own pre-registered Gazebo seed and, for the conditions listed in
p4.independence.initial_yaw.conditions, an initial heading (both recorded in plan.json before the first run).

Every run is checked right after it finishes: the P2 checks (execution and analyzer verdict, PX4 exit, crash markers,
preparation trace, per-motor output-chain gate, p2_metrics) or the P3 checks (the same plus p3_metrics and p3_memory),
then p4_metrics (seed and heading realized, takeover states, teacher-forcing coverage for N2, planned-path check).
Pre-registered flight failures with sound infrastructure and complete measurement are results (config
p3.flight_failures); any other failed check stops the batch, the remaining runs stay NOT_RUN and nothing is re-run.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
import numpy as np
import p2_batch,p3_batch
from p2_batch import identity,write,now,host_state,PY,ROOT
from p0_closure import GATE

def parse_groups(text):
    groups=[]
    for item in text.split(','):
        kind,condition,treatment,n=item.strip().split(':');groups.append({'kind':kind,'condition':condition,'treatment':treatment,'n':int(n)})
    return groups

def run_conditions(prefix,rid,condition,cfg):
    ind=cfg['p4']['independence'];h=hashlib.sha256(f"{prefix}/{rid}/{ind['master_seed']}".encode()).digest()
    seed=int.from_bytes(h[:4],'big')&0x7fffffff;yaw=None
    if condition in ind['initial_yaw']['conditions']:
        lo,hi=ind['initial_yaw']['range_deg'];yaw=round(float(np.random.default_rng(seed).uniform(lo,hi)),3)
    return seed,yaw

def build_plan(prefix,groups,config,cfg):
    plan=[]
    for rep in range(1,max(g['n'] for g in groups)+1):
        for g in groups:
            if rep>g['n']:continue
            rid=f"{g['condition']}-{g['treatment']}-{rep}";seed,yaw=run_conditions(prefix,rid,g['condition'],cfg)
            extra=['--sim-seed',str(seed)]+(['--initial-yaw-deg',str(yaw)] if yaw is not None else [])
            plan.append({'id':rid,'kind':g['kind'],'condition':g['condition'],'treatment':g['treatment'],'config':config,'repetition':rep,
                         'sim_seed':seed,'initial_yaw_deg':yaw,'extra_args':extra,'directory':f'data/{prefix}-{rid}','status':'NOT_RUN'})
    if len({r['sim_seed'] for r in plan})!=len(plan):raise RuntimeError('seed collision in plan')
    return plan

def run_row(row,out):
    if row['kind'].startswith('p3_'):p3_batch.run_row(row,out)
    else:
        p2_batch.run_one(row,out)
        row['checks'].setdefault('subject_measured',False)
    run=ROOT/row['directory']
    if (run/'flight.ulg').exists() and ((run/'p3-metrics.json').exists() or (run/'p2-metrics.json').exists()):
        r=subprocess.run([PY,str(ROOT/'tools/p4_metrics.py'),str(run)],capture_output=True,text=True,cwd=ROOT/'tools')
        (out/f"{row['id']}-p4.log").write_text(r.stdout+r.stderr);row['p4_exit_code']=r.returncode
        m=json.loads((run/'p4-metrics.json').read_text()) if (run/'p4-metrics.json').exists() else {}
        row['p4_problems']=m.get('problems');row['checks']['p4_measured']=r.returncode==0 and m.get('status')=='MEASURED'
        row['teacher_forcing_coverage']=m.get('teacher_forcing_coverage');row['takeover_state']=m.get('takeover_state')
    else:row['checks']['p4_measured']=False
    infra=[k for k in row['checks'] if k not in ['execution','subject_measured']]
    row['infrastructure_ok']=all(row['checks'][k] for k in infra)
    row['flight_failure']=bool(row['infrastructure_ok'] and row.get('flight_outcome')=='FAILURE')
    row['accepted']=all(row['checks'].values()) and not row['flight_failure']
    return row

def execute(plan,out,candidate,development=False):
    for row in plan:
        if row['status']!='NOT_RUN':continue
        if identity()!=candidate:row['status']='IDENTITY_DRIFT';return True
        print('START',row['id'],'seed',row['sim_seed'],'yaw',row['initial_yaw_deg'],flush=True)
        run_row(row,out)
        write(out/'results.json',{'runs':plan,'complete':False})
        print('END',row['id'],row['status'],'accepted='+str(row['accepted']),'flight_failure='+str(row['flight_failure']),flush=True)
        if not row['accepted'] and not row['flight_failure'] and not development:return True
    return False

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--prefix',required=True)
    p.add_argument('--groups',required=True,help='KIND:CONDITION:TREATMENT:N,...');p.add_argument('--config',default='config/p4.json')
    p.add_argument('--purpose',required=True)
    p.add_argument('--development',action='store_true',help='development only: record failed checks and continue; such a batch is never an acceptance result')
    args=p.parse_args()
    out=args.output.resolve();cfg=json.loads((ROOT/args.config).read_text());groups=parse_groups(args.groups)
    plan=build_plan(args.prefix,groups,args.config,cfg);out.mkdir(parents=True,exist_ok=False)
    candidate=identity();write(out/'candidate.json',candidate);write(out/'host.json',host_state())
    write(out/'plan.json',{'created_at':now(),'host':cfg['p4']['host'],'purpose':args.purpose,'config':args.config,'output_chain_gate':GATE,'candidate':'candidate.json',
        'mode':'development' if args.development else 'standard','groups':groups,'order':'repetitions interleave the groups','independence':cfg['p4']['independence'],
        'flight_failures':cfg['p3']['flight_failures'],'teacher_forcing_rule':cfg['p4']['teacher_forcing_rule'],
        'stop_rule':'Pre-registered flight failures with every infrastructure and evidence check passing are results and do not stop the batch; any other failed check stops it. Remaining runs stay NOT_RUN; nothing is re-run in place.',
        'runs':[{k:r[k] for k in ['id','kind','condition','treatment','config','repetition','sim_seed','initial_yaw_deg','directory']} for r in plan]})
    failed=execute(plan,out,candidate,args.development);result=p2_batch.summary(plan,candidate,failed)
    if args.development:result.update({'status':'DEVELOPMENT','failed_checks':{r['id']:[k for k,v in r['checks'].items() if not v] for r in plan if 'checks' in r}})
    write(out/'results.json',result);print(result['status'],out,flush=True)
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
