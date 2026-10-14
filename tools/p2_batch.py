#!/usr/bin/env python3
"""Pre-register and run a frozen P2 batch on one candidate.

Groups are KIND:CONDITION:TREATMENT:N[@CONFIG] ('-' for none); repetitions interleave the groups. Every run is checked
right after it finishes (execution and analyzer verdict, PX4 exit, crash markers, preparation trace, per-motor
output-chain gate, P1/P2 measurement incl. treatment evidence).

standard: any failed check stops the batch; the remaining runs stay NOT_RUN; nothing is re-run in place.
exploration: levels from config p2.exploration run in order. A flight failure (pre-registered criteria met while all
infrastructure checks pass) is a result and does not stop the batch, but escalation stops after that level; then the
highest level gets the N->C group and the failed level the best step-1 treatment. Infrastructure failures stop.
"""
import argparse,datetime,json,re,subprocess
from pathlib import Path
from preparation_batch import identity,write
from p1_batch import chain_gate
from p0_closure import GATE
from preparation_audit import CRASH
ROOT=Path(__file__).resolve().parents[1]
PY=str(ROOT/'uav_lab/.local/venv/bin/python')
SHORT={'p2_c_to_n':'c_to_n','p2_n_to_c':'n_to_c','p2_baseline_raptor':'baseline_raptor','p2_baseline_classic':'baseline_classic',
       'p1_c_to_n':'p1_c_to_n','p1_n_to_c':'p1_n_to_c','p1_baseline_raptor':'p1_baseline_raptor','p1_baseline_classic':'p1_baseline_classic'}

def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

def parse_groups(text,default_config):
    groups=[]
    for item in text.split(','):
        spec,_,config=item.strip().partition('@')
        kind,condition,treatment,n=spec.split(':')
        groups.append({'kind':kind,'condition':None if condition=='-' else condition,'treatment':None if treatment=='-' else treatment,
                       'n':int(n),'config':config or default_config})
    return groups

def build_plan(prefix,groups,start=1,tag=None):
    plan=[];seen={}
    for rep in range(1,max(g['n'] for g in groups)+1):
        for g in groups:
            if rep>g['n']:continue
            parts=[x for x in [g['condition'],SHORT.get(g['kind'],g['kind']),g['treatment']] if x]
            key='-'.join(parts);seen[key]=seen.get(key,0)+1
            rid=f"{key}-{seen[key]+start-1}"
            plan.append({'id':rid,'kind':g['kind'],'condition':g['condition'],'treatment':g['treatment'],'config':g['config'],
                         'repetition':seen[key],'directory':f'data/{prefix}-{rid}','status':'NOT_RUN',**({'group':tag} if tag else {})})
    return plan

def run_one(row,out):
    command=[str(ROOT/'tools/experiment'),row['kind'],'--config',str(ROOT/row['config']),'--output',str(ROOT/row['directory'])]
    if row['condition']:command+=['--condition',row['condition']]
    if row['treatment']:command+=['--treatment',row['treatment']]
    row['command']=command;row['started_at']=now()
    with (out/(row['id']+'.log')).open('w') as log:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
    run=ROOT/row['directory'];row['exit_code']=code;row['finished_at']=now()
    validation=json.loads((run/'validation.json').read_text()) if (run/'validation.json').exists() else {}
    row['status']=validation.get('status','FAIL');row['reason']=validation.get('reason')
    stops=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()] if (run/'events.jsonl').exists() else []
    row['px4_exit_codes']=[e['exit_code'] for e in stops if e['event']=='process_stopped' and e['name']=='px4']
    log=(run/'logs/px4.log').read_text(errors='replace') if (run/'logs/px4.log').exists() else ''
    row['crash_markers']=sorted({x.lower() for x in CRASH.findall(log)})
    flight={'execution':code==0 and row['status'] in ['PASS','PASS_WITH_WARNINGS']}
    infra={'px4_exit':row['px4_exit_codes']==[0],'no_crash_markers':not row['crash_markers']}
    if (run/'flight.ulg').exists() and (run/'metrics.json').exists():
        tools=[('trace','preparation_trace.py'),('output_chain','output_chain.py')]
        if row['kind'].startswith('p1_'):tools.append(('p1','p1_metrics.py'))
        if row['kind'].startswith('p2_'):tools.append(('p2','p2_metrics.py'))
        for name,tool in tools:
            r=subprocess.run([PY,str(ROOT/'tools'/tool),str(run)],capture_output=True,text=True,cwd=ROOT/'tools')
            (out/f"{row['id']}-{name}.log").write_text(r.stdout+r.stderr);row[name+'_exit_code']=r.returncode
        trace=json.loads((run/'preparation-trace.json').read_text()) if (run/'preparation-trace.json').exists() else {}
        infra['trace']=row['trace_exit_code']==0 and trace.get('status')=='MEASURED'
        oc=json.loads((run/'output-chain.json').read_text()) if (run/'output-chain.json').exists() else {}
        row['output_chain_errors']=chain_gate(oc) if oc else ['missing output-chain.json']
        infra['output_chain']=row['output_chain_exit_code']==0 and not row['output_chain_errors']
        row['output_chain_max_age_us']=max(((v.get('neural',{}).get('applied_age_us') or {}).get('max') or 0) for v in oc.get('motors',{}).values()) if oc else None
        if 'p1_exit_code' in row:
            m=json.loads((run/'p1-metrics.json').read_text()) if (run/'p1-metrics.json').exists() else {}
            infra['p1_measured']=row['p1_exit_code']==0 and m.get('status')=='MEASURED';row['p1_problems']=m.get('problems')
        if 'p2_exit_code' in row:
            m=json.loads((run/'p2-metrics.json').read_text()) if (run/'p2-metrics.json').exists() else {}
            infra['p2_measured']=row['p2_exit_code']==0 and m.get('p2_status')=='MEASURED';row['p2_problems']=m.get('problems')
            fo=m.get('flight_outcome') or {};row['flight_outcome']=fo.get('outcome');row['flight_failure_reasons']=fo.get('reasons')
            flight['subject_measured']=m.get('status')=='MEASURED'
    else:infra['analysis_outputs']=False
    row['checks']={**infra,**flight};row['infrastructure_ok']=all(infra.values())
    row['accepted']=all(row['checks'].values())
    # Exploration only: a flight failure that meets the pre-registered criteria with sound infrastructure is a result.
    row['flight_failure']=bool(row['infrastructure_ok'] and not row['accepted'] and row.get('flight_outcome')=='FAILURE')
    return row

def summary(plan,candidate,failed):
    done=not failed and all(r['status']!='NOT_RUN' for r in plan)
    return {'status':'FAIL' if failed else ('PASS' if done else 'PAUSED'),'complete':done,
        'accepted':sum(bool(r.get('accepted')) for r in plan),'flight_failures':sum(bool(r.get('flight_failure')) for r in plan),
        'failed':sum('exit_code' in r and not r.get('accepted') and not r.get('flight_failure') for r in plan),
        'not_run':sum(r['status']=='NOT_RUN' for r in plan),'candidate_unchanged':identity()==candidate,'runs':plan}

def execute(plan,out,candidate,exploration=False):
    for row in plan:
        if row['status']!='NOT_RUN':continue
        if identity()!=candidate:row['status']='IDENTITY_DRIFT';return True
        print('START',row['id'],flush=True)
        run_one(row,out)
        write(out/'results.json',{'runs':plan,'complete':False})
        print('END',row['id'],row['status'],'accepted='+str(row['accepted']),'flight_failure='+str(row['flight_failure']),flush=True)
        if not row['accepted'] and not (exploration and row['flight_failure']):return True
    return False

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--prefix',required=True)
    p.add_argument('--groups',help='KIND:CONDITION:TREATMENT:N[@CONFIG],... (standard mode)')
    p.add_argument('--config',default='config/p2.json');p.add_argument('--purpose',required=True)
    p.add_argument('--exploration',action='store_true');p.add_argument('--best-treatment',help='exploration: best step-1 treatment')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    candidate=identity();write(out/'candidate.json',candidate)
    doc={'created_at':now(),'purpose':args.purpose,'config':args.config,'output_chain_gate':GATE,'candidate':'candidate.json'}
    if not args.exploration:
        groups=parse_groups(args.groups,args.config);plan=build_plan(args.prefix,groups)
        doc.update({'mode':'standard','groups':groups,'order':'repetitions interleave the groups',
            'stop_rule':'Any failed check stops the batch for diagnosis; remaining runs stay NOT_RUN; nothing is re-run in place.',
            'runs':[{k:r[k] for k in ['id','kind','condition','treatment','config','repetition','directory']} for r in plan]})
        write(out/'plan.json',doc)
        failed=execute(plan,out,candidate)
    else:
        if not args.best_treatment:p.error('--best-treatment required for exploration')
        cfg=json.loads((ROOT/args.config).read_text())['p2']['exploration']
        expand=lambda spec,level:[{'kind':k.split(':')[0],'condition':level,'treatment':k.split(':')[1],'n':n,'config':args.config} for k,n in spec.items()]
        doc.update({'mode':'exploration','levels':cfg['levels'],'per_level':cfg['per_level'],'at_highest_level':cfg['at_highest_level'],
            'at_failed_level':{'p2_c_to_n:'+args.best_treatment:cfg['at_failed_level']['best_step1_treatment']},'best_treatment':args.best_treatment,
            'failure_criteria':cfg['failure_criteria'],'rule':cfg['batch_rule'],
            'escalation':'Levels in order; after a level with any flight failure, or after the last level, run at_highest_level at that level; if that level had a flight failure also run at_failed_level there; then stop.'})
        write(out/'plan.json',doc)
        plan=[];failed=False
        for i,level in enumerate(cfg['levels']):
            rows=build_plan(args.prefix,expand(cfg['per_level'],level),tag='per_level');plan+=rows
            failed=execute(plan,out,candidate,exploration=True)
            if failed:break
            level_failed=any(r['flight_failure'] for r in rows)
            if level_failed or i==len(cfg['levels'])-1:
                extra=build_plan(args.prefix,expand(cfg['at_highest_level'],level),tag='at_highest_level')
                if level_failed:extra+=build_plan(args.prefix,expand({'p2_c_to_n:'+args.best_treatment:cfg['at_failed_level']['best_step1_treatment']},level),tag='at_failed_level')
                plan+=extra;failed=execute(plan,out,candidate,exploration=True)
                doc['highest_level']=level;doc['failed_level']=level if level_failed else None;write(out/'plan.json',doc)
                break
    result=summary(plan,candidate,failed);write(out/'results.json',result);print(result['status'],out,flush=True)
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
