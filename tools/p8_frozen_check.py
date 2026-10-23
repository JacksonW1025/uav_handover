#!/usr/bin/env python3
"""Read-only P8 evidence audit. No model reconstruction; missing predictions stay NA.
Run: MPLCONFIGDIR=/tmp/p8-mpl uav_lab/.local/venv/bin/python tools/p8_frozen_check.py
Inputs and pre-fixed choices: data/p8-frozen-check-20261024/{plan,input-manifest}.json.
"""
import csv, hashlib, json, math, sys
from collections import Counter, defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/p8'))
import p8_space as S
OUT=ROOT/'data/p8-frozen-check-20261024'
def load(p): return json.loads((ROOT/p).read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,d): (OUT/n).write_text(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def table(n,rows):
    if not rows:return
    with (OUT/n).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,separators=(',',':')) if isinstance(v,(list,dict)) else v for k,v in row.items()})
def wilson(k,n):
    if not n:return [None,None]
    z=1.959963984540054;p=k/n;den=1+z*z/n
    a=(p+z*z/(2*n))/den;b=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [a-b,a+b]
def same(a,b):
    if isinstance(a,(list,tuple)):return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return abs(float(a)-float(b))<1e-8

def main():
    manifest=load(str(OUT.relative_to(ROOT)/'input-manifest.json'))
    for e in manifest['files']:assert sha(ROOT/e['path'])==e['sha256'],e['path']
    batches=[load(f'data/p8-20261022-batch-b{i}/results.json')['runs'] for i in [1,2]]
    runs=sum(batches,[]);assert len(runs)==900
    assert len({r['id'] for r in runs})==900 and len({r['sim_seed'] for r in runs})==900
    old=load('data/p8-20261022-batch-b2/before-budget-revision/results.json')['runs']
    assert len(old)==376 and batches[1][:376]==old
    csvrows=list(csv.DictReader((ROOT/'export/p8_b_results.csv').open()))
    csvmap={(r['campaign'],int(r['k'])):r for r in csvrows};assert len(csvrows)==len(csvmap)==900
    lists=load('tools/p8/p8_lists.json')['lists'];assert sum(map(len,lists.values()))==1080
    split={}
    for sut in ['T0','T1']:
        base=sorted([r for r in runs if r['method']=='random' and r['sut']==sut],key=lambda r:hashlib.sha256(('P8-frozen-check-v1|'+r['id']).encode()).hexdigest())
        assert len(base)==90
        split.update({r['id']:('calibration' if i<45 else 'test') for i,r in enumerate(base)})
    ledger=[];events=[];executed={};summaries={}
    for r in runs:
        c=r['case'];cfg=load(r['directory']+'/config.json');p=cfg['p2_profile'];summ=load('export/'+Path(r['directory']).name+'/summary.json');summaries[r['id']]=summ
        cr=csvmap[(r['campaign'],r['k'])]
        assert cr['name']==r['name']==S.name(c,r['sut'])==summ['name']
        assert same(S.windows(c),r['windows_s']) and same(p['gaps']['windows_s'],r['windows_s'])
        assert summ['sim_seed']==r['sim_seed'] and summ['method']==r['method'] and summ['k']==r['k']
        assert summ['reconstruction']['components_over_1e-4']==0
        for a,b,precision in [('max_tilt_deg','max_tilt_deg',.00051),('max_alt_loss_m','max_altitude_loss_m',.000051)]:assert abs(float(cr[a])-r[b])<precision
        for f in ['fail_primary','fail_task']:assert int(cr[f])==int(r[f])==int(summ[f])
        actual=[p['pre_gap_s'],p['post_gap_s']];closed=list(S.budget(c));assert same(actual,r['budget_check']['gap_spec'])
        offline=lists.get(r['campaign']);entry=offline[r['k']-1] if offline else None
        if entry:assert entry['name']==r['name'] and same(entry['windows_s'],r['windows_s']) and same([entry['case']['v'],entry['case']['heading_deg']], [c['v'],c['heading_deg']]) and same(entry['case']['durs'],c['durs']) and same(entry['case']['restored'],c['restored'])
        executed[(r['campaign'],r['k'])]=r['id']
        mismatch=not same(actual,closed)
        rec=summ['gap_timing']['gaps'];real=[]
        for i,g in enumerate(rec):
            if i+1<len(rec):real.append((rec[i+1]['last_reception_px4_us']-g['first_reception_px4_us'])/1e6)
        row=dict(id=r['id'],method=r['method'],sut=r['sut'],search_seed=r['seed'],sim_seed=r['sim_seed'],round=r['k'],stage=r['stage'],b2_segment=('preserved376' if r in old else 'continuation74') if r['stage']=='b2' else 'b1',name=r['name'],case=c,windows_s=r['windows_s'],n=len(c['durs']),speed=c['v'],heading=c['heading_deg'],planned_restored=c['restored'],realized_restored_observed=real,pre_gap_s=actual[0],post_gap_s=actual[1],closed_pre_s=closed[0],closed_post_s=closed[1],offline_list_match=bool(entry),budget_status='different_horizon_exclude_prediction_comparison' if mismatch else 'same_historical_budget_prediction_still_missing',prediction_status='missing_frozen_and_original_model',predicted_tilt='NA',original_skip='NA',split=split.get(r['id'],'evaluation_only'),tilt=r['max_tilt_deg'],alt_loss=r['max_altitude_loss_m'],tilt_fail=r['max_tilt_deg']>=45,alt_fail=r['max_altitude_loss_m']>1,primary=r['fail_primary'],task=r['fail_task'],aborted=summ['aborted'],planned_gaps=len(c['durs']),observed_gaps=len(rec),phase_any=any(.4-1e-9<=g<=.6+1e-9 for g in c['restored']),post_segment_observation='aborted_horizon_censored' if summ['aborted'] else 'completed_profile', summary='export/'+Path(r['directory']).name+'/summary.json',config=r['directory']+'/config.json')
        ledger.append(row)
        for e in summ['events']:
            state=e.get('state_at_or_after') or {}
            events.append(dict(id=r['id'],sut=r['sut'],method=r['method'],event=e['event'],gap=e.get('gap'),t_s=e['t_s'],tilt=state.get('tilt_deg'),alt_loss=state.get('alt_loss_m'),speed=state.get('v_u'),ev_u=state.get('ev_u'),a_u=state.get('a_u'),velocity_jump=e.get('velocity_jump_along_axis_m_s'),jump=e.get('jump_along_axis_m')))
    table('matching-ledger.csv',ledger);table('event-ledger.csv',events)
    offline=[]
    for camp,es in lists.items():
        for k,e in enumerate(es,1):offline.append(dict(campaign=camp,k=k,name=e['name'],case=e['case'],pre=e['pre_gap_s'],post=e['post_gap_s'],executed_id=executed.get((camp,k),'NA'),status='executed' if (camp,k) in executed else 'unexecuted_excluded_from_measured_denominator'))
    table('offline-ledger.csv',offline)
    groups=defaultdict(list)
    for r in ledger:
        for key in ['ALL',r['sut'],f"{r['sut']}/{r['method']}",f"{r['sut']}/n{r['n']}",f"{r['sut']}/{r['method']}/n{r['n']}"]:groups[key].append(r)
    stats=[]
    for key,rs in sorted(groups.items()):
        n=len(rs);row={'group':key,'n':n}
        for f in ['tilt_fail','alt_fail','primary','task']:
            k=sum(r[f] for r in rs);row.update({f:k,f+'_rate':k/n,f+'_95wilson':wilson(k,n)})
        row.update(alt_only=sum(r['alt_fail'] and not r['tilt_fail'] for r in rs),task_extra_over_primary=sum(r['task'] and not r['primary'] for r in rs),tilt_min=min(r['tilt'] for r in rs),tilt_median=sorted(r['tilt'] for r in rs)[n//2],tilt_max=max(r['tilt'] for r in rs),max_alt_loss=max(r['alt_loss'] for r in rs),prediction_n=0,spearman='NA',error='NA',underestimation='NA',skip_n='NA',skip_failure='NA',conformal_coverage='NA')
        stats.append(row)
    table('group-summary.csv',stats)
    phase=[]
    for group in ['all']+sorted({r['method'] for r in ledger})+['n2','n3','n4']+[m+'/n'+str(n) for m in sorted({r['method'] for r in ledger}) for n in [2,3,4]]:
        for exposed in [False,True]:
            rs=[r for r in ledger if r['sut']=='T0' and r['phase_any']==exposed and (group=='all' or r['method']==group or 'n'+str(r['n'])==group or r['method']+'/n'+str(r['n'])==group)]
            n=len(rs);k=sum(r['primary'] for r in rs);phase.append(dict(group=group,any_planned_restored_04_06=exposed,n=n,primary_fail=k,rate=k/n if n else None,ci95=wilson(k,n),task_fail=sum(r['task'] for r in rs)))
    table('t0-phase.csv',phase)
    expl=load('data/p8-20261023-t1-boundary/results.json')['runs'];ex=[]
    for r in expl:ex.append(dict(id=r['id'],source=r['source_id'],sim_seed=r['sim_seed'],delta=r['delta_first_restored_s'],case=r['case'],in_domain=min(r['case']['restored'])>=.1-1e-9,primary=r['fail_primary'],task=r['fail_task'],tilt=r['max_tilt_deg'],alt_loss=r['max_altitude_loss_m']))
    table('exploration-ledger.csv',ex);assert len(ex)==24 and sum(r['in_domain'] for r in ex)==18
    discrepancies=[r for r in ledger if r['closed_post_s']!=r['post_gap_s'] or r['closed_pre_s']!=r['pre_gap_s']]
    assert sum(r['primary'] for r in ledger)==432 and sum(r['task'] for r in ledger)==511
    results={'runs':900,'prediction_matches':0,'prediction_missing':900,'duplicate_identity':0,'unique_event_cases':len({r['name'] for r in ledger}),'repeated_case_groups':sum(v>1 for v in Counter(r['name'] for r in ledger).values()),'repeated_case_extra_rows':900-len({r['name'] for r in ledger}),'offline_matched_executed':sum(r['offline_list_match'] for r in ledger),'offline_unexecuted':sum(r['status'].startswith('unexecuted') for r in offline),'budget_discrepancies':[{k:r[k] for k in ['id','pre_gap_s','post_gap_s','closed_pre_s','closed_post_s','budget_status']} for r in discrepancies],'b2_preserved':376,'b2_continued':74,'primary':432,'task':511,'tilt_fail':sum(r['tilt_fail'] for r in ledger),'alt_fail':sum(r['alt_fail'] for r in ledger),'alt_only':sum(r['alt_fail'] and not r['tilt_fail'] for r in ledger),'task_extra_over_primary':sum(r['task'] and not r['primary'] for r in ledger),'exploration':{'n':24,'domain':18,'out':6,'seeds':len({r['sim_seed'] for r in ex})},'split':dict(Counter((r['sut']+'/'+r['split']) for r in ledger)),'worst_tilt':[{'id':r['id'],'tilt':r['tilt'],'alt_loss':r['alt_loss']} for r in sorted(ledger,key=lambda r:r['tilt'],reverse=True)[:10]],'worst_alt':[{'id':r['id'],'tilt':r['tilt'],'alt_loss':r['alt_loss']} for r in sorted(ledger,key=lambda r:r['alt_loss'],reverse=True)[:10]],'input_files_verified':len(manifest['files'])}
    dump('results.json',results)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    ms=['random','contest','ours','fuzz','bo']
    for ax,sut in zip(axs,['T0','T1']):
        for offset,f,label in [(-.18,'primary','Primary'),(.18,'task','Task')]:
            vals=[next(r for r in stats if r['group']==sut+'/'+m)[f]/90 for m in ms]
            ax.bar([i+offset for i in range(5)],vals,.36,label=label)
        ax.set(xticks=range(5),xticklabels=ms,ylim=(0,1.05),title=sut+' (90 measured runs per method)',ylabel='Observed failure fraction');ax.legend()
    fig.savefig(OUT/'failure-rates.png',dpi=160);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for ax,sut in zip(axs,['T0','T1']):
        for m in ms:
            rs=[r for r in ledger if r['sut']==sut and r['method']==m];ax.scatter([r['tilt'] for r in rs],[r['alt_loss'] for r in rs],s=15,alpha=.6,label=m)
        ax.axvline(45,color='k',ls='--');ax.axhline(1,color='k',ls=':');ax.set(title=sut,xlabel='Measured peak tilt (deg)',ylabel='Measured maximum altitude loss (m)');ax.legend(fontsize=8)
    fig.savefig(OUT/'tilt-altitude.png',dpi=160);plt.close(fig)
    # Protect the immutable evidence both before and after all computations.
    for e in manifest['files']:assert sha(ROOT/e['path'])==e['sha256'],e['path']
    print(json.dumps(results,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
