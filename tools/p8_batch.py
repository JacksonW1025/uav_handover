#!/usr/bin/env python3
"""Pre-register and run a frozen P8 batch on one candidate (config/p8.json; P6/P7 batch rules).

Stages (groups pre-registered in config p4.groups):
  dev           development (--development): the new code paths (jump family, chase x0 4.0 with max_chase_s 3.9), never results
  equivalence   P6-A chase x2.0 V2.0 A0 twice with config/p6.json (frozen p6_metrics; rule p8.equivalence.a)
  a             the 8 identification flights (7 conditions, jump v2.5 L3.0 A0 twice), repetitions interleave the groups
  dev_b         development (--development) of the B case path: 5 P8 cases (headings 13-89 deg, 2-4 windows, shrunk budgets)
  equivalence_b P6 B1 v2.0-D0.3-A0:T0, C1 v2.0-D0.3-A45:T0, C2 M1-A0:T1 through the P8 case path, 2 runs each
                (rule p8.equivalence.b); B campaigns run with tools/p8_campaign.py
Every run gets its own Gazebo seed (first 31 bits of sha256(prefix/run id/master seed)), written to plan.json before it
runs. Checks after each run: the P2 checks (execution and analyzer verdict, PX4 exit, crash markers, preparation trace,
per-motor output-chain gate), then p8_metrics (config with a p8 section) or the frozen p6_metrics (config/p6.json).
Identification outcomes (IDENT_OK, IDENT_EXCEEDED_45, IDENT_ABORTED) with sound infrastructure and complete measurement
are results; any other failed check stops the batch, the remaining runs stay NOT_RUN, nothing is re-run in place.
"""
import argparse,json
from pathlib import Path
import p2_batch
from p2_batch import identity,write,now,host_state,ROOT
from p0_closure import GATE
import p6_batch,p8_conditions
from p6_batch import metric
P6_CONDITION_SPEC=p6_batch.condition_spec

def condition_spec(cfg,kind,condition):
    """P6 condition specs plus P8 case names (p8_conditions.case_spec) for p5_gap."""
    if kind=='p5_gap' and 'p8' in cfg and p8_conditions.parse_case(condition):return p8_conditions.case_spec(cfg,condition)
    return P6_CONDITION_SPEC(cfg,kind,condition)

def build_plan(prefix,groups,order_seed=None):
    p6_batch.condition_spec=condition_spec
    try:return p6_batch.build_plan(prefix,groups,order_seed)
    finally:p6_batch.condition_spec=P6_CONDITION_SPEC

def run_row(row,out):
    p2_batch.run_one(row,out)
    cfg=json.loads((ROOT/row['config']).read_text());run=ROOT/row['directory']
    have=(run/'flight.ulg').exists() and (run/'metrics.json').exists()
    name,tool,filename=('p8','p8_metrics.py','p8-metrics.json') if 'p8' in cfg else ('p6','p6_metrics.py','p6-metrics.json')
    if row['kind']=='p5_gap':return gap_row(row,out,run,have)
    if have:
        m=metric(row,out,name,tool,filename)
        io=m.get('ident_outcome') or {};row['ident_outcome']=io.get('class');row['ident_exceeded_45']=io.get('ident_exceeded_45')
        tc=(m.get('p8') or {}).get('task_criterion') or {};row['task_criterion_exceeded']=tc.get('exceeded');row['max_altitude_loss_m']=tc.get('max_altitude_loss_m')
    else:row['checks'][name+'_measured']=False
    infra=[k for k in row['checks'] if k not in ['execution','subject_measured']]
    row['infrastructure_ok']=all(row['checks'][k] for k in infra)
    # Identification outcomes are results; a runner safety abort ends execution early but is measured and exported.
    row['flight_failure']=False
    row['accepted']=bool(row['infrastructure_ok'] and row.get('ident_outcome') in ['IDENT_OK','IDENT_EXCEEDED_45','IDENT_ABORTED']
                         and (row['checks']['execution'] or row.get('ident_outcome')=='IDENT_ABORTED'))
    return row

def gap_row(row,out,run,have):
    """B: P7 batch rule (pre-registered flight failures with sound infrastructure and complete measurement are results)."""
    if have:
        m=metric(row,out,'p8','p8_metrics.py','p8-metrics.json')
        fo=m.get('flight_outcome') or {};row['flight_outcome']=fo.get('outcome');row['flight_failure_reasons']=fo.get('reasons')
        res=(m.get('p8') or {}).get('result') or {}
        row.update({'fail_primary':res.get('fail_primary'),'fail_task':res.get('fail_task'),'max_tilt_deg':res.get('max_tilt_deg'),'max_altitude_loss_m':res.get('max_altitude_loss_m'),
                    'gap_timing':((m.get('p8') or {}).get('gap_timing') or {}).get('status')})
        row['checks']['subject_measured']=bool(m.get('status')=='MEASURED' and fo.get('outcome')=='SUCCESS')
    else:row['checks']['p8_measured']=False
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
        print('END',row['id'],row['status'],'accepted='+str(row['accepted']),'flight_failure='+str(row.get('flight_failure')),'outcome='+str(row.get('ident_outcome') or row.get('flight_outcome')),
              'tilt='+str(row.get('max_tilt_deg')),'alt_loss='+str(row.get('max_altitude_loss_m')),flush=True)
        if not row['accepted'] and not row.get('flight_failure') and not development:return True
    return False

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--prefix',required=True)
    p.add_argument('--stage',required=True,choices=['dev','equivalence','a','dev_b','equivalence_b']);p.add_argument('--config',default='config/p8.json')
    p.add_argument('--purpose',required=True)
    p.add_argument('--development',action='store_true',help='development only: record failed checks and continue; never an acceptance result')
    args=p.parse_args();out=args.output.resolve();cfg=json.loads((ROOT/args.config).read_text())
    groups=p2_batch.parse_groups(cfg['p4']['groups'][args.stage],args.config)
    plan=build_plan(args.prefix,groups,None)
    out.mkdir(parents=True,exist_ok=False)
    candidate=identity();write(out/'candidate.json',candidate);write(out/'host.json',host_state())
    doc={'created_at':now(),'stage':args.stage,'host':cfg['p4']['host'],'purpose':args.purpose,'config':args.config,'output_chain_gate':GATE,'candidate':'candidate.json',
        'mode':'development' if args.development else 'standard','groups':groups,'order':'as listed (repetitions interleave the groups)',
        'independence':cfg['p4']['independence'],'ident_outcomes':cfg['p6']['ident']['outcome'],'criteria':cfg['p8']['criteria'],
        'stop_rule':'Identification outcomes with every infrastructure and evidence check passing are results and do not stop the batch; any other failed check stops it. Remaining runs stay NOT_RUN; nothing is re-run in place.',
        'runs':[{k:r[k] for k in ['id','kind','condition','treatment','config','repetition','sim_seed','initial_yaw_deg','directory']} for r in plan]}
    write(out/'plan.json',doc)
    failed=execute(plan,out,candidate,args.development)
    result=p2_batch.summary(plan,candidate,failed)
    result['identification_outcomes']={r['id']:r.get('ident_outcome') for r in plan if r['kind']=='p6_ident'}
    if args.development:result.update({'status':'DEVELOPMENT','failed_checks':{r['id']:[k for k,v in r['checks'].items() if not v] for r in plan if 'checks' in r}})
    write(out/'results.json',result);print(result['status'],out,flush=True)
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
