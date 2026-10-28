"""Post-hoc audit of archived P8 evidence. No simulator or remote execution."""
from pathlib import Path
import csv,json,re,hashlib
from collections import defaultdict
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier,RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score,roc_auc_score

ROOT=Path(__file__).resolve().parent

def load():
    rows=list(csv.DictReader((ROOT/'upstream/export/p8_b_results.csv').open()))
    for r in rows:
        m=re.fullmatch(r'v([\d.]+)-H([\d.]+)-W(.+):(T[01])',r['name']);assert m
        wins=np.array([[float(v) for v in p.split('-')] for p in m[3].split('_')]);ds=wins[:,1]-wins[:,0];gs=wins[1:,0]-wins[:-1,1]
        r.update(v=float(m[1]),heading=float(m[2]),n=len(ds),ds=ds.tolist(),gs=gs.tolist(),windows=wins.tolist(),sector=int(min(float(m[2]),89.99)//15))
        for k in ['seed','k','fail_primary','fail_task']:r[k]=int(r[k])
        for k in ['max_tilt_deg','max_alt_loss_m']:r[k]=float(r[k])
    assert len(rows)==900
    return rows

def features(r,kind):
    ds=np.array(r['ds']);gs=np.array(r['gs']);h=np.deg2rad(r['heading']);v=r['v']
    base=[v,np.sin(h),np.cos(h),np.sin(2*h),r['n']]
    if kind=='bag':return base+sorted(ds.tolist())+[0.]*(4-len(ds))+sorted(gs.tolist())+[0.]*(3-len(gs))
    if kind=='ordered':return base+ds.tolist()+[0.]*(4-len(ds))+gs.tolist()+[0.]*(3-len(gs))
    if kind=='summary':return base+[ds.sum(),ds.min(),ds.max(),ds.mean(),gs.sum(),gs.min(),gs.max(),gs.mean()]
    raise ValueError(kind)

def metric(y,p):
    y=np.array(y);p=np.array(p);hard=p>=.5
    return dict(n=len(y),accuracy=float(np.mean(hard==y)),balanced_accuracy=float(balanced_accuracy_score(y,hard)),brier=float(np.mean((p-y)**2)),auc=float(roc_auc_score(y,p)) if len(set(y))>1 else None)

def main():
    rows=load();by=defaultdict(list)
    for r in rows:by[r['name']].append(r)
    repeats=[]
    for name,g in by.items():
        if len(g)>1:
            y=[r['fail_task'] for r in g];tilt=[r['max_tilt_deg'] for r in g]
            repeats.append(dict(name=name,n=len(g),task_failures=sum(y),task_flip=min(y)!=max(y),tilt_min=min(tilt),tilt_max=max(tilt),tilt_range=max(tilt)-min(tilt),methods=[r['method'] for r in g]))
    folds=[]
    for sut in ['T0','T1']:
        subset=[r for r in rows if r['sut']==sut]
        for field in ['method','n','sector']:
            for val in sorted(set(r[field] for r in subset)):
                test=[r for r in subset if r[field]==val];names={r['name'] for r in test}
                train=[r for r in subset if r[field]!=val and r['name'] not in names]
                if not train:continue
                preds={};res={};y=[r['fail_task'] for r in test]
                for kind in ['summary','bag','ordered']:
                    model=ExtraTreesClassifier(n_estimators=256,min_samples_leaf=4,max_features=1.,random_state=20261028,n_jobs=2)
                    model.fit([features(r,kind) for r in train],[r['fail_task'] for r in train]);p=model.predict_proba([features(r,kind) for r in test])[:,1]
                    preds[kind]=p.tolist();res[kind]=metric(y,p)
                    # Fixed pool ranking; ties receive fractional expected success.
                    order=np.argsort(-p,kind='stable');cut=p[order[min(10,len(p))-1]];strict=p>cut;tie=p==cut
                    res[kind]['expected_failures_top10']=float(np.sum(np.array(y)[strict])+(min(10,len(p))-strict.sum())*np.mean(np.array(y)[tie]))
                folds.append(dict(sut=sut,field=field,value=val,train_n=len(train),test_n=len(test),metrics=res,case_names=[r['name'] for r in test],y=y,predictions=preds))
                print(sut,field,val,{k:round(v['accuracy'],3) for k,v in res.items()},flush=True)
    aggregates=[]
    for sut in ['T0','T1']:
        for field in ['method','n','sector']:
            ff=[f for f in folds if f['sut']==sut and f['field']==field]
            y=sum([f['y'] for f in ff],[])
            aggregates.append(dict(sut=sut,holdout=field,metrics={kind:metric(y,sum([f['predictions'][kind] for f in ff],[])) for kind in ['summary','bag','ordered']}))
    out=dict(scope='Retrospective descriptive audit. All outcomes previously available. Duplicate planned cases removed across train/test. Does not evaluate a newly executed adaptive test policy or causal transfer.',
        source=dict(ref='d0f3924c762e7fbaf5d799ae582a5b59ebb578f0',sha256=hashlib.sha256((ROOT/'upstream/export/p8_b_results.csv').read_bytes()).hexdigest()),
        counts=dict(rows=len(rows),unique_planned_cases=len(by),repeated_case_groups=len(repeats),repeated_rows=sum(r['n'] for r in repeats),task_flip_groups=sum(r['task_flip'] for r in repeats),minimum_errors_for_one_label_per_planned_case=sum(min(sum(r['fail_task'] for r in g),len(g)-sum(r['fail_task'] for r in g)) for g in by.values())),
        repeats=sorted(repeats,key=lambda r:-r['tilt_range']),aggregates=aggregates,folds=folds,new_flights=0,new_SITL=0,Thor_used=False)
    (ROOT/'p8_audit.json').write_text(json.dumps(out,indent=2))
    print('COUNTS',out['counts']);print('AGGREGATES',json.dumps(aggregates));print('WORST_REPEATS',json.dumps(out['repeats'][:8]))

if __name__=='__main__':main()
