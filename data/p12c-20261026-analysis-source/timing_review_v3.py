#!/usr/bin/env python3
"""Add required-witness/timing evidence to v2 partial gate; never promotes release."""
import json,sys,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[2];P=R/'data/p12c-20261026-preparation'
def main(out):
 if out.exists():raise FileExistsError(out)
 base=json.load(open(P/'acceptance-partial-v2.json'));w=json.load(open(P/'completeness-final.json'));index={r['id']:r for r in w['records']};limit=json.load(open(P/'noninterference-spec.json'))['dynamic_scales']['capture_resume_time_s'];timings=[];failed=[]
 for pair in base['pairs']:
  if pair['status']!='COMPARED_ALL_VALID':continue
  left=index[pair['off']]['events'];right=index[pair['on']]['events'];checks=[]
  assert len(left)==len(right)
  for a,b in zip(left,right):
   assert a['window']==b['window']
   for key in ['capture_profile_s','first_actual_fresh_valid_read_profile_s']:
    both=a[key] is not None and b[key] is not None
    if both:status='PASS' if abs(a[key]-b[key])<=limit else 'FAIL_TIMING_SCALE'
    elif a['complete_coverage'] and b['complete_coverage']:status='FAIL_MISSING_EXPECTED_WITNESS'
    else:status='NOT_COMPARABLE_CENSORED_OR_NOT_REACHED'
    checks.append({'window':a['window'],'field':key,'off':a[key],'on':b[key],'difference_s':abs(a[key]-b[key]) if both else None,'status':status})
  if any(c['status'].startswith('FAIL') for c in checks):failed.append(f"{pair['class']}-b{pair['block']}")
  timings.append({'class':pair['class'],'block':pair['block'],'checks':checks,'zero_events':'NORMAL has genuinely no planned interruption' if not checks else None})
 doc={'schema':'p12c-engineering-supplement-v3','engineering_status':'NOT_RELEASED','base_review_sha256':hashlib.sha256((P/'acceptance-partial-v2.json').read_bytes()).hexdigest(),'completeness_sha256':hashlib.sha256((P/'completeness-final.json').read_bytes()).hexdigest(),'original_seal_source_unchanged':True,'hard_semantics':base['hard_semantics'],'dynamic_effect':base['dynamic_effect'],'evidence_sufficiency':base['evidence_sufficiency'],'timing_checks':timings,'failed_timing_pairs':failed,'empty_timing_cannot_pass_an_expected_event':True,'formal':'NOT_CREATED;24 unstarted; no revised cutoff or replay replaces the6.47deg fail','starts':{'preparation':10,'formal':0,'old':56,'cumulative':66},'new_SITL':0};out.write_text(json.dumps(doc,indent=2)+'\n');print('RELEASE NOT_PASSED','timing_failures',failed)
if __name__=='__main__':main(Path(sys.argv[1]))
