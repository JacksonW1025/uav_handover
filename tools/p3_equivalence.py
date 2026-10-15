#!/usr/bin/env python3
"""Check a finished P3 equivalence batch (new candidate, P2 kinds and config) against the accepted P2 S1 batches.

Criteria are pre-registered in config/p3.json p3.equivalence. Reads run evidence only; writes equivalence.json.
"""
import argparse,json
from pathlib import Path
from p1_audit import row_of
ROOT=Path(__file__).resolve().parents[1]

def reference(batches,kind,cond,treat):
    rows=[]
    for b in batches:
        for r in json.loads((ROOT/b/'results.json').read_text())['runs']:
            if r['kind']==kind and r['condition']==cond and r['treatment']==treat:
                m=json.loads((ROOT/r['directory']/'p2-metrics.json').read_text());rows.append((row_of(m),m))
    return rows

def inside(value,ref,t):
    lo,hi=min(ref),max(ref);w=max(t,(hi-lo)/2);return {'value':value,'reference_min':lo,'reference_max':hi,'allowed':[lo-w,hi+w],'inside':lo-w<=value<=hi+w}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);a=p.parse_args()
    batch=a.batch.resolve();spec=json.loads((ROOT/'config/p3.json').read_text())['p3']['equivalence'];tol=spec['metric_tolerance']
    results=json.loads((batch/'results.json').read_text());out=[];ok=results.get('status')=='PASS' and results.get('complete')
    for r in results['runs']:
        run=ROOT/r['directory'];row={'id':r['id'],'kind':r['kind'],'treatment':r['treatment'],'accepted':bool(r.get('accepted')),'problems':[]}
        if not row['accepted']:row['problems'].append('batch checks not accepted')
        m=json.loads((run/'p2-metrics.json').read_text());mine=row_of(m)
        # N0 reference: both accepted S1 batches; N2: batch s1a (the only S1 batch with N2).
        ref=reference(spec['reference_batches'],r['kind'],r['condition'],r['treatment']);row['reference_runs']=len(ref)
        if not ref:row['problems'].append('no P2 reference runs')
        row['metrics']={}
        for k,t in tol.items():
            row['metrics'][k]=inside(mine[k],[x[0][k] for x in ref],t)
            if not row['metrics'][k]['inside']:row['problems'].append(k+' outside the P2 range')
        if r['treatment']=='N2':
            row['metrics']['gru_norm_written']=inside(m['entry']['gru_norm_written'],[x[1]['entry']['gru_norm_written'] for x in ref],0.05)
            if not row['metrics']['gru_norm_written']['inside']:row['problems'].append('written GRU norm outside the P2 range')
        row['evidence']={'entry':m['entry']['status'],'teacher_forcing':m['teacher_forcing']['status'],'capture':m['reference_at_takeover'].get('classification'),
                         'capture_state_read_matches':m['reference_at_takeover'].get('state_read_matches_capture')}
        if row['evidence']['entry']!='VERIFIED' or row['evidence']['teacher_forcing']!='VERIFIED':row['problems'].append('P2 treatment evidence not VERIFIED')
        if row['evidence']['capture']!='activation_reset_hold' or not row['evidence']['capture_state_read_matches']:row['problems'].append('capture not activation_reset_hold with zero velocity')
        row['equivalent']=not row['problems'];ok=ok and row['equivalent'];out.append(row)
    result={'batch':str(batch.relative_to(ROOT)),'criteria':spec,'runs':out,'equivalent':bool(ok)}
    (batch/'equivalence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print('equivalent',ok)
    for r in out:print(r['id'],r['equivalent'],r['problems'])
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
