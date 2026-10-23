#!/usr/bin/env python3
"""Pure P9 search policies: only frozen candidate forecasts + OWN observations.

No files, B/D outcomes or reference oracle are accessible through this API.
No monotonicity assumption. An adjacent unlike pair needs two extra confirmations.
"""
import math


def segments(candidates):
    es=[c['max_energy'] for c in candidates];cuts=[0]
    for k in range(1,len(es)-1):
        if (es[k]-es[k-1])*(es[k+1]-es[k])<=0:cuts.append(k)
    return list(zip(cuts,cuts[1:]+[len(es)-1]))


def propose(method,candidates,history,limit=10):
    if method not in ['ledger','replay']:raise ValueError('unknown search method')
    n=len(candidates)
    if n!=12:raise ValueError('frozen grid must contain 12 candidates')
    if len(history)<2:return {'status':'QUERY_ENDPOINT','index':0 if not history else n-1}
    obs={}
    for row in history:
        if not isinstance(row['failure'],bool):raise ValueError('feedback must be a measured binary failure')
        obs.setdefault(row['index'],[]).append(row['failure'])
    noisy={i for i,vals in obs.items() if len(set(vals))>1}
    brackets=[(i,i+1) for i in range(n-1) if i in obs and i+1 in obs and
              i not in noisy and i+1 not in noisy and obs[i][0]!=obs[i+1][0]]
    for a,b in brackets:
        if len(obs[a])>=2 and len(obs[b])>=2:
            return {'status':'LOCAL_CONFIRMED_BRACKET','index':None,'bracket':[a,b],
                    'other_transitions_unresolved':True,'noisy_indices':sorted(noisy)}
        if len(history)>=limit:return {'status':'BUDGET_EXHAUSTED','index':None,'noisy_indices':sorted(noisy)}
        for k in [a,b]:
            if len(obs[k])<2:return {'status':'CONFIRM_ENDPOINT','index':k,'bracket':[a,b]}
    if len(history)>=limit:return {'status':'BUDGET_EXHAUSTED','index':None,'noisy_indices':sorted(noisy)}
    available=[i for i in range(n) if i not in obs]
    if not available:return {'status':'GRID_EXHAUSTED_NO_CONFIRMED_BRACKET','index':None,'noisy_indices':sorted(noisy)}
    if method=='replay':
        chosen=min(available,key=lambda i:(abs(candidates[i]['point_tilt_deg']-45.),i))
    else:
        seg=segments(candidates)
        # Visit unexplored local energy segments before refining covered segments.
        def score(i):
            containing=[(a,b) for a,b in seg if a<=i<=b]
            visited=min(sum(j in obs for j in range(a,b+1)) for a,b in containing)
            near_unlike=any(abs(i-j)==1 and ((candidates[i]['point_tilt_deg']>=45.) != obs[j][0]) for j in obs)
            jump=candidates[i]['positive_event_injection']
            curvature=0. if i in [0,n-1] else abs(candidates[i+1]['max_energy']-2*candidates[i]['max_energy']+candidates[i-1]['max_energy'])
            return (visited,not near_unlike,-jump-curvature,abs(candidates[i]['point_tilt_deg']-45.),i)
        chosen=min(available,key=score)
    return {'status':'QUERY','index':chosen,'noisy_indices':sorted(noisy)}


def observed_brackets(candidates,history):
    obs={}
    for h in history:obs.setdefault(h['index'],[]).append(h['failure'])
    out=[]
    for i in range(len(candidates)-1):
        if i in obs and i+1 in obs and len(set(obs[i]))==len(set(obs[i+1]))==1 and obs[i][0]!=obs[i+1][0]:
            out.append([candidates[i]['phase_s'],candidates[i+1]['phase_s']])
    return out
