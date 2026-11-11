"""Sequential independent exploration, retained attempts, resumable ledger."""
import json,sys,subprocess,time,hashlib,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from handover_100.design import CASES
from cn_single.runner import append
from pyulog import ULog
BATCH=ROOT/'data/handover-100-20261110'
def load(p,default=None):return json.loads(p.read_text()) if p.exists() else default

def observed(path):
    result=load(path/'result.json',{})
    flight=path/'flight';events=[json.loads(x) for x in (flight/'events.jsonl').read_text().splitlines()] if (flight/'events.jsonl').exists() else []
    requests=[e for e in events if e['event']=='handover_requested' and e.get('subject')]
    res=dict(attempt=path.name,case=result.get('case'),execution_status=result.get('execution_status','UNFINISHED'),reason=result.get('reason'),subject_requests=len(requests),actual_subject_boundaries=0,request_details=requests)
    if (flight/'flight.ulg').exists():
        try:
            u=ULog(str(flight/'flight.ulg'),message_name_filter_list=['research_actuator'])
            z=next(v.data for v in u.data_list if v.name=='research_actuator' and v.multi_id==0)
            owners=z['owner'];times=z['timestamp'];switches=[dict(time_us=int(times[i]),owner=int(owners[i])) for i in range(1,len(owners)) if owners[i]!=owners[i-1] and owners[i] in [1,2]]
            # Match ordered subject requests; cleanup switch is not counted.
            prev=0;matches=[]
            for e in requests:
                lower=e.get('end_bound_px4_us',0);target=1 if e['to_controller']=='N' else 2
                hit=next((v for v in switches if v['time_us']>=max(lower,prev) and v['owner']==target),None)
                if hit:matches.append(hit);prev=hit['time_us']+1
            res['actual_subject_boundaries']=len(matches);res['boundaries']=matches
            res['ulog_sha256']=hashlib.sha256((flight/'flight.ulg').read_bytes()).hexdigest()
        except Exception as ex:res['evidence_error']=repr(ex)
    return res

def main():
    progress=[];state=BATCH/'batch-progress.json'
    for case in CASES:
        old=sorted(BATCH.glob(case+'-a*'))
        observations=[observed(p) for p in old if p.is_dir()]
        good=[r for r in observations if r['actual_subject_boundaries']>0]
        if good:
            progress.append(good[-1]);continue
        attempt='a'+str(len(observations)+1)
        cmd=[str(ROOT/'tools/handover_100/experiment'),'--case',case,'--attempt',attempt,'--execute']
        print('START',case,attempt,flush=True)
        log=BATCH/(case+'-'+attempt+'-console.log')
        with log.open('x') as f:rc=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT).returncode
        result=observed(BATCH/(case+'-'+attempt));result['runner_exit_code']=rc
        append(BATCH/'orchestrator.jsonl',dict(event='ATTEMPT_RETURNED',time_ns=time.time_ns(),**result))
        progress.append(result)
        state.write_text(json.dumps({'updated_ns':time.time_ns(),'visited_conditions':len(progress),'actual_handover_conditions':sum(r['actual_subject_boundaries']>0 for r in progress),'planned_conditions':100,'runs':progress},ensure_ascii=False,indent=2)+'\n')
        print('END',case,result['execution_status'],'actual_boundaries',result['actual_subject_boundaries'],result.get('reason'),flush=True)
        if rc==2:raise RuntimeError('owned physical cleanup uncertain; inspect before next start')
    print('BATCH_PASS_FINISHED',sum(r['actual_subject_boundaries']>0 for r in progress),'of 100 have handovers',flush=True)
if __name__=='__main__':main()
