#!/usr/bin/env python3
"""Check a finished P8 equivalence batch -> <batch>/equivalence.json (rule config/p8.json p8.equivalence).

A: P6-A chase x2.0 V2.0 A0 on the P8 candidate with config/p6.json (frozen p6_metrics). Equivalent when every run has the
P6 ident class (IDENT_EXCEEDED_45), its max tilt is within 2.5 deg of the P6 range [52.5, 53.2] deg, MC_RAPTOR_RREC is 0 in
the log and research_recovery has no row.
B (--b): the three P6 conditions through the P8 case path (rule p8.equivalence.b): every run accepted or a pre-registered
flight failure, the same flight outcome as the history, max tilt (frozen whole window) within 2.5 deg of the historical
range, RREC 0 and no research_recovery row; for heading 0 the generated spec (without description) and the merged
profile byte-identical (json.dumps) to P6 gap_spec of the P6 name.
"""
import argparse,json
from pathlib import Path
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[1]
TOL_DEG=2.5

def main_b(b):
    import p6_conditions,p8_conditions
    from run_experiment import p5_profile
    res=json.loads((b/'results.json').read_text());cfg=json.loads((ROOT/'config/p8.json').read_text());P6=json.loads((ROOT/'config/p6.json').read_text())
    rule=cfg['p8']['equivalence']['b'];rows=[];strip=lambda d:{k:v for k,v in d.items() if k!='description'}
    for r in res['runs']:
        run=ROOT/r['directory'];m=json.loads((run/'p8-metrics.json').read_text()) if (run/'p8-metrics.json').exists() else {}
        ref=rule['reference'][f"{r['condition']}:{r['treatment']}"];lo,hi=ref['max_tilt_deg'];res8=(m.get('p8') or {}).get('result') or {};par=(m.get('p8') or {}).get('parameters') or {}
        tilt=res8.get('max_tilt_deg');outcome=(m.get('flight_outcome') or {}).get('outcome')
        diff=None if tilt is None else (0. if lo<=tilt<=hi else (tilt-hi if tilt>hi else tilt-lo))
        spec=p8_conditions.case_spec(cfg,r['condition']);heading0=p8_conditions.parse_case(r['condition'])[1]==0.
        if heading0:
            a=p6_conditions.gap_spec(P6,ref['p6_name']);byte=json.dumps(strip(a))==json.dumps(strip(spec)) and json.dumps(strip(p5_profile(P6['p5'],a)))==json.dumps(strip(p5_profile(cfg['p5'],spec)))
        else:byte=None
        ok=bool((r.get('accepted') or r.get('flight_failure')) and outcome==ref['outcome'] and diff is not None and abs(diff)<=TOL_DEG
                and par.get('MC_RAPTOR_RREC') is not None and float(par['MC_RAPTOR_RREC'])==0. and par.get('research_recovery_rows')==0 and byte is not False)
        rows.append({'id':r['id'],'condition':r['condition'],'treatment':r['treatment'],'p6_name':ref['p6_name'],'outcome':outcome,'reference_outcome':ref['outcome'],
                     'max_tilt_deg':tilt,'reference_max_tilt_deg':ref['max_tilt_deg'],'distance_to_reference_range_deg':diff,'max_altitude_loss_m':res8.get('max_altitude_loss_m'),
                     'MC_RAPTOR_RREC':par.get('MC_RAPTOR_RREC'),'research_recovery_rows':par.get('research_recovery_rows'),'heading0_spec_and_profile_byte_identical':byte,
                     'gap_timing':((m.get('p8') or {}).get('gap_timing') or {}).get('status'),'equivalent':ok})
    eq=sum(x['equivalent'] for x in rows)
    out={'rule':rule['rule'],'tolerance_deg':TOL_DEG,'runs':rows,'equivalent':eq,'total':len(rows),'batch_status':res.get('status'),
         'status':'EQUIVALENT' if rows and eq==len(rows) and res.get('status')=='PASS' else 'NOT_EQUIVALENT'}
    (b/'equivalence.json').write_text(json.dumps(out,indent=1,ensure_ascii=False)+'\n');print(out['status'],f'{eq}/{len(rows)}',[(x['id'],x['outcome'],x['max_tilt_deg'],x['heading0_spec_and_profile_byte_identical']) for x in rows])
    return 0 if out['status']=='EQUIVALENT' else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=Path);p.add_argument('--b',action='store_true');a=p.parse_args()
    if a.b:return main_b(a.batch.resolve())
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
