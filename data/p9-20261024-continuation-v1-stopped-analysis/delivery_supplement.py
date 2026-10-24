#!/usr/bin/env python3
"""Read-only stopped-batch accounting and planned-segment diagnostics, new output."""
import csv,json,sys,hashlib,subprocess
from pathlib import Path
from datetime import datetime
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write
from p1_metrics import tilt_deg

def main():
    here=Path(__file__).resolve().parent;out=here/'delivery-supplement';out.mkdir(exist_ok=False)
    report=ROOT/'data/p9-20261024-continuation-v1-report-stopped-v1';plots=ROOT/'data/p9-20261024-continuation-v1-postanalysis-stopped-v1'
    ledger_path=ROOT/'data/p9-20261024-preparation/attempts.jsonl'
    ledger=[json.loads(x) for x in ledger_path.read_text().splitlines()]
    starts=[x for x in ledger if x['event']=='START_INTENT' and x['budget_class']=='formal'];ends={x['id']:x for x in ledger if x['event']=='FINISH'}
    rows=list(csv.DictReader((report/'prediction-measurement-ledger.csv').open()));measure={r['id']:r for r in rows}
    assert len(starts)==162 and len(measure)==160
    accounting=[];inputs={};prediction_s=0.
    for s in starts:
        attempt=ROOT/s['output'];before=attempt/'prediction-before-query.json';b=json.loads(before.read_text());inputs[str(before.relative_to(ROOT))]=sha(before)
        prediction_s+=b['row'].get('prediction_compute_s',0.)
        r=measure.get(s['id']);state='FROZEN_MEASURED' if r else ('ORIGINAL_INFRA_MISSING' if s['attempt_number']==102 else 'FLIGHT_FAILURE_FROZEN_ANALYSIS_EXCEPTION')
        accounting.append({'attempt_number':s['attempt_number'],'id':s['id'],'stage':s['stage'],'seed':s['seed'],'state':state,'prediction_before_path':str(before.relative_to(ROOT)),'prediction_sha256':sha(before),'predicted_tilt_deg':b['prediction']['point_tilt_deg'],'predicted_altitude_loss_m':None,'overall_skip':b['prediction']['overall_skip'],'overall_decision':b['prediction']['overall_decision'],'frozen_observed_tilt_deg':r['observed_tilt_deg'] if r else None,'frozen_primary_failure':r['primary_failure'] if r else (True if s['attempt_number']==162 else None),'finished_time':ends.get(s['id'],{}).get('time'),'diagnostic_scope':'attempt162: P7 primary FAILURE is recorded, P9 fixed-window result absent; diagnostic values stored separately' if s['attempt_number']==162 else ''})
    with (out/'all-162-starts.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(accounting[0]));w.writeheader();w.writerows(accounting)
    checks={}
    for d,commit in [('data/p9-20261024-freeze','6a0292e4d7259f9396d5dad08486eb9e2a743427'),('data/p9-20261024-continuation-v1-freeze','95f424bafd040214dd834fb2737d29986c54913a')]:
        m=json.loads((ROOT/d/'manifest.json').read_text());bad=[]
        for p,h in m['files'].items():
            blob=subprocess.check_output(['git','show',commit+':'+p],cwd=ROOT)
            if sha(ROOT/p)!=h or hashlib.sha256(blob).hexdigest()!=h:bad.append(p)
        checks[d]={'files_checked':len(m['files']),'manifest_sha256':sha(ROOT/d/'manifest.json'),'commit':commit,'drift':bad}
    assert not any(c['drift'] for c in checks.values())
    prior=(ROOT/'data/p9-20261024-continuation-v1-freeze/prior-ledger.jsonl').read_bytes()
    assert ledger_path.read_bytes().startswith(prior)
    segments=[]
    for r in rows:
        if r['stage']!='D':continue
        run=ROOT/r['evidence_directory']/'run';m=json.loads((run/'p9-metrics.json').read_text());cfg=json.loads((run/'config.json').read_text())
        u=ULog(str(run/'flight.ulg'),['vehicle_local_position','vehicle_attitude']);t={d.name:d.data for d in u.data_list if d.multi_id==0}
        t0=m['clock_origin_native_us'];lp=t['vehicle_local_position'];lt=(np.array(lp['timestamp_sample'],float)-t0)/1e6
        z0=np.interp(0.,lt,lp['z']);at=(np.array(t['vehicle_attitude']['timestamp'],float)-t0)/1e6
        theta=tilt_deg(np.column_stack([t['vehicle_attitude'][f'q[{i}]'] for i in range(4)]))
        end=m['window_observed_s'][1];w=(at>=0)&(at<=min(16.,end));assert abs(float(theta[w].max())-m['max_tilt_deg'])<1e-6
        w=(lt>=0)&(lt<=16.);assert abs(max(0.,float((lp['z'][w]-z0).max()))-m['max_altitude_loss_m'])<1e-6
        gaps=json.loads(r['windows_s']);offset=float(cfg['p2_profile']['pre_gap_s'])-1.
        for i,(a,b) in enumerate(gaps):
            a+=offset;finish=offset+gaps[i+1][0] if i+1<len(gaps) else 16.
            aw=(at>=a)&(at<min(finish,end));zw=(lt>=a)&(lt<min(finish,end))
            obs='NOT_REACHED' if end<a else ('COMPLETE' if end>=finish-.02 else 'CENSORED')
            peak=float(theta[aw].max()) if aw.any() else None;loss=max(0.,float((lp['z'][zw]-z0).max())) if zw.any() else None
            segments.append({'id':r['id'],'arm':r['treatment'],'cluster':r['cluster'],'planned_segment_index':i,'planned_start_from_base_s':a,'planned_end_from_base_s':finish,'observation':obs,'peak_tilt_deg':peak,'global_baseline_altitude_loss_m':loss,'observed_tilt_ge45':None if peak is None else peak>=45.,'observed_altitude_gt1':None if loss is None else loss>1.})
        for p in [run/'flight.ulg',run/'p9-metrics.json',run/'config.json']:inputs[str(p.relative_to(ROOT))]=sha(p)
    with (out/'D-planned-segment-risks.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(segments[0]));w.writeheader();w.writerows(segments)
    diagnostic=json.loads((here/'attempt162-diagnostic/p9-open-gap-diagnostic.json').read_text())
    x162=next(x for x in starts if x['attempt_number']==162);exception=next(x for x in ledger if x['event']=='INTERRUPTED_OR_EXCEPTION' and x['id']==x162['id'])
    write(out/'delivery-assessment.json',{'status':'INCOMPLETE_NO_OVERALL_PASS','development_starts':10,'formal_starts':162,'formal_completed_frozen_measurements':160,'original_epoch':{'starts':102,'frozen_results':101,'whole_audit':'FAIL'},'continuation_epoch':{'starts':60,'completed_frozen_results':59,'whole_audit':'FAIL','individual_raw_remeasurements_pass':59,'unstarted_original_rows':11},'original_missing102':True,'new_attempt162':{'primary_flight_failure':True,'frozen_p9_analyzer_exception':True,'diagnostic_only_peak_tilt_deg':diagnostic['max_tilt_deg'],'diagnostic_observed_s':diagnostic['window_observed_s'],'counted_as_completed_frozen_measurement':False,'start_to_exception_wall_s':(datetime.fromisoformat(exception['time'])-datetime.fromisoformat(x162['time'])).total_seconds()},'unspent_search_slots':7,'remaining_unstarted_D':11,'continuation_formal_cap':173,'original_formal_cap':180,'frozen_input_verification':checks,'ledger_prior_prefix_identical':True,'all_162_before_query_prediction_compute_s':prediction_s,'report_generator_corrections':['root results.json continuation_epoch.started field uses completed row count59; actual START_INTENT count60, explicitly corrected here','root results.json original_epoch.infra_missing1 does not include new attempt162 analysis exception; both enumerated here','nominal bootstrap n1 intervals are degenerate resamples, not valid population confidence intervals; do not cite as precision'],'D_planned_segments_scope':'post-flight diagnostic intervals at planned event starts through next planned start; global P9 altitude baseline, not P7 local baseline; no missing tail imputed','no_third_batch':'continuation plan forbids automatic third batch; simulations remain stopped, no retries'})
    import matplotlib
    matplotlib.use('Agg');import matplotlib.pyplot as plt
    arms=['P9-Z','P9-C','P9-R','P9-CR'];dr=[r for r in rows if r['stage']=='D'];fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for ax,key,label,limit in [(axes[0,0],'observed_tilt_deg','Peak tilt (deg)',45),(axes[0,1],'observed_altitude_loss_m','Altitude loss (m)',1),(axes[1,0],'max_lag_m','Maximum lag (m)',4.5)]:
        for k,c in enumerate(sorted({r['cluster'] for r in dr})):
            rr=[next(r for r in dr if r['cluster']==c and r['treatment']==a) for a in arms];x=np.arange(4)+(k-2.5)*.018;y=[float(r[key]) for r in rr]
            ax.plot(x,y,color='0.8',lw=.7)
            for xi,yi,r in zip(x,y,rr):ax.scatter(xi,yi,color=f'C{k}',marker='o' if r['full_horizon_comparable']=='True' else '^',s=25)
        ax.set(xticks=range(4),xticklabels=arms,ylabel=label);ax.axhline(limit,color='black',lw=.7)
    ax=axes[1,1];bottom=np.zeros(4)
    for outcome,label,color in [('SUCCESS','Cost success','#009E73'),('FAILURE','Cost failure','#D55E00'),('CENSORED','Censored','#E69F00'),('UNOBSERVED_FINAL_RESUME','Final resume unobserved','#999999')]:
        y=np.array([sum(r['treatment']==a and r['final_task_cost_outcome']==outcome for r in dr) for a in arms]);ax.bar(range(4),y,bottom=bottom,label=label,color=color);bottom+=y
    ax.set(xticks=range(4),xticklabels=arms,ylabel='Completed paired clusters (n=6)');ax.legend(fontsize=8)
    fig.suptitle('D partial: six of nine planned clusters; 11 arms not run, attempt162 diagnostic separate\nTriangles: censored lower bounds; absent final resume never counted as recovery',fontsize=11)
    fig.savefig(out/'D-repair-and-task-cost-reviewed.png',dpi=180);fig.savefig(out/'D-repair-and-task-cost-reviewed.pdf');plt.close(fig)
    for p in [ledger_path,report/'results.json',report/'prediction-measurement-ledger.csv',here/'attempt162-diagnostic/p9-open-gap-diagnostic.json',Path(__file__).resolve()]:inputs[str(p.relative_to(ROOT))]=sha(p)
    write(out/'input-manifest.json',inputs);write(out/'output-manifest.json',{str(p.relative_to(out)):sha(p) for p in out.iterdir() if p.is_file() and p.name!='output-manifest.json'})
    print('SUPPLEMENT',len(accounting),'attempts;',len(segments),'planned D segments; all frozen86 checks pass')
if __name__=='__main__':main()
