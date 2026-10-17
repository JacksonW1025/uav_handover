#!/usr/bin/env python3
"""Check a finished P5 equivalence batch (new candidate with MC_RAPTOR_RTGT=2 added) against existing runs.

Criteria are pre-registered in config/p5.json p5.equivalence: P4 M1 N2 (config/p4.json, RTGT=0 default) against every
run of the identical condition in completed formal batches (01b M1 N2 + 01c V1.0 T0) and P4-01c V1.0 T1 (config/p4c.json,
RTGT=1) against 01c V1.0 T1; each metric inside [min - t, max + t], t = max(tolerance, half the reference spread);
written GRU norm inside the reference range (+-0.05); P2 entry and teacher-forcing evidence VERIFIED; M1: RTGT=0 in force,
activation capture with mode 0 and zero target velocity, no profile rows; V1.0 T1: p4c target evidence VERIFIED (mode 1).
Reads run evidence only; writes equivalence.json.
"""
import argparse,json
from pathlib import Path
from p1_audit import row_of
from p3_equivalence import inside
from p4c_equivalence import target_evidence
ROOT=Path(__file__).resolve().parents[1]

def reference(entries):
    rows=[]
    for batch,kind,cond,treat in entries:
        for r in json.loads((ROOT/batch/'results.json').read_text())['runs']:
            if (r['kind'],r['condition'],r['treatment'])==(kind,cond,treat) and r.get('accepted'):
                m=json.loads((ROOT/r['directory']/'p2-metrics.json').read_text());rows.append((row_of(m),m,r['directory']))
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);p.add_argument('--config',default='config/p5.json');a=p.parse_args()
    batch=a.batch.resolve();spec=json.loads((ROOT/a.config).read_text())['p5']['equivalence'];tol=spec['metric_tolerance']
    results=json.loads((batch/'results.json').read_text());out=[];ok=results.get('status')=='PASS' and bool(results.get('complete'))
    for r in results['runs']:
        run=ROOT/r['directory'];key=f"{r['condition']}:{r['treatment']}"
        row={'id':r['id'],'kind':r['kind'],'condition':r['condition'],'treatment':r['treatment'],'config':r['config'],'accepted':bool(r.get('accepted')),'problems':[]}
        if not row['accepted']:row['problems'].append('batch checks not accepted')
        if not (run/'p2-metrics.json').exists():row['problems'].append('p2-metrics.json missing');row['equivalent']=False;ok=False;out.append(row);continue
        m=json.loads((run/'p2-metrics.json').read_text());mine=row_of(m)
        ref=reference(spec['reference'][key]);row['reference_runs']=[x[2] for x in ref]
        if not ref:row['problems'].append('no reference runs')
        row['metrics']={}
        for k,t in tol.items():
            row['metrics'][k]=inside(mine[k],[x[0][k] for x in ref],t)
            if not row['metrics'][k]['inside']:row['problems'].append(k+' outside the reference range')
        row['metrics']['gru_norm_written']=inside(m['entry']['gru_norm_written'],[x[1]['entry']['gru_norm_written'] for x in ref],0.05)
        if not row['metrics']['gru_norm_written']['inside']:row['problems'].append('written GRU norm outside the reference range')
        row['evidence']={'entry':m['entry']['status'],'teacher_forcing':m['teacher_forcing']['status'],'capture':m['reference_at_takeover'].get('classification'),
                         'capture_state_read_matches':m['reference_at_takeover'].get('state_read_matches_capture')}
        if row['evidence']['entry']!='VERIFIED' or row['evidence']['teacher_forcing']!='VERIFIED':row['problems'].append('P2 treatment evidence not VERIFIED')
        if r['treatment']=='N2':
            if row['evidence']['capture']!='activation_reset_hold' or not row['evidence']['capture_state_read_matches']:row['problems'].append('capture not activation_reset_hold with zero velocity')
            row['target_evidence']=target_evidence(run,m['change_px4_us'])
            if not row['target_evidence']['ok']:row['problems'].append('takeover target evidence: RTGT=0 zero-velocity capture not confirmed')
        else:
            c=json.loads((run/'p4c-metrics.json').read_text()) if (run/'p4c-metrics.json').exists() else {}
            tg=c.get('target') or {};row['target_evidence']={'status':tg.get('status'),'capture_mode':(tg.get('capture') or {}).get('mode'),'initial_target_speed_m_s':tg.get('initial_target_speed_m_s')}
            if tg.get('status')!='VERIFIED' or row['target_evidence']['capture_mode']!=1 or row['evidence']['capture']!='activation_speed_matched':row['problems'].append('T1 (RTGT=1) target evidence not VERIFIED')
        row['equivalent']=not row['problems'];ok=ok and row['equivalent'];out.append(row)
    result={'batch':str(batch.relative_to(ROOT)),'criteria_config':a.config,'criteria':spec,'runs':out,'equivalent':bool(ok)}
    (batch/'equivalence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print('equivalent',ok)
    for r in out:print(r['id'],r['equivalent'],r['problems'])
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
