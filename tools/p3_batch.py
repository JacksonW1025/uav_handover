#!/usr/bin/env python3
"""Pre-register and run a frozen P3 batch on one candidate (same machinery as p2_batch).

Groups are KIND:CONDITION:TREATMENT:N; repetitions interleave the groups. Every run is checked right after it finishes:
execution and analyzer verdict, PX4 exit, crash markers, preparation trace, per-motor output-chain gate (p2_batch),
then p3_metrics (sequence, parameters, exit/entry memory, teacher forcing, capture, recovery stages) and p3_memory
(exact policy replay of the logged inputs). Pre-registered flight failures with sound infrastructure and complete
measurement are results (config p3.flight_failures); any other failed check stops the batch, the remaining runs stay
NOT_RUN and nothing is re-run in place.
"""
import argparse,json,subprocess
from pathlib import Path
import p2_batch
from p2_batch import identity,write,now,host_state,HOST,PY,ROOT
from p0_closure import GATE

def parse_groups(text):
    groups=[]
    for item in text.split(','):
        kind,condition,treatment,n=item.strip().split(':');groups.append({'kind':kind,'condition':condition,'treatment':treatment,'n':int(n)})
    return groups

def build_plan(prefix,groups,config):
    plan=[]
    for rep in range(1,max(g['n'] for g in groups)+1):
        for g in groups:
            if rep>g['n']:continue
            rid=f"{g['condition']}-{g['treatment']}-{rep}"
            plan.append({'id':rid,'kind':g['kind'],'condition':g['condition'],'treatment':g['treatment'],'config':config,'repetition':rep,
                         'directory':f'data/{prefix}-{rid}','status':'NOT_RUN'})
    return plan

def run_row(row,out):
    p2_batch.run_one(row,out);run=ROOT/row['directory']
    if (run/'metrics.json').exists() and (run/'flight.ulg').exists():
        for name,tool in [('p3','p3_metrics.py'),('p3_memory','p3_memory.py')]:
            r=subprocess.run([PY,str(ROOT/'tools'/tool),str(run)],capture_output=True,text=True,cwd=ROOT/'tools')
            (out/f"{row['id']}-{name}.log").write_text(r.stdout+r.stderr);row[name+'_exit_code']=r.returncode
        m=json.loads((run/'p3-metrics.json').read_text()) if (run/'p3-metrics.json').exists() else {}
        mm=json.loads((run/'p3-memory.json').read_text()) if (run/'p3-memory.json').exists() else {}
        row['p3_problems']=m.get('problems');row['p3_memory_problems']=mm.get('problems')
        fo=m.get('flight_outcome') or {};row['flight_outcome']=fo.get('outcome');row['flight_failure_reasons']=fo.get('reasons')
        row['checks']['p3_measured']=row['p3_exit_code']==0 and m.get('p3_status')=='MEASURED'
        row['checks']['p3_memory_replay']=row['p3_memory_exit_code']==0 and mm.get('status')=='MEASURED'
        row['deactivation']=m.get('deactivation')
    else:row['checks']['p3_measured']=False
    infra=[k for k in row['checks'] if k not in ['execution','subject_measured']]
    row['infrastructure_ok']=all(row['checks'][k] for k in infra)
    # A pre-registered flight failure needs complete measurement and evidence; only the flight outcome may fail.
    row['flight_failure']=bool(row['infrastructure_ok'] and row.get('flight_outcome')=='FAILURE')
    row['accepted']=all(row['checks'].values()) and not row['flight_failure']
    return row

def execute(plan,out,candidate):
    for row in plan:
        if row['status']!='NOT_RUN':continue
        if identity()!=candidate:row['status']='IDENTITY_DRIFT';return True
        print('START',row['id'],flush=True)
        run_row(row,out)
        write(out/'results.json',{'runs':plan,'complete':False})
        print('END',row['id'],row['status'],'accepted='+str(row['accepted']),'flight_failure='+str(row['flight_failure']),flush=True)
        if not row['accepted'] and not row['flight_failure']:return True
    return False

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--prefix',required=True)
    p.add_argument('--groups',required=True,help='KIND:CONDITION:TREATMENT:N,...');p.add_argument('--config',default='config/p3.json')
    p.add_argument('--purpose',required=True);args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    candidate=identity();write(out/'candidate.json',candidate);write(out/'host.json',host_state())
    cfg=json.loads((ROOT/args.config).read_text());groups=parse_groups(args.groups);plan=build_plan(args.prefix,groups,args.config)
    write(out/'plan.json',{'created_at':now(),'host':HOST,'purpose':args.purpose,'config':args.config,'output_chain_gate':GATE,'candidate':'candidate.json',
        'mode':'standard','groups':groups,'order':'repetitions interleave the groups','flight_failures':cfg['p3']['flight_failures'],
        'stop_rule':'Pre-registered flight failures with every infrastructure and evidence check passing are results and do not stop the batch; any other failed check stops it. Remaining runs stay NOT_RUN; nothing is re-run in place.',
        'runs':[{k:r[k] for k in ['id','kind','condition','treatment','config','repetition','directory']} for r in plan]})
    failed=execute(plan,out,candidate);result=p2_batch.summary(plan,candidate,failed)
    write(out/'results.json',result);print(result['status'],out,flush=True)
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
