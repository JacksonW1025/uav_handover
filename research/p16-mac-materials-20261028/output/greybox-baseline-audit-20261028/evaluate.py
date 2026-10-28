import json,copy,time,hashlib,concurrent.futures,numpy as np
from core import ROOT,OLD,reference,forecast,sanitize
RAW=ROOT.parent/'offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json'

def score(pred,raw,group_map=False):
    rr=[]
    for p in pred:
        r=raw[p['id']];rr.append(dict(**p,actual=float(r['LP_max_loss_m']),actual_tilt=float(r['LP_peak_tilt_deg']),censored=bool(r['censored']),task_failure=r['task']=='FAILURE'))
    if group_map:
        for fam in ['F2','F4']:
            for arm in ['AB-short','AB-medium','AB-long']:
                group=[r for r in rr if r['family']==fam and r['arm']==arm]
                ph=float(np.mean([r['prediction'] for r in group]));pt=float(np.mean([r['predicted_tilt'] for r in group]));pf=float(np.mean([r['prediction']>1 or r['predicted_tilt']>45 for r in group]))
                for r in group:r['prediction']=ph;r['predicted_tilt']=pt;r['map_failure']=pf>.5
    for r in rr:r['predicted_task']=r.get('map_failure',r['prediction']>1 or r['predicted_tilt']>45)
    complete=[r for r in rr if not r['censored']];pos=[r for r in rr if r['task_failure']];neg=[r for r in rr if not r['task_failure']]
    m=dict(n=len(rr),task_correct=sum(r['task_failure']==r['predicted_task'] for r in rr),task_FN=sum(not r['predicted_task'] for r in pos),task_FP=sum(r['predicted_task'] for r in neg),
      complete_n=len(complete),height_MAE=float(np.mean([abs(r['prediction']-r['actual']) for r in complete])),tilt_MAE=float(np.mean([abs(r['predicted_tilt']-r['actual_tilt']) for r in complete])),
      witnessed_tilt_FN=sum(r['predicted_tilt']<=45 for r in rr if r['actual_tilt']>45),known_tilt_FP=sum(r['predicted_tilt']>45 for r in complete if r['actual_tilt']<=45),
      height_FN=sum(r['prediction']<=1 for r in rr if r['actual']>1),height_FP=sum(r['prediction']>1 for r in complete if r['actual']<=1),domain_exits=sum(r['stop'] is not None for r in rr))
    choices=[]
    for block in [1,2,3]:
        pool=[r for r in rr if r['block']==block]
        for outcome in ['prediction','predicted_tilt']:
            r=max(pool,key=lambda r:r[outcome]);choices.append(dict(block=block,target=outcome,id=r['id'],task_failure=r['task_failure'],actual_height=r['actual'],actual_tilt=r['actual_tilt'],censored=r['censored']))
    return dict(metrics=m,choices=choices,rows=rr)

def job(x):
    name,scope,inp,m,variant=x;t=time.perf_counter();p,z,seam=forecast(inp,m,variant)
    return name,scope,p,time.perf_counter()-t

def main():
    t=time.perf_counter();fitted=json.loads((ROOT/'models.json').read_text());rows=json.loads(RAW.read_text())['rows'];raw={r['id']:r for r in rows};cases=sorted([r for r in rows if r['branch']=='AB'],key=lambda r:r['id'])
    models={'ordinary_EE':(fitted['equation_error'],'full'),'ordinary_OE':(fitted['output_error'],'full')}
    for a in ['hold_target','no_carry','hold_target_no_carry','no_neural_carry','no_physical_carry']:models[a]=(fitted['equation_error'],a)
    jobs=[];cache={};details=[]
    for scope in ['case_initial','normal_template']:
        for name,(m,v) in models.items():
            cache[(name,scope)]=[]
            for r in cases:
                inp=sanitize(r)
                if scope=='normal_template':inp['initial']=copy.deepcopy(next(z['initial'] for z in rows if z['family']==r['family'] and z['block']==r['block'] and z['branch']=='NORMAL'))
                jobs.append((name,scope,inp,m,v))
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
        for name,scope,p,elapsed in pool.map(job,jobs):
            cache[(name,scope)].append(p)
            print(name,scope,p['id'],round(p['prediction'],4),round(p['predicted_tilt'],3),p['stop'],flush=True)
            (ROOT/'progress.json').write_text(json.dumps(dict(completed=sum(map(len,cache.values())),total=len(jobs),elapsed_s=time.perf_counter()-t)))
            if len(cache[(name,scope)])==18:
                out=dict(name=name,scope=scope,per_case=score(cache[(name,scope)],raw),group_map=score(cache[(name,scope)],raw,True));details.append(out)
                (ROOT/'results.json').write_text(json.dumps(dict(results=details,elapsed_s=time.perf_counter()-t),indent=2))
    # Compare to archived proposed-model results independently of fitting.
    old=json.loads((OLD/'h2_strict_singles.json').read_text());archived={r['id']:r for r in old['results']}
    nom={r['id']:r for r in json.loads((ROOT.parent/'sequential-budget-audit-20261028/prepared.json').read_text())['nominal_forecasts']}
    comparison={}
    for scope,ref in [('case_initial',archived),('normal_template',nom)]:
        comparison[scope]={k:float(max(abs(p[k]-ref[p['id']][k]) for p in cache[('ordinary_EE',scope)])) for k in ['prediction','predicted_tilt']}
        comparison[scope]['same_decisions']=all((p['prediction']>1 or p['predicted_tilt']>45)==(ref[p['id']]['prediction']>1 or ref[p['id']]['predicted_tilt']>45) for p in cache[('ordinary_EE',scope)])
    (ROOT/'equivalence.json').write_text(json.dumps(dict(parameter_max_abs=fitted['original_parameter_max_abs'],forecast_max_differences=comparison,interpretation='Same mathematical model and estimator; independent plant and regression implementation. Source controller is intentionally shared under equal-information rules.'),indent=2))
    print('EQUIVALENCE',comparison,flush=True)
if __name__=='__main__':main()
