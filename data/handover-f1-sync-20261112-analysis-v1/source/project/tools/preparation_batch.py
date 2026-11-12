#!/usr/bin/env python3
"""Pre-register and run a bounded preparation batch; retain failures and stop for diagnosis."""
import argparse,datetime,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
KINDS=['classic_hover','raptor_hover','repeated_handover','state_reset','state_hold','state_restore','state_injection']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def identity():
    result={'project_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'lab':{},
        'files':{str(p.relative_to(ROOT)):sha(p) for folder in ['tools','research','config'] for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in str(p)}}
    for v,target in [('classic','px4_sitl_default'),('raptor','px4_sitl_raptor')]:
        s=ROOT/'uav_lab/.local/checkouts'/('px4-'+v)
        untracked=subprocess.check_output(['git','-C',str(s),'ls-files','--others','--exclude-standard','-z']).decode().strip('\0').split('\0')
        result['lab'][v]={'binary_sha256':sha(s/'build'/target/'bin/px4'),
            'diff_sha256':hashlib.sha256(subprocess.check_output(['git','-C',str(s),'diff','--binary'])).hexdigest(),
            'untracked':{n:sha(s/n) for n in untracked if n and (s/n).is_file()}}
    result['policy_sha256']=sha(ROOT/'uav_lab/.local/checkouts/px4-raptor/src/modules/mc_raptor/blob/policy.tar')
    plugin=ROOT/'uav_lab/.local/checkouts/px4-raptor/build/px4_sitl_raptor/src/modules/simulation/gz_plugins/libResearchMulticopterMotorModel.so'
    if plugin.exists():result['gz_research_plugin_sha256']=sha(plugin)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--prefix',required=True);p.add_argument('--startup-count',type=int,default=20);p.add_argument('--flight-repetitions',type=int,default=3);args=p.parse_args()
    if args.startup_count<0 or args.flight_repetitions<0 or args.startup_count+args.flight_repetitions==0:p.error('counts must be nonnegative')
    args.output.mkdir(parents=True,exist_ok=False)
    candidate=identity();write(args.output/'candidate.json',candidate)
    plan=[]
    for i in range(args.startup_count):
        kind='classic_hover' if i%2==0 else 'raptor_hover'
        plan.append({'id':f'startup-{i+1:02d}','kind':kind,'startup_only':True})
    for cycle in range(1,args.flight_repetitions+1):
        for kind in KINDS:plan.append({'id':f'flight-{cycle}-{kind}','kind':kind,'startup_only':False})
    for row in plan:row['directory']='data/'+args.prefix+'-'+row['id'];row['status']='NOT_RUN'
    write(args.output/'plan.json',{'created_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'purpose':'Preparation engineering screen, not formal state comparison or reliability certification.',
        'latency_target_ms':4,'latency_hard_gate_added':False,'output_chain_trace':'gz_research_plugin_sha256' in candidate,'stop_rule':'Any failure stops this candidate for diagnosis. Remaining runs remain NOT_RUN.', 'runs':plan})
    failed=False
    for row in plan:
        if identity()!=candidate:
            row['status']='IDENTITY_DRIFT';failed=True;break
        command=[str(ROOT/'tools/experiment'),row['kind'],'--output',str(ROOT/row['directory'])]
        if row['startup_only']:command.append('--startup-only')
        print('START',row['id'],flush=True)
        with (args.output/(row['id']+'.log')).open('w') as log:
            code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        run=ROOT/row['directory'];row['exit_code']=code
        validation=json.loads((run/'validation.json').read_text()) if (run/'validation.json').exists() else {}
        row['status']=validation.get('status','FAIL');row['reason']=validation.get('reason')
        if not row['startup_only'] and row['kind']!='classic_hover' and (run/'flight.ulg').exists():
            trace=subprocess.run([str(ROOT/'uav_lab/.local/venv/bin/python'),str(ROOT/'tools/preparation_trace.py'),str(run)],capture_output=True,text=True)
            (args.output/(row['id']+'-trace.log')).write_text(trace.stdout+trace.stderr)
            row['trace_exit_code']=trace.returncode
            chain=subprocess.run([str(ROOT/'uav_lab/.local/venv/bin/python'),str(ROOT/'tools/output_chain.py'),str(run)],capture_output=True,text=True)
            (args.output/(row['id']+'-output-chain.log')).write_text(chain.stdout+chain.stderr)
            row['output_chain_exit_code']=chain.returncode
        stops=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines() if json.loads(s)['event']=='process_stopped'] if (run/'events.jsonl').exists() else []
        row['px4_exit_codes']=[e['exit_code'] for e in stops if e['name']=='px4']
        row['accepted']=code==0 and row['status'] in ['PASS','PASS_WITH_WARNINGS'] and row['px4_exit_codes']==[0]
        if not row['startup_only'] and row['kind']!='classic_hover':
            row['accepted'] &= row.get('trace_exit_code')==0 and (run/'preparation-trace.json').exists() and json.loads((run/'preparation-trace.json').read_text())['status']=='MEASURED'
            # Output-chain trace is required only when this candidate provides the research motor model.
            if 'gz_research_plugin_sha256' in candidate:row['accepted'] &= row.get('output_chain_exit_code')==0
        write(args.output/'results.json',{'runs':plan,'complete':False})
        print('END',row['id'],row['status'],'accepted='+str(row['accepted']),flush=True)
        if not row['accepted']:failed=True;break
    result={'status':'FAIL' if failed else 'PASS','complete':not failed,'p0_complete':False,
        'note':'This batch does not close historical P0 issues or prove Gazebo motor physics consumption.',
        'accepted':sum(bool(r.get('accepted')) for r in plan),'failed':sum('exit_code' in r and not r.get('accepted') for r in plan),
        'not_run':sum(r['status']=='NOT_RUN' for r in plan),'candidate_unchanged':identity()==candidate,'runs':plan}
    write(args.output/'results.json',result);print(result['status'],args.output,flush=True)
    return int(failed)
if __name__=='__main__':raise SystemExit(main())
