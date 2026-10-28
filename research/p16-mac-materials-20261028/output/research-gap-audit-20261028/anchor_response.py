"""Exact one-call source intervention, fixed measured physical and recurrent state.

Changes only vertical reference during recorded timeout intervals. This computes
command changes, NOT a new flight response or closed-loop repair outcome.
"""
from pathlib import Path
import json,numpy as np
ROOT=Path(__file__).resolve().parent
P=dict(np.load(ROOT.parent/'offline-adjoint-20261028/upstream/data/p11-20261025-formal/models/policy.npz'))

def network(h,x):
    e=np.maximum(0,x@P['W0'].T+P['b0']);gi=e@P['Wi'].T+P['bi'];gh=h@P['Wh'].T+P['bh']
    sig=lambda z:1/(1+np.exp(-z));r=sig(gi[:,:16]+gh[:,:16]);z=sig(gi[:,16:32]+gh[:,16:32]);n=np.tanh(gi[:,32:]+r*gh[:,32:])
    hh=(1-z)*n+z*h;return np.clip(hh@P['W2'].T+P['b2'],-1,1)

def main():
    events=[];validation=[];interval=[]
    for p in sorted((ROOT.parent/'model-search-20261028/upstream/data/p11-20261025-formal').glob('*/packed/measurement.npz')):
        d=dict(np.load(p));t=d['profile_s'];stale=d['stale'].astype(bool);N=len(t)
        last=np.maximum.accumulate(np.where(d['read_valid'].astype(bool),np.arange(N),-1));valid=last>=0
        ix=np.flatnonzero(valid&stale&(t>=12.5)&(t<17.))
        if not len(ix):continue
        h=d['h_before'][ix];x=d['input'][ix].copy();aa=network(h,x);err=float(np.max(abs(aa-d['action'][ix])));validation.append(dict(id=p.parts[-3],rows=len(ix),max_action_error=err));assert err<1e-5
        anchor=d['external_p'][last[ix],2];height_error=d['position'][ix,2]-anchor
        xx=x.copy();xx[:,2]=np.clip(-height_error,-.5,.5);bb=network(h,xx)
        # Permutation of motors does not affect collective command; [0,1] scale.
        du=(bb-aa).mean(axis=1)/2
        caps=set((np.flatnonzero(stale[1:]&~stale[:-1])+1).tolist())
        for j,i in enumerate(ix):
            r=dict(id=p.parts[-3],profile_s=float(t[i]),task_relative_down_error=float(height_error[j]),down_velocity=float(d['velocity'][i,2]),original_z_input=float(x[j,2]),anchored_z_input=float(xx[j,2]),collective_command_change=float(du[j]),largest_motor_change=float(np.max(abs(bb[j]-aa[j]))/2))
            if i in caps:events.append(r)
        mask=height_error>.1
        if np.any(mask):interval.append(dict(id=p.parts[-3],rows=int(mask.sum()),positive_fraction=float(np.mean(du[mask]>0)),mean_collective_change=float(du[mask].mean()),min_collective_change=float(du[mask].min()),max_collective_change=float(du[mask].max())))
    selected=[r for r in events if r['task_relative_down_error']>.1]
    out=dict(scope='Exact single-call counterfactual only: original measured h, previous-action history, attitude, velocity and physical state retained. Change vertical position input to reference the last valid external altitude. No trajectory rollout; no measured repair outcome claimed.',
        validation=validation,events=events,intervals=interval,summary=dict(captures=len(events),captures_with_down_error_above_10cm=len(selected),positive_collective_changes=sum(r['collective_command_change']>0 for r in selected),mean_collective_change=float(np.mean([r['collective_command_change'] for r in selected])) if selected else None,max_replay_error=max(r['max_action_error'] for r in validation)),new_flights=0,new_SITL=0,Thor_used=False)
    (ROOT/'anchor_response.json').write_text(json.dumps(out,indent=2));print(json.dumps(out['summary'],indent=2));print(json.dumps(selected,indent=2))

if __name__=='__main__':main()
