#!/usr/bin/env python3
"""Check a finished equivalence batch (new candidate, MC_RAPTOR_RINI=0) against P1 batch-02 and P0 batch-05.

Criteria are pre-registered in config/p2.json p2.equivalence. Reads run evidence only; writes equivalence.json.
"""
import argparse,glob,json
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_audit import row_of
ROOT=Path(__file__).resolve().parents[1]

def reference(batch,kind,cond):
    rows=[]
    for r in json.loads((ROOT/batch/'results.json').read_text())['runs']:
        if r['kind']==kind and r['condition']==cond:rows.append(row_of(json.loads((ROOT/r['directory']/'p1-metrics.json').read_text())))
    return rows

def entry_rows(run):
    u=ULog(str(run/'flight.ulg'),['research_memory']);m=next((d.data for d in u.data_list if d.name=='research_memory'),None)
    if m is None:return None,None
    entries=[{'px4_us':int(m['timestamp'][i]),'entry_mode':int(m['entry_mode'][i]),'entry_result':int(m['entry_result'][i]),
              'max_abs_written':float(max(abs(m[f'gru[{k}]'][i]) for k in range(16))),
              'max_abs_written_previous_action':float(max(abs(m[f'previous_action[{k}]'][i]) for k in range(4)))} for i in np.flatnonzero(m['kind']==2)]
    return entries,int(np.sum(m['teacher_forced'].astype(bool)))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);a=p.parse_args()
    batch=a.batch.resolve();spec=json.loads((ROOT/'config/p2.json').read_text())['p2']['equivalence'];tol=spec['metric_tolerance']
    results=json.loads((batch/'results.json').read_text());out=[];ok=results.get('status')=='PASS' and results.get('complete')
    for r in results['runs']:
        run=ROOT/r['directory'];row={'id':r['id'],'kind':r['kind'],'accepted':bool(r.get('accepted')),'problems':[]}
        if not row['accepted']:row['problems'].append('batch checks not accepted')
        if r['kind'].startswith('p1_'):
            m=json.loads((run/'p1-metrics.json').read_text());mine=row_of(m);ref=reference(spec['p1_reference_batch'],r['kind'],r['condition'])
            row['metrics']={}
            for k,t in tol.items():
                vals=[x[k] for x in ref];lo,hi=min(vals),max(vals);w=max(t,(hi-lo)/2)
                inside=lo-w<=mine[k]<=hi+w;row['metrics'][k]={'value':mine[k],'reference_min':lo,'reference_max':hi,'allowed':[lo-w,hi+w],'inside':inside}
                if not inside:row['problems'].append(k+' outside reference range')
            if r['kind']=='p1_c_to_n':
                row['capture']=m['reference_at_takeover'].get('classification');row['capture_state_read_matches']=m['reference_at_takeover'].get('state_read_matches_capture')
                if row['capture']!='activation_reset_hold' or not row['capture_state_read_matches']:row['problems'].append('capture not activation_reset_hold with zero velocity')
            entries,forced=entry_rows(run);row['entries']=entries;row['teacher_forced_rows']=forced
            if not entries:row['problems'].append('no research_memory entry rows')
            elif any(e['entry_mode']!=0 or e['max_abs_written']>0 or e['max_abs_written_previous_action']>0 for e in entries) or forced:row['problems'].append('RINI=0 entry not an exact original reset')
        else:
            m=json.loads((run/'metrics.json').read_text());v=json.loads((run/'validation.json').read_text())
            row['p0']={'status':v['status'],'state_values':m.get('state_values_validation',{}).get('status'),'state_log':m.get('state_log_validation',{}).get('status'),
                'recovery':m.get('joint_recovery_status_counts'),'executor':m.get('executor_acceptance')}
            refs=[json.loads(Path(d,'validation.json').read_text())['status'] for d in sorted(glob.glob(str(ROOT/f"data/prep-20261012-b05-flight-*-{r['kind']}")))]
            row['p0_reference_statuses']=sorted(set(refs))
            if row['p0']['status'] not in ['PASS','PASS_WITH_WARNINGS'] or row['p0']['state_values']!='PASS' or row['p0']['state_log']!='PASS' or row['p0']['executor']!='PASS' or row['p0']['recovery'].get('NOT_SETTLED') or row['p0']['recovery'].get('INSUFFICIENT_OBSERVATION'):
                row['problems'].append('P0 scenario verdict differs from batch-05')
        row['equivalent']=not row['problems'];ok=ok and row['equivalent'];out.append(row)
    result={'batch':str(batch.relative_to(ROOT)),'criteria':spec,'runs':out,'equivalent':bool(ok)}
    (batch/'equivalence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print('equivalent',ok)
    for r in out:print(r['id'],r['equivalent'],r['problems'])
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
