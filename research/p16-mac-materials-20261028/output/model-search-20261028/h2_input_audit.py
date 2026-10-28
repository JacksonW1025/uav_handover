from pathlib import Path
import json,sys,concurrent.futures,hashlib,numpy as np,copy
from fetch_evidence import ROOT,fetch
from h2_continuation import DOCS
OLD=ROOT.parent/'offline-adjoint-20261028';rr=json.loads((OLD/'upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows']
def one(r):
 name='data/p13-20261026-formal/'+r['id']+'/analysis-v1/packed/prediction-input.json';old=OLD/'upstream'/name;p=old if old.exists() else fetch(name);d=json.loads(p.read_text());plan=d['plan'];errors=[]
 if d['initial']!={k:r['initial'][k] for k in d['initial']}:errors.append('INITIAL_MISMATCH')
 if plan['profile']!=DOCS[r['family']]['plan']['profile']:errors.append('REFERENCE_MISMATCH')
 actual=plan['windows_profile_s'];expected=[]
 if r['branch'] in ['A','AB','REPAIR']:expected.append([13.255,13.615])
 if r['branch'] in ['B','AB','REPAIR']:expected.append([13.615+r['gap_s'],13.975+r['gap_s']])
 if len(actual)!=len(expected) or (actual and np.max(abs(np.array(actual)-expected))>1e-10):errors.append('EVENT_PLAN_MISMATCH')
 if bool(plan['p12_repair'])!=(r['branch']=='REPAIR') or plan['p12_phase']!=r['phase']:errors.append('EVENT_SEMANTIC_MISMATCH')
 return dict(id=r['id'],errors=errors,input_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:results=list(ex.map(one,rr))
assert not any(r['errors'] for r in results),[r for r in results if r['errors']]
import h2_preflight as h2
h2.M=json.loads((ROOT/'h2_strict_singles.json').read_text())['model'];checks=[]
for fam in ['F2','F4']:
 r=next(r for r in rr if r['family']==fam and r['arm']=='AB-short' and r['block']==1);a,t=h2.forecast(r);s=copy.deepcopy(r);s['LP_max_loss_m']=123;s['LP_peak_tilt_deg']=179;s['censored']=not r['censored'];s['B_before']={};s['physical']={};s['prediction_summary']={};b,u=h2.forecast(s);same=bool(np.array_equal(t,u) and a['prediction']==b['prediction'] and a['predicted_tilt']==b['predicted_tilt']);assert same;checks.append(dict(id=r['id'],future_outcome_permutation_invariance=same))
(ROOT/'h2_input_audit.json').write_text(json.dumps(dict(archived_inputs_verified=len(results),cases=results,negative_control_checks=checks),indent=2));print('PASS',len(results),'inputs;',len(checks),'future-outcome permutation checks',flush=True)
