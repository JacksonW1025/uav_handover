#!/usr/bin/env python3
"""Check a finished P8 equivalence batch -> <batch>/equivalence.json (rule config/p8.json p8.equivalence).

A: P6-A chase x2.0 V2.0 A0 on the P8 candidate with config/p6.json (frozen p6_metrics). Equivalent when every run has the
P6 ident class (IDENT_EXCEEDED_45), its max tilt is within 2.5 deg of the P6 range [52.5, 53.2] deg, MC_RAPTOR_RREC is 0 in
the log and research_recovery has no row.
"""
import argparse,json
from pathlib import Path
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[1]
TOL_DEG=2.5

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);a=p.parse_args()
    b=a.batch.resolve();res=json.loads((b/'results.json').read_text());rule=json.loads((ROOT/'config/p8.json').read_text())['p8']['equivalence']['a']
    ref=rule['reference'];lo,hi=ref['max_tilt_deg'];rows=[]
    for r in res['runs']:
        run=ROOT/r['directory'];m=json.loads((run/'p6-metrics.json').read_text()) if (run/'p6-metrics.json').exists() else {}
        u=ULog(str(run/'flight.ulg'),['research_recovery']) if (run/'flight.ulg').exists() else None
        vals={} if u is None else dict(u.initial_parameters)
        if u is not None:
            for _,n,v in sorted(u.changed_parameters,key=lambda x:x[0]):vals[n]=v
        rec=0 if u is None else sum(len(d.data['timestamp']) for d in u.data_list if d.name=='research_recovery')
        cls=(m.get('ident_outcome') or {}).get('class');tilt=(m.get('tilt') or {}).get('max_tilt_deg')
        diff=None if tilt is None else (0. if lo<=tilt<=hi else (tilt-hi if tilt>hi else tilt-lo))
        ok=bool(r.get('accepted') and cls==ref['class'] and diff is not None and abs(diff)<=TOL_DEG and vals.get('MC_RAPTOR_RREC') is not None and float(vals['MC_RAPTOR_RREC'])==0. and rec==0)
        rows.append({'id':r['id'],'accepted':r.get('accepted'),'class':cls,'max_tilt_deg':tilt,'distance_to_reference_range_deg':diff,'MC_RAPTOR_RREC':vals.get('MC_RAPTOR_RREC'),
                     'research_recovery_rows':rec,'max_altitude_loss_m':(m.get('whole') or {}).get('max_altitude_loss_m'),'equivalent':ok})
    eq=sum(x['equivalent'] for x in rows)
    out={'rule':rule['rule'],'reference':ref,'tolerance_deg':TOL_DEG,'runs':rows,'equivalent':eq,'total':len(rows),'status':'EQUIVALENT' if rows and eq==len(rows) else 'NOT_EQUIVALENT'}
    (b/'equivalence.json').write_text(json.dumps(out,indent=1,ensure_ascii=False)+'\n');print(out['status'],f'{eq}/{len(rows)}',[(x['id'],x['class'],x['max_tilt_deg']) for x in rows])
    return 0 if out['status']=='EQUIVALENT' else 1
if __name__=='__main__':raise SystemExit(main())
