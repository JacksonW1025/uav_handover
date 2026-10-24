"""Read-only per-run costs; unique output, no censoring imputation."""
import argparse,csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import write,sha
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=False)
rp=ROOT/'data/p9-20261024-continuation-v1-report-stopped-v1/prediction-measurement-ledger.csv'
rows=[];inputs={str(rp.relative_to(ROOT)):sha(rp),str(Path(__file__).resolve().relative_to(ROOT)):sha(Path(__file__))}
for r in csv.DictReader(rp.open()):
    if r['stage']!='D':continue
    path=ROOT/r['evidence_directory']/'run/p9-metrics.json';m=json.loads(path.read_text());inputs[str(path.relative_to(ROOT))]=sha(path)
    last=next((x for x in m['recoveries'] if x['index']==m['planned_interruptions']-1),{})
    rows.append({'id':r['id'],'arm':r['treatment'],'cluster':r['cluster'],'complete_window':m['complete_window'],'max_tilt_deg':m['max_tilt_deg'],'max_altitude_loss_m':m['max_altitude_loss_m'],'max_lag_m':m['max_lag_m'],'max_horizontal_distance_m':m['max_horizontal_distance_m'],'integrated_abs_lag_m_s':m['integrated_abs_lag_m_s'],'final_resume_observed':bool(last),'final_catch_up_s':last.get('vehicle_catch_up_10s_s'),'final_catch_up_censored':last.get('vehicle_catch_up_censored',True),'final_lag_at_6s_m':last.get('lag_at_6s_m'),'cost_outcome':m['final_task_cost_outcome'],'task_outcome':m['task_outcome']})
with (a.output/'D-task-costs.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
ranges={}
for arm in ['P9-Z','P9-C','P9-R','P9-CR']:
    rr=[r for r in rows if r['arm']==arm];ranges[arm]={'n':len(rr),'complete_windows':sum(r['complete_window'] for r in rr)}
    for k in ['max_tilt_deg','max_altitude_loss_m','max_lag_m','max_horizontal_distance_m','integrated_abs_lag_m_s','final_catch_up_s','final_lag_at_6s_m']:
        vals=[r[k] for r in rr if r[k] is not None];ranges[arm][k]={'observed_n':len(vals),'range':[min(vals),max(vals)] if vals else None,'censored_peaks_are_lower_bounds':k.startswith('max_')}
write(a.output/'arm-ranges.json',ranges);write(a.output/'input-manifest.json',inputs);write(a.output/'output-manifest.json',{p.name:sha(p) for p in a.output.iterdir() if p.is_file() and p.name!='output-manifest.json'})
print(json.dumps(ranges,ensure_ascii=False))
