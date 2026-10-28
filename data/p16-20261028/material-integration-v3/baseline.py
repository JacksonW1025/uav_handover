"""Label-oracle blind replay. Policy only sees its own queried records."""
from p16.quality import task

def predict(pool,history):
 out={}
 for family in sorted({c['family'] for c in pool}):
  points=sorted([c for c in pool if c['family']==family],key=lambda c:c['G']);known=[(i,history[c['id']]) for i,c in enumerate(points) if c['id'] in history and history[c['id']].get('valid',False)]
  for i,c in enumerate(points):
   if c['id'] in history and history[c['id']].get('valid',False):out[c['id']]={k:history[c['id']][k] for k in ['tilt','height','task']};continue
   if not known:out[c['id']]=dict(tilt='UNKNOWN',height='UNKNOWN',task='UNKNOWN');continue
   left=next(((j,r) for j,r in reversed(known) if j<i),known[0]);right=next(((j,r) for j,r in known if j>i),known[-1]);d={}
   for component in ['tilt','height']:
    a=left[1][component];b=right[1][component]
    if 'UNKNOWN' in [a,b]:d[component]='UNKNOWN'
    else:
     t=0 if right[0]==left[0] else (c['G']-points[left[0]]['G'])/(points[right[0]]['G']-points[left[0]]['G']);prob=(a=='FAIL')*(1-t)+(b=='FAIL')*t;d[component]='FAIL' if prob>=.5 else 'SUCCESS'
   d['task']=task(d['tilt'],d['height']);out[c['id']]=d
 return out

def choose(pool,history):
 remaining=[c for c in pool if c['id'] not in history];assert remaining
 # Fixed coarse initial cover: each family endpoints and midpoint, interleaved.
 families=sorted({c['family'] for c in pool});grids={f:sorted([c for c in pool if c['family']==f],key=lambda c:c['G']) for f in families}
 coarse=[grids[f][i]['id'] for i0 in [0,-1,'mid'] for f in families for i in [len(grids[f])//2 if i0=='mid' else i0]]
 for ident in coarse:
  if ident not in history:return next(c for c in pool if c['id']==ident)
 ranked=[]
 for c in remaining:
  pp=grids[c['family']];i=pp.index(c);known=[j for j,x in enumerate(pp) if x['id'] in history and history[x['id']].get('valid',False)];left=max([j for j in known if j<i],default=None);right=min([j for j in known if j>i],default=None);transition=False;width=0;middle=0
  if left is not None and right is not None:
   a=history[pp[left]['id']]['task'];b=history[pp[right]['id']]['task'];transition=a!='UNKNOWN' and b!='UNKNOWN' and a!=b;width=pp[right]['G']-pp[left]['G'];middle=abs(c['G']-(pp[right]['G']+pp[left]['G'])/2)
  distance=min([abs(c['G']-pp[j]['G']) for j in known],default=10)
  ranked.append((not transition,-width if transition else -distance,middle,c['family'],c['G'],c))
 return sorted(ranked,key=lambda x:x[:-1])[0][-1]

def replay(pool,oracle):
 history={};maps=[dict(query=0,prediction=predict(pool,history),seen_ids=[])]
 for q in range(len(pool)):
  chosen=choose(pool,history);record=oracle(chosen['id']);history[chosen['id']]=record;maps.append(dict(query=q+1,selected=chosen,seen_ids=list(history),prediction=predict(pool,history)))
 return maps
