#!/usr/bin/env python3
"""Signed/clock/state/event structure; diagnostic only, no empirical hard bound."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
from data import ROOT,write,sha
from experiment import load_inputs,stats
from models import baseline,valid_steps,residuals,rot


def run(inp,out):
    out.mkdir(parents=True,exist_ok=False);result=[];portable=[]
    for meta,a in load_inputs(inp):
        m=baseline();k=valid_steps(a,24,meta['profile_start_bound_us']);w,norm,aux,_=residuals(a,m,k)
        diag={**m,'sensor_clocks':True,'yaw_transport':'delayed_frame','name':'fixed_parameter_clock_diagnostic_NOT_an_extra_fitted_candidate'}
        wc,nc,_,_=residuals(a,diag,k)
        lp=a['t']-a['lp_age_us'];advance=lp[k+1]-lp[k]
        signed={}
        for coordinate in range(3):
            for lag in [1,5,25,125]:
                ix=np.arange(lag,len(k));good=(k[ix]-k[ix-lag]==lag)&(a['phase'][k[ix]]==a['phase'][k[ix-lag]])
                x=w[ix[good],coordinate,0];y=w[ix[good]-lag,coordinate,0]
                signed[f'{coordinate}_lag_{lag}']=None if len(x)<3 or np.std(x)==0 or np.std(y)==0 else float(np.corrcoef(x,y)[0,1])
        clock={str(x):{'rows':int((advance==x).sum()),'p_residual_bias_NED':np.mean(w[advance==x,0],axis=0).tolist(),
            'v_residual_bias_NED':np.mean(w[advance==x,1],axis=0).tolist(),'common_P95':float(np.quantile(norm[advance==x],.95))} for x in np.unique(advance)}
        bins=[];qn=np.linalg.norm(a['q'][k],axis=1)
        for lo,hi in [(0,.5),(.5,2),(2,5),(5,1000)]:
            mask=(qn>=lo)&(qn<hi)
            if mask.any():bins.append({'q_norm_interval':[lo,hi],'rows':int(mask.sum()),'P_norm':stats(norm[mask])})
        phase=a['phase'][k];normal=norm[phase=='normal'];threshold=float(np.quantile(normal,.95));persist=[]
        edges=np.flatnonzero((phase[1:]!=phase[:-1])&np.isin(phase[1:],['capture','resume']))+1
        for z,edge in enumerate(edges):
            end=min(len(k),edge+500,edges[z+1] if z+1<len(edges) else len(k));found=None
            for j in range(edge,end-24):
                if k[j+24]-k[j]==24 and (norm[j:j+25]<=threshold).all():found=(a['t'][k[j]]-a['t'][k[edge]])/1e6;break
            persist.append({'event_phase':str(phase[edge]),'sample_us':int(a['t'][k[edge]]),'below_normal_P95_for_100ms_after_s':found,
                'censored':found is None,'observed_window_s':(a['t'][k[end-1]]-a['t'][k[edge]])/1e6})
        # Correlate with the actual commit flag descriptively, not causal GRU attribution.
        raw=ROOT/f'data/p9-20261024-dev-{meta["run"]:02}/run/flight.ulg'
        tm=ULog(str(raw),['research_timing']).data_list[0].data;tms=np.asarray(tm['timestamp_sample'],np.int64)
        ix=np.minimum(np.searchsorted(tms,a['t'][k]),len(tms)-1);match=tms[ix]==a['t'][k]
        commit=np.asarray(tm['gru_committed']).astype(bool)[ix]
        by_commit={str(x):stats(norm[match&(commit==x)]) for x in [False,True] if (match&(commit==x)).any()}
        for i in sorted(set([0,int(np.argmax(norm))])):
            j=int(k[i]);portable.append({'run':meta['run'],'row':j,'sample_us':int(a['t'][j]),'phase':str(a['phase'][j]),
                'p':a['p'][[j,j+1]].tolist(),'v':a['v'][[j,j+1]].tolist(),'q':a['q'][[j,j+1]].tolist(),
                'delayed_p':a['p'][j-22].tolist(),'delayed_v':a['v'][j-22].tolist(),'delayed_r':a['rp'][j-22].tolist(),'delayed_s':a['rv'][j-22].tolist(),
                'cos_fixed_yaw':float(np.cos(a['frame_yaw0'][j])),'sin_fixed_yaw':float(np.sin(a['frame_yaw0'][j])),
                'complete_empirical_P_norm':float(norm[i]),'aux_innovation':aux[i].tolist()})
        result.append({'run':meta['run'],'role':meta['role'],'clock_modes':clock,'signed_component_ACF_NED_x':signed,'state_bins':bins,
            'event_persistence':persist,'norm_by_GRU_commit_descriptive':by_commit,'baseline_common_metric':stats(norm),
            'fixed_parameter_clock_only_diagnostic':stats(nc),'maximum_aux_reset_innovation':np.max(abs(aux),axis=0).tolist(),
            'interpretation':'clock hold creates alternating observation increments; association is not a causal decomposition of hidden memory, thrust or estimator error',
            'units':'p metres, v metres/second, q metres/second^2; P metric includes their cross terms, not q max alone'})
    write(out/'structure.json',{'runs':result,'portable_complete_metric_samples':portable,'not_a_hard_bound':True,
        'temporal_rows_not_independent_trials':True,'new_flights':0})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.input,a.output)
