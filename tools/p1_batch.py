#!/usr/bin/env python3
"""Pre-register and run the frozen P1 batch: S1 first, optional pause for review, then S2/S3 under the same candidate.

Every run is checked right after it finishes (execution, analyzer verdict, PX4 exit, executor/output-chain
measurement and per-motor output-chain gate, P1 measurement). Any failure stops the batch; the remaining runs
stay NOT_RUN. --resume continues the same plan only if the candidate identity is unchanged.
"""
import argparse,datetime,json,subprocess
from pathlib import Path
from preparation_batch import identity,write
from p0_closure import GATE,measurement_errors
ROOT=Path(__file__).resolve().parents[1]
PY=str(ROOT/'uav_lab/.local/venv/bin/python')

def build_plan(prefix,cfg):
    p1=cfg['p1'];plan=[]
    for condition in p1['conditions']:
        for rep in range(1,max(p1['handover_repetitions'],p1['baseline_repetitions'])+1):
            kinds=(['p1_c_to_n','p1_n_to_c'] if rep<=p1['handover_repetitions'] else [])+(['p1_baseline_classic','p1_baseline_raptor'] if rep<=p1['baseline_repetitions'] else [])
            for kind in kinds:
                rid=f'{condition}-{kind[3:]}-{rep}'
                plan.append({'id':rid,'kind':kind,'condition':condition,'repetition':rep,'directory':f'data/{prefix}-{rid}','status':'NOT_RUN'})
    return plan

def chain_gate(oc):
    errors=measurement_errors(oc)
    for motor,value in oc.get('motors',{}).items():
        n=value.get('neural',{});age=n.get('applied_age_us') or {}
        if age.get('p99') is None or age['p99']>GATE['p99_us']:errors.append(motor+': p99 over gate')
        if age.get('max') is None or age['max']>GATE['max_us']:errors.append(motor+': max over gate')
        if n.get('longest_over_target_steps') is None or n['longest_over_target_steps']>GATE['longest_over_target_steps']:errors.append(motor+': consecutive over-target steps')
    return errors

def run_one(row,out):
    command=[str(ROOT/'tools/experiment'),row['kind'],'--condition',row['condition'],'--config',str(ROOT/'config/p1.json'),'--output',str(ROOT/row['directory'])]
    row['command']=command;row['started_at']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    with (out/(row['id']+'.log')).open('w') as log:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
    run=ROOT/row['directory'];row['exit_code']=code
    validation=json.loads((run/'validation.json').read_text()) if (run/'validation.json').exists() else {}
    row['status']=validation.get('status','FAIL');row['reason']=validation.get('reason')
    stops=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()] if (run/'events.jsonl').exists() else []
    row['px4_exit_codes']=[e['exit_code'] for e in stops if e['event']=='process_stopped' and e['name']=='px4']
    checks={'execution':code==0 and row['status'] in ['PASS','PASS_WITH_WARNINGS'],'px4_exit':row['px4_exit_codes']==[0]}
    if (run/'flight.ulg').exists() and (run/'metrics.json').exists():
        for name,tool in [('trace','preparation_trace.py'),('output_chain','output_chain.py'),('p1','p1_metrics.py')]:
            r=subprocess.run([PY,str(ROOT/'tools'/tool),str(run)],capture_output=True,text=True)
            (out/f"{row['id']}-{name}.log").write_text(r.stdout+r.stderr);row[name+'_exit_code']=r.returncode
        trace=json.loads((run/'preparation-trace.json').read_text()) if (run/'preparation-trace.json').exists() else {}
        checks['trace']=row['trace_exit_code']==0 and trace.get('status')=='MEASURED'
        oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
        row['output_chain_errors']=chain_gate(oc) if oc else ['missing output-chain.json']
        checks['output_chain']=row['output_chain_exit_code']==0 and not row['output_chain_errors']
        p1=json.loads((run/'p1-metrics.json').read_text()) if (run/'p1-metrics.json').exists() else {}
        checks['p1_measured']=row['p1_exit_code']==0 and p1.get('status')=='MEASURED'
        row['p1_problems']=p1.get('problems')
    else:checks['analysis_outputs']=False
    row['checks']=checks;row['accepted']=all(checks.values())
    return row['accepted']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--prefix')
    p.add_argument('--pause-after',choices=['S1','S2','S3'],help='stop cleanly after this condition for review')
    p.add_argument('--resume',action='store_true',help='continue the pre-registered plan in output');args=p.parse_args()
    out=args.output.resolve()
    if args.resume:
        plan_doc=json.loads((out/'plan.json').read_text());candidate=json.loads((out/'candidate.json').read_text())
        results=json.loads((out/'results.json').read_text());plan=results['runs']
        if any('exit_code' in r and not r.get('accepted') for r in plan):raise SystemExit('batch already stopped on a failure; not resuming')
        if identity()!=candidate:raise SystemExit('IDENTITY_DRIFT: candidate changed since pre-registration; not resuming')
    else:
        if not args.prefix:p.error('--prefix required for a new batch')
        out.mkdir(parents=True,exist_ok=False)
        cfg=json.loads((ROOT/'config/p1.json').read_text())
        candidate=identity();write(out/'candidate.json',candidate)
        plan=build_plan(args.prefix,cfg)
        plan_doc={'created_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'config':'config/p1.json',
            'purpose':'P1 exploratory handover performance batch (original RAPTOR reset / original classic AUTO_LOITER takeover). 30 handovers plus same-controller baselines; exploratory budget, not a statistical test.',
            'order':'S1, then S2, then S3; within a condition repetitions interleave kinds. Review pause after S1 keeps the same frozen candidate.',
            'output_chain_gate':GATE,'stop_rule':'Any failed check stops the batch for diagnosis; remaining runs stay NOT_RUN; nothing is re-run in place.',
            'runs':[{k:r[k] for k in ['id','kind','condition','repetition','directory']} for r in plan]}
        write(out/'plan.json',plan_doc)
    failed=False;paused=False
    for i,row in enumerate(plan):
        if row['status']!='NOT_RUN':continue
        if identity()!=candidate:row['status']='IDENTITY_DRIFT';failed=True;break
        print('START',row['id'],flush=True)
        ok=run_one(row,out)
        write(out/'results.json',{'runs':plan,'complete':False})
        print('END',row['id'],row['status'],'accepted='+str(ok),flush=True)
        if not ok:failed=True;break
        nxt=plan[i+1] if i+1<len(plan) else None
        if args.pause_after and row['condition']==args.pause_after and nxt and nxt['condition']!=args.pause_after:paused=True;break
    done=not failed and all(r['status']!='NOT_RUN' for r in plan)
    result={'status':'FAIL' if failed else ('PASS' if done else 'PAUSED'),'complete':done,
        'accepted':sum(bool(r.get('accepted')) for r in plan),'failed':sum('exit_code' in r and not r.get('accepted') for r in plan),
        'not_run':sum(r['status']=='NOT_RUN' for r in plan),'candidate_unchanged':identity()==candidate,'runs':plan}
    write(out/'results.json',result);print(result['status'],out,flush=True)
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
