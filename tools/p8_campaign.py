#!/usr/bin/env python3
"""P8-B campaigns: 5 methods x 2 systems under test x 3 seeds = 30 campaigns of 30 runs (config/p8.json p8.b).

  p8_campaign.py data/<batch> --state data/<state> --stage b1|b2 [--resume]
  p8_campaign.py data/<batch> --state data/<dev state> --stage dev --campaigns fuzz/T0/0,bo/T1/0 --rounds 1 1 --development

Rotation: the campaigns in the pre-registered order (p8.b.rotation.order) form a ring; round k flies the k-th run of every
campaign (B1 rounds 1-15, B2 rounds 16-30). Offline methods (random, contest, ours) take tools/p8/p8_lists.json
lists["<method>/<sut>/<seed>"] in order; online methods (fuzz, bo) call p8_methods.Fuzz/BO(sut, seed, p8_space.fits)
.propose(history) and get (case, max tilt deg, primary failure) appended after the run. The campaign state (round done,
list position, history, the proposed case, m.rng.bit_generator.state after every propose) is written to
<state>/campaigns/<method>_<sut>_<seed>.json before the run starts, so a restart reuses the proposed case and never redraws.

Before every run: p8_conditions.budget_check -- p8_space.budget(case) must equal the gap_spec fit; otherwise the batch stops
with <batch>/diagnosis.json. Each run: kind p5_gap, condition = the P8 case name, treatment = the system under test,
config/p8.json, its own Gazebo seed; checks and measurement as tools/p8_batch.py (p8_metrics). An infrastructure or
evidence failure is rerun with the same case and a new seed (id suffix -r1, -r2; infra_rerun, not counted); after 2 reruns
the batch stops. Flight failures are results. Every run flown is appended to <state>/runs/p8_b_cases.jsonl. The batch
identity (tools/, research/, config/, Lab, binaries) is re-hashed before every run (IDENTITY_DRIFT stops the batch).
No run starts while a ToDesk remote-desktop session is connected (the orchestrator waits and logs it); the session state at
the start and end of every run is recorded in its row.
"""
import argparse,json,subprocess,sys,time,traceback,copy,hashlib
from pathlib import Path
import p2_batch,p8_conditions,p8_batch
from p2_batch import identity,write,now,host_state,ROOT
from p0_closure import GATE
from p6_batch import seed_of
import p8_space,p8_methods

MAX_RERUNS=2
def remote_session():return bool(subprocess.run(['pgrep','-x','ToDesk_Session'],capture_output=True).stdout.strip())

def wait_host(args):
    """Host rule (p8.b.host_rule): no run starts while a remote-desktop session is connected; the wait is logged."""
    if not remote_session():return 0.
    t=time.monotonic();print('WAIT remote-desktop session connected',now(),flush=True);log_case(args.state,{'event':'wait_remote_desktop'})
    while remote_session():time.sleep(30)
    w=time.monotonic()-t;log_case(args.state,{'event':'wait_end','waited_s':round(w,1)});print('WAIT END',round(w,1),flush=True);return w
ONLINE={'fuzz':p8_methods.Fuzz,'bo':p8_methods.BO}

def campaign_file(state,cid):return state/'campaigns'/(cid.replace('/','_')+'.json')

def load_state(state,cid):
    f=campaign_file(state,cid)
    if f.exists():return json.loads(f.read_text())
    m,s,k=cid.split('/');return {'campaign':cid,'method':m,'sut':s,'seed':int(k),'k_done':0,'next_index':0,'history':[],'rng_state':None,'pending':None,'runs':[],'skipped':[]}

def save_state(state,st):
    f=campaign_file(state,st['campaign']);f.parent.mkdir(parents=True,exist_ok=True);tmp=f.with_suffix('.tmp')
    tmp.write_text(json.dumps(st,indent=1,ensure_ascii=False)+'\n');tmp.replace(f)

def log_case(state,item):
    d=state/'runs';d.mkdir(parents=True,exist_ok=True)
    with (d/'p8_b_cases.jsonl').open('a') as f:f.write(json.dumps({'time':now(),**item},ensure_ascii=False)+'\n')

def propose(st,lists):
    """The case of the campaign's next round (st['k_done']+1); the state is saved by the caller before the run."""
    k=st['k_done']+1
    if st['pending'] and st['pending']['k']==k:return st['pending']
    if st['method'] in ONLINE:
        m=ONLINE[st['method']](st['sut'],st['seed'],p8_conditions.runner_fits)
        if st['rng_state'] is not None:m.rng.bit_generator.state=st['rng_state']
        legacy=ONLINE[st['method']](st['sut'],st['seed'],p8_space.fits)
        legacy.rng.bit_generator.state=copy.deepcopy(m.rng.bit_generator.state)
        hist=[(h[0],h[1],h[2]) for h in st['history']]
        c=m.propose(hist);old=legacy.propose(hist)
        if c!=old or m.rng.bit_generator.state!=legacy.rng.bit_generator.state:
            raise RuntimeError('runner budget changes frozen online proposal or RNG state; continuation refused')
        st['rng_state']=m.rng.bit_generator.state
        st['pending']={'k':k,'case':c,'source':'propose'}
    else:
        lst=lists[st['campaign']];i=st['next_index']
        if i>=len(lst):raise RuntimeError(f"list {st['campaign']} exhausted at round {k}")
        st['pending']={'k':k,'case':lst[i]['case'],'source':'list','list_index':i,'list_name':lst[i]['name']}
    return st['pending']

def run_case(args,cfg,st,pend,rerun,out,candidate,plan):
    sut=st['sut'];cond=p8_conditions.case_condition(pend['case'],sut);k=pend['k']
    rid=f"{st['method']}-{sut}-s{st['seed']}-k{k:02d}"+(f'-r{rerun}' if rerun else '');seed=seed_of(args.prefix,rid,cfg)
    row={'id':rid,'kind':'p5_gap','condition':cond,'treatment':sut,'config':'config/p8.json','repetition':1,'sim_seed':seed,'initial_yaw_deg':None,
         'extra_args':['--sim-seed',str(seed)],'directory':f'data/{args.prefix}-{rid}','status':'NOT_RUN',
         'campaign':st['campaign'],'method':st['method'],'sut':sut,'seed':st['seed'],'k':k,'name':cond+':'+sut,'case':pend['case'],'windows_s':p8_space.windows(pend['case']),
         'infra_rerun':bool(rerun),'stage':args.stage,'budget_check':pend['budget_check']}
    plan.append(row)
    if getattr(args,'revision',None):row['identity_revision']=str(args.revision)
    row['waited_for_host_s']=wait_host(args)
    if identity()!=candidate:row['status']='IDENTITY_DRIFT';return row
    row['remote_desktop_session_at_start']=remote_session()
    log_case(args.state,{'event':'start','campaign':st['campaign'],'k':k,'run_id':rid,'name':row['name'],'windows_s':row['windows_s'],'budget':pend['budget_check'],'sim_seed':seed,'infra_rerun':bool(rerun),'batch':str(out.relative_to(ROOT))})
    print('START',st['campaign'],'k',k,rid,row['name'],'seed',seed,flush=True)
    try:p8_batch.run_row(row,out)
    except Exception as e:row['status']=row.get('status') if row.get('status')!='NOT_RUN' else 'ERROR';row['error']=repr(e);row['accepted']=False;row['flight_failure']=False;traceback.print_exc()
    row['remote_desktop_session_at_end']=remote_session()
    log_case(args.state,{'event':'end','campaign':st['campaign'],'k':k,'run_id':rid,'name':row['name'],'status':row.get('status'),'accepted':row.get('accepted'),'flight_failure':row.get('flight_failure'),
             'fail_primary':row.get('fail_primary'),'fail_task':row.get('fail_task'),'max_tilt_deg':row.get('max_tilt_deg'),'max_altitude_loss_m':row.get('max_altitude_loss_m'),'infra_rerun':bool(rerun)})
    print('END',rid,row.get('status'),'accepted='+str(row.get('accepted')),'flight_failure='+str(row.get('flight_failure')),'tilt='+str(row.get('max_tilt_deg')),'alt_loss='+str(row.get('max_altitude_loss_m')),flush=True)
    return row

def stop(out,plan,reason,**info):
    write(out/'diagnosis.json',{'created_at':now(),'reason':reason,**info,'note':'batch stopped by the pre-registered rule; nothing re-run in place; the user decides how to continue'})
    print('STOP',reason,flush=True);return True

def execute(args,cfg,out,candidate,plan,order,rounds):
    lists=json.loads((ROOT/'tools/p8/p8_lists.json').read_text())['lists']
    for k in range(rounds[0],rounds[1]+1):
        for cid in order:
            st=load_state(args.state,cid)
            if st['k_done']>=k:continue
            if st['k_done']!=k-1:return stop(out,plan,'campaign out of step',campaign=cid,k_done=st['k_done'],round=k)
            try:pend=propose(st,lists)
            except Exception as e:return stop(out,plan,'proposal rejected',campaign=cid,round=k,error=repr(e))
            chk=p8_conditions.budget_check(cfg,pend['case'],st['sut']);pend['budget_check']=chk;save_state(args.state,st)
            if not chk['equal']:return stop(out,plan,'authoritative generation budget differs from execution spec',campaign=cid,round=k,case=pend['case'],budget_check=chk)
            if chk['gap_spec'] is None:
                # Reject without changing the frozen list position or pending case.
                if st['method'] in ONLINE:return stop(out,plan,'online method proposed a case outside the budget',campaign=cid,round=k,case=pend['case'])
                return stop(out,plan,'unexpected cancelled list case; state retained without skipping',campaign=cid,round=k,case=pend['case'])
            for rerun in range(MAX_RERUNS+1):
                row=run_case(args,cfg,st,pend,rerun,out,candidate,plan);write(out/'results.json',{'runs':plan,'complete':False})
                if row['status']=='IDENTITY_DRIFT':return stop(out,plan,'IDENTITY_DRIFT',run=row['id'])
                if row.get('accepted') or row.get('flight_failure'):break
                if args.development:break
            else:return stop(out,plan,f'infrastructure or evidence failure after {MAX_RERUNS} reruns',campaign=cid,round=k,runs=[r['id'] for r in plan[-(MAX_RERUNS+1):]])
            if not (row.get('accepted') or row.get('flight_failure')):
                st['runs'].append({'k':k,'id':row['id'],'status':'DEVELOPMENT_FAILED'});save_state(args.state,st);continue
            res={'k':k,'id':row['id'],'name':row['name'],'case':pend['case'],'fail_primary':bool(row['flight_failure']),'fail_task':row.get('fail_task'),
                 'max_tilt_deg':row.get('max_tilt_deg'),'max_altitude_loss_m':row.get('max_altitude_loss_m'),'cell':list(p8_space.cell(pend['case'])),
                 'infra_reruns':[r['id'] for r in plan if r.get('campaign')==cid and r.get('k')==k and r['id']!=row['id']],'list_index':pend.get('list_index')}
            if st['method'] in ONLINE:st['history'].append([pend['case'],float(row['max_tilt_deg']),bool(row['flight_failure'])])
            else:st['next_index']=pend['list_index']+1
            st['runs'].append(res);st['k_done']=k;st['pending']=None;save_state(args.state,st)
    return False

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--state',type=Path,required=True)
    p.add_argument('--stage',required=True,choices=['dev','b1','b2']);p.add_argument('--prefix',default='p8-20261022-b')
    p.add_argument('--campaigns',help='dev only: comma-separated campaign ids');p.add_argument('--rounds',nargs=2,type=int,help='dev only: first and last round')
    p.add_argument('--resume',action='store_true',help='continue an interrupted batch directory on the same candidate');p.add_argument('--purpose',default='')
    p.add_argument('--revision',type=Path,help='explicit user-approved identity amendment for resume; original candidate retained')
    p.add_argument('--development',action='store_true',help='development only: never results')
    args=p.parse_args();out=args.output.resolve();args.state=args.state.resolve();cfg=json.loads((ROOT/'config/p8.json').read_text());b=cfg['p8']['b']
    order=b['rotation']['order'];rounds={'b1':(1,b['b1_rounds']),'b2':(b['b1_rounds']+1,b['rounds'])}.get(args.stage)
    if args.stage=='dev':
        if not args.development or not args.campaigns or not args.rounds:p.error('dev needs --development --campaigns --rounds')
        order=[c for c in order if c in args.campaigns.split(',')];rounds=tuple(args.rounds)
    elif args.development:p.error('b1/b2 are never development')
    if args.resume:
        candidate=json.loads((out/'candidate.json').read_text());plan=json.loads((out/'results.json').read_text())['runs']
        if args.revision:
            rev=json.loads(args.revision.read_text())
            if rev['original_candidate']!=candidate:raise SystemExit('revision original candidate differs')
            n=rev['preserved_runs']
            if len(plan)<n or rows_sha(plan[:n])!=rev['preserved_rows_sha256']:raise SystemExit('preserved results changed')
            candidate=rev['revised_candidate']
        if identity()!=candidate:raise SystemExit('candidate changed; resume refused')
        doc=json.loads((out/'plan.json').read_text());doc.setdefault('resumed_at',[]).append(now());write(out/'plan.json',doc)
    else:
        out.mkdir(parents=True,exist_ok=False);candidate=identity();write(out/'candidate.json',candidate);write(out/'host.json',host_state());plan=[]
        if args.stage=='b2':
            for cid in order:
                st=load_state(args.state,cid)
                if st['k_done']!=b['b1_rounds']:raise SystemExit(f'B1 not complete for {cid}: k_done {st["k_done"]}')
        write(out/'plan.json',{'created_at':now(),'stage':args.stage,'purpose':args.purpose,'config':'config/p8.json','state':str(args.state.relative_to(ROOT)),'prefix':args.prefix,
            'rounds':list(rounds),'order':order,'output_chain_gate':GATE,'candidate':'candidate.json','mode':'development' if args.development else 'standard',
            'rules':{k:b[k] for k in ['methods','rotation','budget_check','infrastructure_rule','cases_log','run_ids']},'criteria':cfg['p8']['criteria'],'flight_failures':cfg['p5']['failure_criteria'],
            'independence':cfg['p4']['independence']})
    failed=execute(args,cfg,out,candidate,plan,order,rounds)
    result=p2_batch.summary(plan,candidate,failed)
    result.update({'stage':args.stage,'rounds':list(rounds),'infra_reruns':[r['id'] for r in plan if r.get('infra_rerun')],
                   'complete':bool(not failed and all(load_state(args.state,c)['k_done']>=rounds[1] for c in order))})
    if args.revision:result['identity_revision']={'file':str(args.revision.relative_to(ROOT) if args.revision.is_absolute() else args.revision),'preserved_runs':rev['preserved_runs'],'original_candidate_retained':True}
    if args.development:result['status']='DEVELOPMENT'
    write(out/'results.json',result);print(result['status'],out,flush=True)
    return 1 if failed else 0
def rows_sha(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()

if __name__=='__main__':raise SystemExit(main())
