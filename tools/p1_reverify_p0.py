#!/usr/bin/env python3
"""Re-verify the frozen P0 batch-05 flights after the P1 analysis change; never edits the raw runs.

For every flight two separate reanalyses are made with tools/reanalyze_p0.py:
  p0rule      unchanged P0 config -> metrics.json must equal the recorded one exactly (code path unchanged);
  controller  joint_recovery.position_reference='active_controller_target' (P1 rule) -> verdict and recovery
              stages compared with the recorded P0 result.
"""
import argparse,hashlib,json,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BATCH=ROOT/'data/preparation-20261011/batch-05'

def load(p):return json.loads(p.read_text())
def reanalyze(raw,out,reference=None):
    cmd=[sys.executable,str(ROOT/'tools/reanalyze_p0.py'),str(raw),str(out)]+(['--position-reference',reference] if reference else [])
    return subprocess.run(cmd,capture_output=True,text=True).returncode

def stages(m):return [(s['owner'],s['joint_recovery']['status'],s['joint_recovery']['time_s']) for s in m.get('recovery_stages',[])]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--jobs',type=int,default=6);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    runs=[r for r in load(BATCH/'results.json')['runs'] if not r['startup_only']]
    jobs=[]
    for r in runs:
        raw=ROOT/r['directory']
        jobs+=[(r,raw,out/(raw.name+'-p0rule'),None),(r,raw,out/(raw.name+'-controller'),'active_controller_target')]
    with ThreadPoolExecutor(a.jobs) as pool:codes=list(pool.map(lambda j:reanalyze(j[1],j[2],j[3]),jobs))
    rows=[]
    for (r,raw,dst,ref),code in zip(jobs,codes):
        old=load(raw/'metrics.json');new=load(dst/'metrics.json') if (dst/'metrics.json').exists() else {}
        row={'run':str(raw.relative_to(ROOT)),'kind':r['kind'],'mode':'controller' if ref else 'p0rule','exit_code':code,
             'recorded_status':old.get('status'),'status':new.get('status'),'recovery_status':new.get('recovery_status')}
        if ref:
            row['recorded_stages']=stages(old);row['stages']=stages(new)
            row['stage_statuses_equal']=[s[1] for s in stages(old)]==[s[1] for s in stages(new)]
            row['max_time_change_s']=max((abs((x[2] or 0)-(y[2] or 0)) for x,y in zip(stages(old),stages(new))),default=0)
            row['raptor_captures']=len(new.get('controller_target',{}).get('raptor_captures',[]))
            row['neural_intervals']=len(new.get('controller_target',{}).get('neural_intervals_us',[]))
        else:row['metrics_identical']=old==new
        rows.append(row)
    p0=[r for r in rows if r['mode']=='p0rule'];ct=[r for r in rows if r['mode']=='controller']
    summary={'batch':str(BATCH.relative_to(ROOT)),'flights':len(runs),
        'code_sha256':{n:hashlib.sha256((ROOT/'tools'/n).read_bytes()).hexdigest() for n in ['analyze.py','p0_metrics.py','recovery.py','reanalyze_p0.py','p1_reverify_p0.py']},
        'p0rule':{'all_metrics_identical':all(r['metrics_identical'] for r in p0),'identical':sum(r['metrics_identical'] for r in p0)},
        'controller':{'all_pass':all(r['status'] in ['PASS','PASS_WITH_WARNINGS'] for r in ct),
            'all_stage_statuses_equal':all(r['stage_statuses_equal'] for r in ct),
            'every_neural_interval_has_capture':all(r['raptor_captures']>=r['neural_intervals'] for r in ct),
            'max_recovery_time_change_s':max(r['max_time_change_s'] for r in ct)},
        'runs':rows}
    summary['passed']=summary['p0rule']['all_metrics_identical'] and summary['controller']['all_pass'] and summary['controller']['all_stage_statuses_equal']
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:summary[k] for k in ['p0rule','controller','passed']}));return 0 if summary['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
