#!/usr/bin/env python3
"""Check a finished P4-01c equivalence batch (new candidate, MC_RAPTOR_RTGT=0) against accepted reference batches.

Criteria are pre-registered in config/p4c.json p4c.equivalence: P2 S1 N0/N2 (config/p2.json) against P2 s1a/s1b and
P4 M1 N2 (config/p4.json) against P4 01b, each metric inside [min - t, max + t] of the reference group, plus the P2
evidence and the takeover-target evidence of the new candidate (RTGT=0 in force, research_target activation capture
with mode 0 and zero target velocity, no profile rows). Reads run evidence only; writes equivalence.json.
"""
import argparse,json
from pathlib import Path
import numpy as np
from pyulog import ULog
from p1_audit import row_of
from p3_equivalence import reference,inside
ROOT=Path(__file__).resolve().parents[1]

def target_evidence(run,t_c):
    u=ULog(str(run/'flight.ulg'),['research_target']);tg=next((d.data for d in u.data_list if d.name=='research_target'),None)
    out={'MC_RAPTOR_RTGT':u.initial_parameters.get('MC_RAPTOR_RTGT'),'changed':[(int(t),n,v) for t,n,v in u.changed_parameters if n in ('MC_RAPTOR_RTGT','MC_RAPTOR_RTDEC')]}
    if tg is None:return {**out,'ok':False,'problem':'research_target missing'}
    t=np.asarray(tg['timestamp'],np.int64);caps=np.flatnonzero((tg['kind']==1)&(tg['activation']==1)&(np.abs(t-t_c)<=50000))
    out['activation_captures_at_change']=int(len(caps));out['profile_rows']=int((tg['kind']==2).sum())
    if len(caps)==1:
        i=caps[0];out.update({'capture_mode':int(tg['mode'][i]),'capture_target_velocity':[float(tg[f'velocity[{k}]'][i]) for k in range(3)]})
    out['ok']=bool(out['MC_RAPTOR_RTGT']==0 and not out['changed'] and len(caps)==1 and out['capture_mode']==0 and max(map(abs,out['capture_target_velocity']))==0 and out['profile_rows']==0)
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);p.add_argument('--config',default='config/p4c.json');a=p.parse_args()
    batch=a.batch.resolve();spec=json.loads((ROOT/a.config).read_text())['p4c']['equivalence'];tol=spec['metric_tolerance']
    results=json.loads((batch/'results.json').read_text());out=[];ok=results.get('status')=='PASS' and bool(results.get('complete'))
    for r in results['runs']:
        run=ROOT/r['directory'];row={'id':r['id'],'kind':r['kind'],'condition':r['condition'],'treatment':r['treatment'],'accepted':bool(r.get('accepted')),'problems':[]}
        if not row['accepted']:row['problems'].append('batch checks not accepted')
        m=json.loads((run/'p2-metrics.json').read_text());mine=row_of(m)
        ref=reference(spec['reference'][r['condition']],r['kind'],r['condition'],r['treatment']);row['reference_runs']=len(ref)
        row['reference_batches']=spec['reference'][r['condition']]
        if not ref:row['problems'].append('no reference runs')
        row['metrics']={}
        for k,t in tol.items():
            row['metrics'][k]=inside(mine[k],[x[0][k] for x in ref],t)
            if not row['metrics'][k]['inside']:row['problems'].append(k+' outside the reference range')
        if r['treatment']=='N2':
            row['metrics']['gru_norm_written']=inside(m['entry']['gru_norm_written'],[x[1]['entry']['gru_norm_written'] for x in ref],0.05)
            if not row['metrics']['gru_norm_written']['inside']:row['problems'].append('written GRU norm outside the reference range')
        row['evidence']={'entry':m['entry']['status'],'teacher_forcing':m['teacher_forcing']['status'],'capture':m['reference_at_takeover'].get('classification'),
                         'capture_state_read_matches':m['reference_at_takeover'].get('state_read_matches_capture')}
        if row['evidence']['entry']!='VERIFIED' or row['evidence']['teacher_forcing']!='VERIFIED':row['problems'].append('P2 treatment evidence not VERIFIED')
        if row['evidence']['capture']!='activation_reset_hold' or not row['evidence']['capture_state_read_matches']:row['problems'].append('capture not activation_reset_hold with zero velocity')
        row['target_evidence']=target_evidence(run,m['change_px4_us'])
        if not row['target_evidence']['ok']:row['problems'].append('takeover target evidence: RTGT=0 zero-velocity capture not confirmed')
        row['equivalent']=not row['problems'];ok=ok and row['equivalent'];out.append(row)
    result={'batch':str(batch.relative_to(ROOT)),'criteria_config':a.config,'criteria':spec,'runs':out,'equivalent':bool(ok)}
    (batch/'equivalence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print('equivalent',ok)
    for r in out:print(r['id'],r['equivalent'],r['problems'])
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
