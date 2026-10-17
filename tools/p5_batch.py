#!/usr/bin/env python3
"""Pre-register and run a frozen P5 batch on one candidate (P2 kinds for E1/E4 and the equivalence, p5_gap for E2/E3).

Groups are KIND:CONDITION:TREATMENT:N[@CONFIG] (default config/p5.json); repetitions interleave the groups. Every run
gets its own pre-registered Gazebo seed (P4 rule: first 31 bits of sha256(prefix/run id/master seed of the run's
config)) and, for conditions with a fixed initial_yaw_deg (E1 Y45), that spawn yaw; both are written to plan.json
before the first run. Checks after each run: the P2 checks (execution and analyzer verdict, PX4 exit, crash markers,
preparation trace, per-motor output-chain gate, p2_metrics for P2 kinds), p4_metrics (P2 kinds: seed and heading
realized, takeover state, teacher-forcing coverage), p4c_metrics (C->N with a config that has a p4c section) and
p5_metrics (config with a p5 section). Pre-registered flight failures with sound infrastructure and complete
measurement are results; any other failed check stops the batch, the remaining runs stay NOT_RUN, nothing is re-run.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
import p2_batch
from p2_batch import identity,write,now,host_state,PY,ROOT
from p0_closure import GATE

def condition_spec(cfg,kind,condition):
    return cfg['p5']['conditions'][condition] if kind=='p5_gap' else cfg['p2']['conditions'][condition]

def run_conditions(prefix,rid,cfg,spec):
    ind=cfg['p4']['independence'];h=hashlib.sha256(f"{prefix}/{rid}/{ind['master_seed']}".encode()).digest()
    return int.from_bytes(h[:4],'big')&0x7fffffff,spec.get('initial_yaw_deg')

def build_plan(prefix,groups):
    plan=[]
    for rep in range(1,max(g['n'] for g in groups)+1):
        for g in groups:
            if rep>g['n']:continue
            cfg=json.loads((ROOT/g['config']).read_text());spec=condition_spec(cfg,g['kind'],g['condition'])
            rid=f"{g['condition']}-{g['treatment']}-{rep}";seed,yaw=run_conditions(prefix,rid,cfg,spec)
            extra=['--sim-seed',str(seed)]+(['--initial-yaw-deg',str(yaw)] if yaw is not None else [])
            plan.append({'id':rid,'kind':g['kind'],'condition':g['condition'],'treatment':g['treatment'],'config':g['config'],'repetition':rep,
                         'sim_seed':seed,'initial_yaw_deg':yaw,'extra_args':extra,'directory':f'data/{prefix}-{rid}','status':'NOT_RUN'})
    if len({r['id'] for r in plan})!=len(plan):raise RuntimeError('run id collision in plan')
    if len({r['sim_seed'] for r in plan})!=len(plan):raise RuntimeError('seed collision in plan')
    return plan

def metric(row,out,name,tool,filename):
    run=ROOT/row['directory'];r=subprocess.run([PY,str(ROOT/'tools'/tool),str(run)],capture_output=True,text=True,cwd=ROOT/'tools')
    (out/f"{row['id']}-{name}.log").write_text(r.stdout+r.stderr);row[name+'_exit_code']=r.returncode
    m=json.loads((run/filename).read_text()) if (run/filename).exists() else {}
    row[name+'_problems']=m.get('problems');row['checks'][name+'_measured']=r.returncode==0 and m.get('status')=='MEASURED'
    return m

def run_row(row,out):
    p2_batch.run_one(row,out)
    cfg=json.loads((ROOT/row['config']).read_text());run=ROOT/row['directory']
    have=(run/'flight.ulg').exists() and (run/'metrics.json').exists()
    if row['kind'].startswith('p2_'):
        row['checks'].setdefault('subject_measured',False)
        if have and (run/'p2-metrics.json').exists():
            m=metric(row,out,'p4','p4_metrics.py','p4-metrics.json');row['takeover_state']=m.get('takeover_state')
            if row['kind']=='p2_c_to_n' and 'p4c' in cfg:
                m=metric(row,out,'p4c','p4c_metrics.py','p4c-metrics.json');row['target_check']=(m.get('target') or {}).get('status')
        else:row['checks']['p4_measured']=False
    if 'p5' in cfg:
        if have:
            m=metric(row,out,'p5','p5_metrics.py','p5-metrics.json')
            if row['kind']=='p5_gap':
                fo=m.get('flight_outcome') or {};row['flight_outcome']=fo.get('outcome');row['flight_failure_reasons']=fo.get('reasons')
                row['checks']['subject_measured']=bool(m.get('status')=='MEASURED' and fo.get('outcome')=='SUCCESS')
        else:row['checks']['p5_measured']=False
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
    p.add_argument('--groups',required=True,help='KIND:CONDITION:TREATMENT:N[@CONFIG],...');p.add_argument('--config',default='config/p5.json')
    p.add_argument('--purpose',required=True)
    p.add_argument('--development',action='store_true',help='development only: record failed checks and continue; such a batch is never an acceptance result')
    args=p.parse_args()
    out=args.output.resolve();cfg=json.loads((ROOT/args.config).read_text());groups=p2_batch.parse_groups(args.groups,args.config)
    plan=build_plan(args.prefix,groups);out.mkdir(parents=True,exist_ok=False)
    candidate=identity();write(out/'candidate.json',candidate);write(out/'host.json',host_state())
    write(out/'plan.json',{'created_at':now(),'host':cfg['p4']['host'],'purpose':args.purpose,'config':args.config,'output_chain_gate':GATE,'candidate':'candidate.json',
        'mode':'development' if args.development else 'standard','groups':groups,'order':'repetitions interleave the groups','independence':cfg['p4']['independence'],
        'flight_failures':cfg['p5']['failure_criteria'] if 'p5' in cfg else cfg['p2']['exploration']['failure_criteria'],
        'stop_rule':'Pre-registered flight failures with every infrastructure and evidence check passing are results and do not stop the batch; any other failed check stops it. Remaining runs stay NOT_RUN; nothing is re-run in place.',
        'runs':[{k:r[k] for k in ['id','kind','condition','treatment','config','repetition','sim_seed','initial_yaw_deg','directory']} for r in plan]})
    failed=execute(plan,out,candidate,args.development);result=p2_batch.summary(plan,candidate,failed)
    if args.development:result.update({'status':'DEVELOPMENT','failed_checks':{r['id']:[k for k,v in r['checks'].items() if not v] for r in plan if 'checks' in r}})
    write(out/'results.json',result);print(result['status'],out,flush=True)
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
