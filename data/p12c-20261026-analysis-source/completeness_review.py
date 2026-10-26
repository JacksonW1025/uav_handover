#!/usr/bin/env python3
"""Independent stricter capture/resume completeness; original seal/tools/results unchanged."""
import json,sys,hashlib
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c.features import load
P=R/'data/p12c-20261026-preparation';D=R/'data/p12c-20261026-development'
def classify(end,a,b,capture,resume):
 full=bool(end>=b+.1)
 if full:return {'status':'PASS' if capture is not None and resume is not None else 'FAIL_MISSING_EXPECTED_WITNESS','complete_coverage':True,'expected_capture':True,'expected_resume':True}
 return {'status':'OBSERVED_PREFIX' if capture is not None and resume is not None else 'NOT_REACHED_OR_RIGHT_CENSORED','complete_coverage':False,'expected_capture':False,'expected_resume':False}

def main(output):
 if output.exists():raise FileExistsError(output)
 rows=json.load(open(P/'protocol.json'))['rows'];records=[];pending=[]
 for row in rows:
  parent=D/row['id'];analysis=parent/'analysis'
  if not (parent/'result.json').exists():pending.append(row['id']);continue
  d=load(parent/'run',analysis);plan=json.load(open(analysis/'packed/prediction-input.json'))['plan'];m=json.load(open(analysis/'measured/measurement.json'));n=json.load(open(analysis/'native/native-audit.json'));epoch=float(d['run_wall_ns'][0]-d['t'][0]*1e9);end=min(float(d['t'][-1]),plan['nominal_horizon_profile_s'])
  if m.get('failure'):end=min(end,(m['failure']['monotonic_ns']-epoch)/1e9)
  events=[]
  for a,b in plan['windows_profile_s']:
   caps=[float(np.mean(c['capture_host_interval_ns'])-epoch)/1e9 for c in n['captures'] if not c['activation'] and a<=float(np.mean(c['capture_host_interval_ns'])-epoch)/1e9<b+.1 and float(np.mean(c['capture_host_interval_ns'])-epoch)/1e9<=end];fresh=np.flatnonzero((d['t']>=b)&(d['t']<=end)&d['read_valid']&~d['stale']);capture=caps[0] if len(caps)==1 else None;resume=float(d['t'][fresh[0]]) if len(fresh) else None;check=classify(end,a,b,capture,resume);events.append({'window':[a,b],'capture_count':len(caps),'capture_profile_s':capture,'first_actual_fresh_valid_read_profile_s':resume,'valid_end_s':end,**check})
  records.append({'id':row['id'],'observe':row['observe'],'censored':m['censored'],'events':events,'all_expected_witnesses':all(e['status']!='FAIL_MISSING_EXPECTED_WITNESS' for e in events)})
 all_ok=all(r['all_expected_witnesses'] for r in records);status='FAIL' if not all_ok else 'PENDING' if pending else 'PASS';doc={'schema':'p12c-completeness-review-2','status':status,'original_accept_tool_sha256':hashlib.sha256((R/'tools/p12c_platform/accept.py').read_bytes()).hexdigest(),'original_seal_preserved':True,'correction':'close potential empty timing pass; full coverage requires BOTH capture and actual fresh valid resume. Truncation/NOT_REACHED not falsely treated as missing. No new tolerance, fit, source/runtime change or flight. Normal zero planned events correctly has zero expected witnesses.','spec_sha256':hashlib.sha256((P/'noninterference-spec.json').read_bytes()).hexdigest(),'records':records,'pending':pending,'formal_release':'FORBIDDEN unless original3gates PASS AND this independent review PASS','additional_SITL_starts':0};output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(doc,indent=2)+'\n');print(status,'completed',len(records),'pending',len(pending));return doc
if __name__=='__main__':main(Path(sys.argv[1]))
