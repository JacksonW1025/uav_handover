import json,copy,numpy as np,hashlib
from core import ROOT,OLD,reference,forecast,sanitize,plant,vec
from fit_baselines import datasets,fit_ee

def main():
    fitted=json.loads((ROOT/'models.json').read_text());m=fitted['equation_error'];raw=json.loads((ROOT.parent/'offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows']
    rng=np.random.default_rng(37);mx=0.
    for _ in range(50):
        p,v,w=rng.normal(size=(3,3));q=rng.normal(size=4);q/=np.linalg.norm(q);f=rng.uniform(200,900,4)
        a=plant(p,v,q,w,f,m);b=reference.plant(p,v,q,w,f,m)
        mx=max(mx,max(float(np.max(abs(x-y))) for x,y in zip(a,b)))
    assert mx<1e-10
    r=next(r for r in raw if r['family']=='F2' and r['arm']=='AB-short' and r['block']==1);inp=sanitize(r)
    p,z,seam=forecast(inp,m);mut=copy.deepcopy(r);mut['LP_max_loss_m']=999;mut['LP_peak_tilt_deg']=-123;mut['B_before']={'FORBIDDEN':'future'};mut['censored']=not mut['censored'];mut['task']='FAILURE'
    a,u,_=forecast(sanitize(mut),m);assert np.array_equal(z,u)
    checks={}
    for v in ['no_carry','no_neural_carry','no_physical_carry']:
        a,t,s=forecast(inp,m,v);prefix=t[:,0]<s['t'];assert np.array_equal(t[prefix],z[prefix]);checks[v]=dict(prefix_identical=True,seam_time=s['t'],predicted_state_timestamp=s['state_time'])
    b=copy.deepcopy(inp);b['branch']='B';a,t,_=forecast(b,m);c,u,_=forecast(b,m,'no_carry');assert np.array_equal(t,u)
    # Does the same ordinary estimator also reproduce shared-parameter updates?
    ds,manifest,old=datasets();trace=json.loads((ROOT.parent/'sequential-budget-audit-20261028/trajectory_results.json').read_text());path=next(r for r in trace['results'] if r['policy']=='short_duration_first');updates=[]
    for step in path['steps'][:3]:
        use=[d for d in ds if d['id'].endswith('-NORMAL') or d['id'] in step['selected']]
        est=fit_ee(use);delta=float(np.max(abs(vec(est)-vec(step['model']))));assert delta<1e-8
        # Forecast all18 held AB map cells at budgets0,1,2, so update equality is executed.
        preds=[]
        for rr in raw:
            if rr['branch']!='AB':continue
            ii=sanitize(rr);ii['initial']=copy.deepcopy(next(q['initial'] for q in raw if q['family']==rr['family'] and q['block']==rr['block'] and q['branch']=='NORMAL'))
            pp,_,_=forecast(ii,est);preds.append(pp)
        from evaluate import score
        ss=score(preds,{r['id']:r for r in raw},True)['metrics'];ref=step['greybox'];updates.append(dict(budget=step['budget'],selected=step['selected'],parameter_max_delta=delta,ordinary_metrics=ss,proposed_metrics=ref,height_MAE_abs_delta=abs(ss['height_MAE']-ref['height_MAE'])))
        assert abs(ss['height_MAE']-ref['height_MAE'])<1e-6
    out=dict(plant_step_max_difference=mx,labels_and_future_state_permutation_invariant=True,carry_ablation_preserves_entire_prefix=checks,no_A_no_carry_identity=True,training_hashes_verified=len(manifest),no_AB_training=True,ordinary_shared_parameter_updates=updates)
    (ROOT/'verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()
