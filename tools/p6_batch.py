#!/usr/bin/env python3
"""Pre-register and run a frozen P6 batch on one candidate (config/p6.json; P5 batch rules).

Stages (groups pre-registered in config p4.groups, rules in config p6):
  dev, equivalence, a     groups as listed; repetitions interleave the groups (P5 order)
  b1, c                   groups as listed, one shuffled list (random.Random(p6.b.b1.order_seed / p6.c.order_seed))
  b2 --source <b1>        adaptive refinement (p6.b.b2.rule): per family the midpoint of the success->failure bracket,
                          then bisection on each result until <= 0.05 s, at most 3 runs per family
  b3 --source <b1> <b2>   last success and first failure of the 2.0 m/s families T0 / T1a3 / T1a1.5, 2 new seeds each
Every run gets its own Gazebo seed (first 31 bits of sha256(prefix/run id/master seed)), written to plan.json before it
runs. Checks after each run: the P2 checks (execution and analyzer verdict, PX4 exit, crash markers, preparation trace,
per-motor output-chain gate), then p6_metrics (config with a p6 section) or the frozen p5_metrics (config/p5.json,
equivalence). Pre-registered flight failures (p5_gap) and identification outcomes (IDENT_EXCEEDED_45, IDENT_ABORTED) with
sound infrastructure and complete measurement are results; any other failed check stops the batch, the remaining runs
stay NOT_RUN, nothing is re-run in place.
"""
import argparse,hashlib,json,random,subprocess
from pathlib import Path
import p2_batch,p6_conditions
from p2_batch import identity,write,now,host_state,PY,ROOT
from p0_closure import GATE

def condition_spec(cfg,kind,condition):
    if kind=='p5_gap':return cfg['p5']['conditions'].get(condition) or p6_conditions.gap_spec(cfg,condition)
    if kind=='p6_ident':return cfg['p6']['ident']['conditions'][condition]
    return cfg['p2']['conditions'][condition]

def seed_of(prefix,rid,cfg):
    h=hashlib.sha256(f"{prefix}/{rid}/{cfg['p4']['independence']['master_seed']}".encode()).digest();return int.from_bytes(h[:4],'big')&0x7fffffff

def make_row(prefix,kind,condition,treatment,config,rep):
    cfg=json.loads((ROOT/config).read_text());spec=condition_spec(cfg,kind,condition)
    if spec is None or spec.get('cancelled'):raise RuntimeError(f'condition {condition} unknown or cancelled')
    rid=f'{condition}-{treatment}-{rep}';seed=seed_of(prefix,rid,cfg);yaw=spec.get('initial_yaw_deg')
    return {'id':rid,'kind':kind,'condition':condition,'treatment':treatment,'config':config,'repetition':rep,'sim_seed':seed,'initial_yaw_deg':yaw,
            'extra_args':['--sim-seed',str(seed)]+(['--initial-yaw-deg',str(yaw)] if yaw is not None else []),'directory':f'data/{prefix}-{rid}','status':'NOT_RUN'}

def build_plan(prefix,groups,order_seed=None):
    plan=[]
    for rep in range(1,max(g['n'] for g in groups)+1):
        for g in groups:
            if rep<=g['n']:plan.append(make_row(prefix,g['kind'],g['condition'],g['treatment'],g['config'],rep))
    if order_seed is not None:random.Random(order_seed).shuffle(plan)
    if len({r['id'] for r in plan})!=len(plan) or len({r['sim_seed'] for r in plan})!=len(plan):raise RuntimeError('run id or seed collision in plan')
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
    name,tool,filename=('p6','p6_metrics.py','p6-metrics.json') if 'p6' in cfg else ('p5','p5_metrics.py','p5-metrics.json')
    if have:
        m=metric(row,out,name,tool,filename)
        if row['kind']=='p5_gap':
            fo=m.get('flight_outcome') or {};row['flight_outcome']=fo.get('outcome');row['flight_failure_reasons']=fo.get('reasons')
            row['checks']['subject_measured']=bool(m.get('status')=='MEASURED' and fo.get('outcome')=='SUCCESS')
        else:
            io=m.get('ident_outcome') or {};row['ident_outcome']=io.get('class');row['ident_exceeded_45']=io.get('ident_exceeded_45')
    else:row['checks'][name+'_measured']=False
    infra=[k for k in row['checks'] if k not in ['execution','subject_measured']]
    row['infrastructure_ok']=all(row['checks'][k] for k in infra)
    if row['kind']=='p6_ident':
        # Identification outcomes are results; a runner safety abort ends execution early but is measured and exported.
        row['flight_failure']=False
        row['accepted']=bool(row['infrastructure_ok'] and row.get('ident_outcome') in ['IDENT_OK','IDENT_EXCEEDED_45','IDENT_ABORTED']
                             and (row['checks']['execution'] or row.get('ident_outcome')=='IDENT_ABORTED'))
    else:
        row['flight_failure']=bool(row['infrastructure_ok'] and row.get('flight_outcome')=='FAILURE')
        row['accepted']=all(row['checks'].values()) and not row['flight_failure']
    return row

def run_and_check(row,plan,out,candidate,development):
    """Run one row; True when the batch must stop."""
    if identity()!=candidate:row['status']='IDENTITY_DRIFT';return True
    print('START',row['id'],'seed',row['sim_seed'],flush=True)
    run_row(row,out);write(out/'results.json',{'runs':plan,'complete':False})
    print('END',row['id'],row['status'],'accepted='+str(row['accepted']),'flight_failure='+str(row['flight_failure']),'outcome='+str(row.get('flight_outcome') or row.get('ident_outcome')),flush=True)
    return not row['accepted'] and not row['flight_failure'] and not development

def execute(plan,out,candidate,development=False):
    for row in plan:
        if row['status']!='NOT_RUN':continue
        if run_and_check(row,plan,out,candidate,development):return True
    return False

# ---- B2 / B3 ----------------------------------------------------------------------------------------------------------
def gap_D(row):
    m=p6_conditions.GAP_NAME.match(row['condition']);return (float(m['v']),float(m['D']),m['axis']) if m else (None,None,None)

def family_points(rows,treatment,speed,axis='A0'):
    """(D, outcome) of the completed p5_gap runs of one family (accepted successes and pre-registered flight failures)."""
    pts=[]
    for r in rows:
        if r.get('kind')!='p5_gap' or r.get('treatment')!=treatment or r.get('status')=='NOT_RUN':continue
        v,D,ax=gap_D(r)
        if v!=speed or ax!=axis:continue
        if r.get('accepted'):pts.append((D,'S'))
        elif r.get('flight_failure'):pts.append((D,'F'))
    return sorted(pts)

def bracket(pts,width=0.05):
    """Pre-registered B2 decision: (next D or None, state, last success, first failure)."""
    seq=''.join(o for _,o in pts);S=[D for D,o in pts if o=='S'];F=[D for D,o in pts if o=='F']
    if 'S' in seq[seq.find('F'):] and 'F' in seq:return None,'non_monotone',(max(S) if S else None),(min(F) if F else None)
    if not S or not F:return None,('all_success' if S else 'all_failure'),(max(S) if S else None),(min(F) if F else None)
    ls,ff=max(S),min(F)
    if ff-ls<=width+1e-9:return None,'bracketed',ls,ff
    return round((ls+ff)/2,4),'refine',ls,ff

def source_rows(paths):
    rows=[]
    for p in paths:rows+=[dict(r,source_batch=str(Path(p).resolve().relative_to(ROOT))) for r in json.loads((Path(p)/'results.json').read_text())['runs']]
    return rows

def stage_b2(prefix,cfg,config,sources,out,candidate,development,plan,log):
    b=cfg['p6']['b'];rule=b['b2'];rows=source_rows(sources)
    if not all(r['status']!='NOT_RUN' for r in rows):raise RuntimeError('B1 not complete')
    for f in b['families']:
        for v in f['speeds_m_s']:
            key=f"{f['treatment']}@{p6_conditions.fmt(v)}";pts=family_points(rows,f['treatment'],v,b['axis']);entry={'family':key,'b1_points':pts,'added':[]}
            log.append(entry)
            for k in range(rule['max_runs_per_family']):
                D,state,ls,ff=bracket(pts,rule['bracket_s']);entry.update({'state':state,'last_success_D_s':ls,'first_failure_D_s':ff})
                if D is None:break
                row=make_row(prefix,'p5_gap',p6_conditions.gap_name(v,D,b['axis']),f['treatment'],config,1);plan.append(row)
                write(out/'refinement.json',{'rule':rule['rule'],'families':log})
                if run_and_check(row,plan,out,candidate,development):return True
                o='S' if row['accepted'] else ('F' if row['flight_failure'] else None)
                entry['added'].append({'D_s':D,'id':row['id'],'outcome':o})
                if o is None:break
                pts=sorted(pts+[(D,o)])
            else:
                D,state,ls,ff=bracket(pts,rule['bracket_s']);entry.update({'state':state if D is None else 'max_runs_reached','last_success_D_s':ls,'first_failure_D_s':ff})
            entry['final_points']=pts;write(out/'refinement.json',{'rule':rule['rule'],'families':log})
    return False

def b3_plan(prefix,cfg,config,sources):
    b=cfg['p6']['b'];rows=source_rows(sources);plan=[];chosen=[]
    for t,v in b['b3']['families']:
        pts=family_points(rows,t,float(v),b['axis']);_,state,ls,ff=bracket(pts,b['b2']['bracket_s'])
        chosen.append({'family':f'{t}@{p6_conditions.fmt(v)}','points':pts,'state':state,'last_success_D_s':ls,'first_failure_D_s':ff})
        for D in [x for x in [ls,ff] if x is not None]:
            for rep in range(1,b['b3']['repetitions']+1):plan.append(make_row(prefix,'p5_gap',p6_conditions.gap_name(float(v),D,b['axis']),t,config,rep))
    return plan,chosen

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--prefix',required=True)
    p.add_argument('--stage',required=True,choices=['dev','equivalence','a','b1','b2','b3','c']);p.add_argument('--config',default='config/p6.json')
    p.add_argument('--source',nargs='*',default=[],help='b2: the B1 batch; b3: the B1 and B2 batches');p.add_argument('--purpose',required=True)
    p.add_argument('--development',action='store_true',help='development only: record failed checks and continue; never an acceptance result')
    args=p.parse_args();out=args.output.resolve();cfg=json.loads((ROOT/args.config).read_text())
    extra={};groups=None
    if args.stage in ['dev','equivalence','a','b1','c']:
        groups=p2_batch.parse_groups(cfg['p4']['groups'][args.stage],args.config)
        seed={'b1':cfg['p6']['b']['b1']['order_seed'],'c':cfg['p6']['c']['order_seed']}.get(args.stage)
        plan=build_plan(args.prefix,groups,seed);extra['order']=f'shuffled with random.Random({seed})' if seed is not None else 'repetitions interleave the groups'
    elif args.stage=='b2':
        if len(args.source)!=1:p.error('b2 needs --source <B1 batch>')
        plan=[];extra.update({'order':'adaptive: families in config order, bisection runs appended as decided','rule':cfg['p6']['b']['b2'],'sources':args.source})
    else:
        if not args.source:p.error('b3 needs --source <B1> <B2>')
        plan,chosen=b3_plan(args.prefix,cfg,args.config,args.source);extra.update({'order':'family order, last success then first failure, 2 repetitions','rule':cfg['p6']['b']['b3'],'sources':args.source,'chosen':chosen})
    out.mkdir(parents=True,exist_ok=False)
    candidate=identity();write(out/'candidate.json',candidate);write(out/'host.json',host_state())
    doc={'created_at':now(),'stage':args.stage,'host':cfg['p4']['host'],'purpose':args.purpose,'config':args.config,'output_chain_gate':GATE,'candidate':'candidate.json',
        'mode':'development' if args.development else 'standard','groups':groups,**extra,'independence':cfg['p4']['independence'],
        'flight_failures':cfg['p5']['failure_criteria'],'ident_outcomes':cfg['p6']['ident']['outcome'] if 'p6' in cfg else None,
        'stop_rule':'Pre-registered flight failures and identification outcomes with every infrastructure and evidence check passing are results and do not stop the batch; any other failed check stops it. Remaining runs stay NOT_RUN; nothing is re-run in place.',
        'runs':[{k:r[k] for k in ['id','kind','condition','treatment','config','repetition','sim_seed','initial_yaw_deg','directory']} for r in plan]}
    write(out/'plan.json',doc)
    if args.stage=='b2':
        log=[];failed=stage_b2(args.prefix,cfg,args.config,args.source,out,candidate,args.development,plan,log)
        doc['runs']=[{k:r[k] for k in ['id','kind','condition','treatment','config','repetition','sim_seed','initial_yaw_deg','directory']} for r in plan];doc['refinement']='refinement.json';write(out/'plan.json',doc)
    else:failed=execute(plan,out,candidate,args.development)
    result=p2_batch.summary(plan,candidate,failed)
    result['identification_outcomes']={r['id']:r.get('ident_outcome') for r in plan if r['kind']=='p6_ident'}
    if args.development:result.update({'status':'DEVELOPMENT','failed_checks':{r['id']:[k for k,v in r['checks'].items() if not v] for r in plan if 'checks' in r}})
    write(out/'results.json',result);print(result['status'],out,flush=True)
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
