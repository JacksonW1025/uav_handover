#!/usr/bin/env python3
"""Known-input memory counterfactuals; never a closed-loop flight counterfactual."""
import argparse,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p3_memory import load_policy
from p11.observe import network
from p9_model import write,sha


def compare(sync,out):
    d=dict(np.load(sync));P=load_policy();reports={}
    # The same recorded exogenous input is held fixed: controlled network sensitivity only.
    for name in ['zero_hidden','zero_previous_history','zero_both']:
        error=[]
        for i,x in enumerate(d['input']):
            h=d['h_before'][i].copy();xx=x.copy()
            if name in ['zero_hidden','zero_both']:h[:]=0
            if name in ['zero_previous_history','zero_both']:xx[18:]=0
            _,_,a=network(P,h,xx);error.append(float(np.linalg.norm(a-d['action'][i])))
        reports[name]={'output_L2_max':max(error),'output_L2_p95':float(np.quantile(error,.95)),'output_L2_mean':float(np.mean(error)),
            'source_realizability':'StateBridge inject can replace GRU/previous-action but action-mean executor history has no independent public reset; zero history is a partial intervention, not asserted reachable flight state'}
    write(out,{'schema':'p11-memory-sensitivity-1','sync_sha256':sha(sync),'rows':len(d['sample_us']),'experiments':reports,
        'classification':'known-input offline interventions, not causal contribution to observed body response; no future closed-loop claim'})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('sync',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    compare(a.sync,a.output)
