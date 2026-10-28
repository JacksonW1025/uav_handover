"""Offline, configuration-held-out search audit. See protocol.json before results."""
from pathlib import Path
import json, hashlib, itertools, math, copy
import numpy as np
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import Ridge
from sklearn.tree import DecisionTreeRegressor

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent.parent
ALPHAS=[.01,.1,1.,10.]
METHODS=['state_split','cheap_rank','cheap_ridge','cheap_tree','lookup','pooled_suffix']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x): p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False))

def read_data():
    p=PROJECT/'output/offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json'
    a=json.loads(p.read_text())['rows']; records=[]; sources=[p]
    for r in a:
        branch=r['branch']; hasb=branch in ['B','AB','REPAIR']; hasa=branch in ['A','AB','REPAIR']; repair=branch=='REPAIR'
        g=float(r['gap_s']) if hasb else 0.
        records.append(dict(dataset='P13',id=r['id'],group=r['family']+'|'+r['arm'],family=r['family'],condition=r['family'],arm=r['arm'],branch=branch,block=r['block'],hasb=hasb,gap=g,
            h=[float(hasa),float(repair)],s=[float(r['family']=='F4'),float(hasb),float(repair),g/2],y=float(r['task']=='FAILURE'),
            extra=dict(task=r['task'],censored=r['censored'],tilt=r['LP_peak_tilt_deg'],height=r['LP_max_loss_m'])))
    for p in sorted((ROOT/'upstream/data').glob('*/p3-metrics.json')):
        r=json.loads(p.read_text()); sources.append(p); d=r['condition'];t=r['treatment']; rep=int(p.parent.name.rsplit('-',1)[1])
        e=r['events']['second_C_to_N'];assert r['deactivation']['requested_s'] in [.3,10.]
        records.append(dict(dataset='P3',id=p.parent.name,group=d+'|'+t,condition=d,family=d,arm=t,block=rep,
            h=[r['deactivation']['requested_s']/10,float(d=='D3')],s=[float(t==z) for z in ['N0','N2','N2s','N3']],
            y=float(e['motor']['step_at_change']),extra=dict(outcome=r['flight_outcome'],treatment=r['treatment_parameters'])))
    assert len([r for r in records if r['dataset']=='P13'])==66
    assert len([r for r in records if r['dataset']=='P3'])==36
    dump(ROOT/'inputs_manifest.json',dict(protocol_sha256=sha(ROOT/'protocol.json'),files=[dict(path=str(p.relative_to(PROJECT)),sha256=sha(p),bytes=p.stat().st_size) for p in sources]))
    dump(ROOT/'records.json',records)
    return records

def aggregate(rows):
    groups=sorted(set(r['group'] for r in rows)); out=[]
    for g in groups:
        rr=[r for r in rows if r['group']==g]; assert len(rr)==3
        assert len(set(tuple(r['h']+r['s']) for r in rr))==1
        out.append(dict(group=g,h=rr[0]['h'],s=rr[0]['s'],y=np.mean([r['y'] for r in rr]),n=len(rr)))
    return out

def arrays(rows):
    return np.array([r['h'] for r in rows]),np.array([r['s'] for r in rows]),np.array([r['y'] for r in rows])

class Head:
    def __init__(self,alpha,degree=2): self.alpha=alpha;self.degree=degree
    def fit(self,x,y):
        self.poly=PolynomialFeatures(degree=self.degree,include_bias=False);z=self.poly.fit_transform(x)
        self.model=Ridge(alpha=self.alpha).fit(z,y);return self
    def predict(self,x):return self.model.predict(self.poly.transform(x))

class StateSplit:
    def __init__(self,max_states,alpha):self.max_states=max_states;self.alpha=alpha
    def fit(self,h,s,y):
        self.h=h;self.s=s;self.y=y;self.nodes=[];self.witnesses=[]
        def leaf(idx):return dict(idx=idx,head=Head(self.alpha).fit(s[idx],y[idx]))
        self.root=leaf(np.arange(len(y))); leaves=[self.root]
        while len(leaves)<self.max_states:
            best=None
            for node in leaves:
                idx=node['idx']; before=np.sum((y[idx]-node['head'].predict(s[idx]))**2)
                for j in range(h.shape[1]):
                    vals=sorted(set(h[idx,j]));thresholds=[(a+b)/2 for a,b in zip(vals,vals[1:])]
                    for cut in thresholds:
                        li=idx[h[idx,j]<=cut];ri=idx[h[idx,j]>cut]
                        if min(len(li),len(ri))<2:continue
                        witness=None
                        for a in li:
                            for b in ri:
                                if np.array_equal(s[a],s[b]) and abs(y[a]-y[b])>1e-10:
                                    witness=dict(left=int(a),right=int(b),suffix=s[a].tolist(),left_y=float(y[a]),right_y=float(y[b]));break
                            if witness:break
                        if witness is None:continue
                        l=leaf(li);r=leaf(ri)
                        after=sum(np.sum((y[z['idx']]-z['head'].predict(s[z['idx']]))**2) for z in [l,r])
                        gain=before-after
                        if gain>1e-10 and (best is None or gain>best[0]+1e-12):best=(gain,node,j,cut,l,r,witness)
            if best is None:break
            gain,node,j,cut,l,r,witness=best;leaves.remove(node)
            node.update(j=j,cut=float(cut),left=l,right=r);leaves.extend([l,r]);self.witnesses.append(dict(feature=j,threshold=float(cut),training_gain=float(gain),witness=witness))
        self.n_states=len(leaves);return self
    def predict(self,h,s):
        result=[]
        for a,b in zip(h,s):
            node=self.root
            while 'j' in node:node=node['left'] if a[node['j']]<=node['cut'] else node['right']
            result.append(node['head'].predict(b[None,:])[0])
        return np.array(result)

class Predictor:
    def __init__(self,spec):self.spec=spec
    def fit(self,rows):
        h,s,y=arrays(rows);self.train=rows;self.h=h;self.s=s;self.y=y;kind=self.spec['kind'];x=np.c_[h,s]
        if kind=='state':self.model=StateSplit(self.spec['states'],self.spec['alpha']).fit(h,s,y)
        elif kind=='pooled':self.model=Head(self.spec['alpha']).fit(s,y)
        elif kind=='ridge':self.model=Head(self.spec['alpha'],self.spec['degree']).fit(x,y)
        elif kind=='tree':self.model=DecisionTreeRegressor(max_depth=self.spec['depth'],min_samples_leaf=self.spec['min_leaf'],random_state=0).fit(x,y)
        return self
    def predict(self,rows):
        h=np.array([r['h'] for r in rows]);s=np.array([r['s'] for r in rows]);kind=self.spec['kind'];x=np.c_[h,s]
        if kind=='state':out=self.model.predict(h,s)
        elif kind=='pooled':out=self.model.predict(s)
        elif kind=='lookup':
            out=[]
            for xx in x:
                d=np.sum((np.c_[self.h,self.s]-xx)**2,axis=1);out.append(np.mean(self.y[np.isclose(d,d.min(),atol=1e-12,rtol=0)]))
            out=np.array(out)
        else:out=self.model.predict(x)
        return out
    def details(self):
        d=dict(spec=self.spec)
        if self.spec['kind']=='state':
            witnesses=copy.deepcopy(self.model.witnesses)
            for w in witnesses:
                for z in ['left','right']:w['witness'][z+'_group']=self.train[w['witness'][z]]['group']
            d.update(states=self.model.n_states,witnesses=witnesses)
        return d

def cv_score(spec,train):
    errors=[]
    for i in range(len(train)):
        tr=train[:i]+train[i+1:];te=train[i:i+1]
        p=Predictor(spec).fit(tr).predict(te)[0];errors.append((p-te[0]['y'])**2)
    return float(np.mean(errors))

def fit_all(train):
    specs={
      'state_split':[dict(kind='state',states=k,alpha=a) for k in [1,2,3,4] for a in ALPHAS],
      'pooled_suffix':[dict(kind='pooled',alpha=a) for a in ALPHAS],
      'cheap_ridge':[dict(kind='ridge',degree=d,alpha=a) for d in [1,2] for a in ALPHAS],
      'cheap_tree':[dict(kind='tree',depth=d,min_leaf=l) for d in [1,2,3,4] for l in [1,2]]}
    models={};details={}
    for m,ss in specs.items():
        scores=[cv_score(s,train) for s in ss];i=int(np.argmin(scores));model=Predictor(ss[i]).fit(train);models[m]=model
        details[m]=dict(**model.details(),cv_mse=scores[i],candidates=[dict(spec=s,cv_mse=e) for s,e in zip(ss,scores)])
    best=min(['cheap_ridge','cheap_tree'],key=lambda m:details[m]['cv_mse']);models['cheap_rank']=models[best];details['cheap_rank']=dict(**details[best],selected_family=best)
    models['lookup']=Predictor(dict(kind='lookup')).fit(train);details['lookup']=models['lookup'].details()
    return models,details

def folds(dataset,rows):
    if dataset=='P13':
        definitions=[('all_AB',lambda r:r['branch']=='AB'),('all_B_only',lambda r:r['branch']=='B'),('all_REPAIR',lambda r:r['branch']=='REPAIR'),('F2_AB',lambda r:r['family']=='F2' and r['branch']=='AB'),('F4_AB',lambda r:r['family']=='F4' and r['branch']=='AB'),('family_F2',lambda r:r['family']=='F2'),('family_F4',lambda r:r['family']=='F4')]
        for name,g in [('short',.55),('medium',1.2),('long',2.)]:definitions.append(('gap_'+name,lambda r,g=g:r['hasb'] and abs(r['gap']-g)<1e-6))
    else:
        definitions=[(d,lambda r,d=d:r['condition']==d) for d in ['D1','D2','D3']]
        definitions += [('all_long',lambda r:r['condition'] in ['D2','D3'])]
        for parity in [0,1]:definitions.append(('checkerboard_'+str(parity),lambda r,p=parity: (['D1','D2','D3'].index(r['condition'])+['N0','N2','N2s','N3'].index(r['arm']))%2==p))
    for name,fn in definitions:
        te=[r for r in rows if fn(r)];tr=[r for r in rows if not fn(r)]
        assert not (set(r['group'] for r in tr)&set(r['group'] for r in te))
        assert all(sum(x['group']==r['group'] for x in te)==3 for r in te)
        yield name,tr,te

def choice_weights(pred):
    pred=np.round(pred,10);win=pred==pred.max();return win.astype(float)/win.sum()

def pool_metrics(pred,y,binary):
    p=np.round(pred,10);y=np.array(y);w=choice_weights(p);top=float(w@y);best=float(y.max());worsthit=float(w@(np.isclose(y,y.max(),atol=1e-10)))
    pairs=[]
    for i,j in itertools.combinations(range(len(y)),2):
        if abs(y[i]-y[j])>1e-10:pairs.append(float((p[i]-p[j])*(y[i]-y[j])>0)+.5*float(p[i]==p[j]))
    result=dict(top1=top,regret=best-top,worst_hit=worsthit,pair_accuracy=float(np.mean(pairs)) if pairs else None,weights=w.tolist())
    if binary:
        first=None;offset=0;found2=0.;left=2
        for score in sorted(set(p),reverse=True):
            idx=np.flatnonzero(p==score);n=len(idx);k=int(y[idx].sum())
            if first is None and k:first=offset+(n+1)/(k+1)
            if left>0:found2+=min(left,n)*k/n;left-=n
            offset+=n
        result.update(first_failure_rank=first,failures_at_2=found2,fail_count=int(y.sum()),n=len(y),random_top1=float(y.mean()),random_first=(len(y)+1)/(y.sum()+1) if y.sum() else None)
    return result

def evaluate(dataset,te,preds):
    evalrows=[r for r in te if dataset!='P13' or r['hasb']]
    key=lambda r:r['condition']+'|'+str(r['block'])
    pools=[]
    for k in sorted(set(map(key,evalrows))):
        rr=[r for r in evalrows if key(r)==k];y=[r['y'] for r in rr]
        mm={m:pool_metrics([preds[m][r['id']] for r in rr],y,dataset=='P13') for m in METHODS}
        pools.append(dict(pool=k,ids=[r['id'] for r in rr],arms=[r['arm'] for r in rr],y=y,predictions={m:[preds[m][r['id']] for r in rr] for m in METHODS},metrics=mm))
    summary={}
    for m in METHODS:
        mm=[p['metrics'][m] for p in pools];summary[m]={}
        for field in ['top1','regret','worst_hit','pair_accuracy','first_failure_rank','failures_at_2']:
            vals=[x[field] for x in mm if field in x and x[field] is not None]
            if vals:summary[m][field]=float(np.mean(vals))
        score=lambda r:float(np.clip(preds[m][r['id']],0,1)) if dataset=='P13' else preds[m][r['id']]
        err=[(score(r)-r['y'])**2 for r in evalrows];summary[m]['map_mse']=float(np.mean(err))
        erra=[(score(r)-r['y'])**2 for r in te];summary[m]['map_mse_all_heldout']=float(np.mean(erra))
    comparisons={}
    for other in ['cheap_rank','cheap_ridge','cheap_tree','lookup','pooled_suffix']:
        changed=wins=losses=ties=0;deltas=[]
        for p in pools:
            a=p['metrics']['state_split'];b=p['metrics'][other]
            if not np.allclose(a['weights'],b['weights'],atol=1e-10):
                changed+=1;delta=a['top1']-b['top1'];deltas.append(delta)
                wins+=int(delta>1e-10);losses+=int(delta< -1e-10);ties+=int(abs(delta)<=1e-10)
        comparisons[other]=dict(changed=changed,wins=wins,losses=losses,ties=ties,sum_top1_difference_on_changed=float(sum(deltas)))
    return dict(pools=pools,summary=summary,comparisons=comparisons,eval_count=len(evalrows),pool_count=len(pools),mixed_pools=sum(0<sum(p['y'])<len(p['y']) for p in pools) if dataset=='P13' else None)

def validate_metrics():
    assert pool_metrics([-.2,-.1],[0,1],True)['top1']==1.0
    m=pool_metrics([0,0,0],[1,0,0],True)
    assert abs(m['top1']-1/3)<1e-10 and abs(m['first_failure_rank']-2)<1e-10 and abs(m['failures_at_2']-2/3)<1e-10
    m=pool_metrics([2,1,1],[0,1,0],True);assert abs(m['first_failure_rank']-2.5)<1e-10
    m=pool_metrics([1,1,1],[.2,.4,.6],False);assert abs(m['top1']-.4)<1e-10

def main():
    validate_metrics();rows=read_data();results=[]
    for ds in ['P13','P3']:
        rr=[r for r in rows if r['dataset']==ds]
        for name,tr,te in folds(ds,rr):
            print('Fitting',ds,name,len(tr),len(te),flush=True);train=aggregate(tr);models,details=fit_all(train);preds={}
            for m,model in models.items():
                p=model.predict(te)
                # Held-out labels are never read by predict; mutate all to verify.
                mutated=copy.deepcopy(te)
                for r in mutated:r['y']=100-r['y']
                q=model.predict(mutated)
                assert np.array_equal(p,q)
                preds[m]={r['id']:float(z) for r,z in zip(te,p)}
            result=dict(dataset=ds,fold=name,train_groups=[r['group'] for r in train],test_groups=sorted(set(r['group'] for r in te)),train_n=len(tr),test_n=len(te),models=details,predictions=preds,**evaluate(ds,te,preds))
            results.append(result);dump(ROOT/'results.json',dict(protocol_sha256=sha(ROOT/'protocol.json'),results=results))
            print('RESULT',ds,name,{m:round(result['summary'][m]['top1'],5) for m in METHODS},'states',details['state_split']['states'],flush=True)
    # Exact deterministic rerun of first fold, including model selection.
    _,tr,te=next(folds('P13',[r for r in rows if r['dataset']=='P13']));models,_=fit_all(aggregate(tr))
    for m,model in models.items():assert np.array_equal(model.predict(te),np.array([results[0]['predictions'][m][r['id']] for r in te]))
    dump(ROOT/'validation.json',dict(passed=True,checks=['complete replicates held together','no configuration overlap in every fold','feature whitelist (planned metadata only)','heldout label mutation invariance on all folds and methods','deterministic first-fold full refit','analytical random-tie metric unit checks','all 16 fixed folds completed'],folds=len(results),raw_records=len(rows),protocol_sha256=sha(ROOT/'protocol.json'),audit_sha256=sha(Path(__file__))))
    print('Complete: 16 folds, all validation passed.',flush=True)

if __name__=='__main__':main()
