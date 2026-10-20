#!/usr/bin/env python3
"""Pre-register and run a frozen P7 batch on one candidate (config/p7.json; P6 batch rules).

Stages (groups pre-registered in config p4.groups):
  dev           development (--development): every new code path, never results
  equivalence   P6 B1 cells T0 v2.0 D0.4 and T1a3 v2.0 D0.7 with config/p6.json (frozen p6_metrics), 2 runs each
  a, c          one list shuffled with random.Random(p7.a.order_seed / p7.c.order_seed)
  b             the 12 pre-registered random sequences in draw order
Every run gets its own Gazebo seed (first 31 bits of sha256(prefix/run id/master seed)), written to plan.json before it
runs. Checks after each run: the P2 checks (execution and analyzer verdict, PX4 exit, crash markers, preparation trace,
per-motor output-chain gate), then p7_metrics (config with a p7 section) or p6_metrics (config/p6.json). Pre-registered
flight failures with sound infrastructure and complete measurement are results; any other failed check stops the batch,
the remaining runs stay NOT_RUN, nothing is re-run in place.
"""
import argparse,json,random
from pathlib import Path
import p2_batch
from p2_batch import identity,write,now,host_state,ROOT
from p0_closure import GATE
from p6_batch import build_plan,metric

def run_row(row,out):
    p2_batch.run_one(row,out)
    cfg=json.loads((ROOT/row['config']).read_text());run=ROOT/row['directory']
    have=(run/'flight.ulg').exists() and (run/'metrics.json').exists()
    name,tool,filename=('p7','p7_metrics.py','p7-metrics.json') if 'p7' in cfg else ('p6','p6_metrics.py','p6-metrics.json')
    if have:
        m=metric(row,out,name,tool,filename)
        fo=m.get('flight_outcome') or {};row['flight_outcome']=fo.get('outcome');row['flight_failure_reasons']=fo.get('reasons')
        row['checks']['subject_measured']=bool(m.get('status')=='MEASURED' and fo.get('outcome')=='SUCCESS')
    else:row['checks'][name+'_measured']=False
    infra=[k for k in row['checks'] if k not in ['execution','subject_measured']]
    row['infrastructure_ok']=all(row['checks'][k] for k in infra)
    row['flight_failure']=bool(row['infrastructure_ok'] and row.get('flight_outcome')=='FAILURE')
    row['accepted']=all(row['checks'].values()) and not row['flight_failure']
    return row

def execute(plan,out,candidate,development=False):
    for row in plan:
        if row['status']!='NOT_RUN':continue
        if identity()!=candidate:row['status']='IDENTITY_DRIFT';return True
        print('START',row['id'],'seed',row['sim_seed'],flush=True)
        run_row(row,out);write(out/'results.json',{'runs':plan,'complete':False})
        print('END',row['id'],row['status'],'accepted='+str(row['accepted']),'flight_failure='+str(row['flight_failure']),'outcome='+str(row.get('flight_outcome')),flush=True)
        if not row['accepted'] and not row['flight_failure'] and not development:return True
    return False

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--prefix',required=True)
    p.add_argument('--stage',required=True,choices=['dev','equivalence','a','b','c']);p.add_argument('--config',default='config/p7.json')
    p.add_argument('--purpose',required=True)
    p.add_argument('--development',action='store_true',help='development only: record failed checks and continue; never an acceptance result')
    args=p.parse_args();out=args.output.resolve();cfg=json.loads((ROOT/args.config).read_text())
    groups=p2_batch.parse_groups(cfg['p4']['groups'][args.stage],args.config)
    seed={'a':cfg['p7']['a']['order_seed'],'c':cfg['p7']['c']['order_seed']}.get(args.stage)
    plan=build_plan(args.prefix,groups,seed)
    out.mkdir(parents=True,exist_ok=False)
    candidate=identity();write(out/'candidate.json',candidate);write(out/'host.json',host_state())
    doc={'created_at':now(),'stage':args.stage,'host':cfg['p4']['host'],'purpose':args.purpose,'config':args.config,'output_chain_gate':GATE,'candidate':'candidate.json',
        'mode':'development' if args.development else 'standard','groups':groups,'order':f'shuffled with random.Random({seed})' if seed is not None else 'as listed (repetitions interleave the groups)',
        'independence':cfg['p4']['independence'],'flight_failures':cfg['p5']['failure_criteria'],'cancelled':cfg['p7']['cancelled'],
        'stop_rule':'Pre-registered flight failures with every infrastructure and evidence check passing are results and do not stop the batch; any other failed check stops it. Remaining runs stay NOT_RUN; nothing is re-run in place.',
        'runs':[{k:r[k] for k in ['id','kind','condition','treatment','config','repetition','sim_seed','initial_yaw_deg','directory']} for r in plan]}
    write(out/'plan.json',doc)
    failed=execute(plan,out,candidate,args.development)
    result=p2_batch.summary(plan,candidate,failed)
    if args.development:result.update({'status':'DEVELOPMENT','failed_checks':{r['id']:[k for k,v in r['checks'].items() if not v] for r in plan if 'checks' in r}})
    write(out/'results.json',result);print(result['status'],out,flush=True)
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
