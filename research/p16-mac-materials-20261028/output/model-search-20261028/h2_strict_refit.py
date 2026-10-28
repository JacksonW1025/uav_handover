from pathlib import Path
import json,sys,time,hashlib,numpy as np
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'offline-adjoint-20261028'
sys.path.insert(0,str(OLD/'upstream/tools'));sys.path.insert(0,str(ROOT/'upstream/tools'))
from p11.fit import fit
import h2_preflight as h2
base=ROOT/'upstream/data/p11-20261025-formal';config=json.loads((ROOT/'upstream/config/p11.json').read_text());train=[r for r in config['rows'] if r['split']=='development']
original=json.loads((OLD/'upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows']
protocol={'scope':'Strict new event-combination transfer. Refit only archived P11 training groups; exclude every multi-event condition including repaired combinations and anchors. Test all P13 with pre-stream data. No outcome-dependent model choice.','variants':{'singles':['NORMAL','A','B'],'normal_only':['NORMAL']},'reference_checks':'Family reference tables identical between sampled blocks/gaps/repair. No physical COM inputs. Clock and source weights fixed from earlier engineering validation.','limitations':'Method structure designed with familiarity with all stages; this is retrospective executed holdout evidence, not prospective validation. Frozen neural controller source is available by assumption.','baseline_scope':'Give baselines the same P11 single-event trajectory outcomes and P13 single-event history. Continuous labels and censor flags separated.'}
(ROOT/'h2_strict_protocol.json').write_text(json.dumps(protocol,indent=2))
for label,branches in protocol['variants'].items():
 tr=[r for r in train if r['branch'] in branches];data=[];manifest=[]
 for r in tr:
  p=base/r['id']/'packed/measurement.npz';d=dict(np.load(p));data.append(d);doc=json.loads((base/r['id']/'packed/prediction-input.json').read_text());assert len(doc['plan']['windows_profile_s'])<=1;manifest.append(dict(id=r['id'],sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 h2.M=fit(data,'M2');print('FIT',label,h2.M,flush=True);results=[];traces={};start=time.perf_counter()
 for r in sorted(original,key=lambda x:x['id']):
  z,t=h2.forecast(r);results.append(z);traces[r['id']]=t;print(label,r['id'],round(z['prediction'],3),round(z['predicted_tilt'],2),z['stop'],flush=True)
 complete=[r for r in results if not r['actual_censored']];positive=[r for r in results if r['actual']>1];negative=[r for r in complete if r['actual']<=1]
 summary=dict(n=len(results),complete_n=len(complete),height_MAE=float(np.mean([abs(r['prediction']-r['actual']) for r in complete])),tilt_MAE=float(np.mean([abs(r['predicted_tilt']-r['actual_tilt']) for r in complete])),height_FN=sum(r['prediction']<=1 for r in positive),height_FP=sum(r['prediction']>1 for r in negative),domain_exits=sum(r['stop'] is not None for r in results),cpu_wall_s=time.perf_counter()-start)
 (ROOT/('h2_strict_'+label+'.json')).write_text(json.dumps(dict(protocol=protocol,training=manifest,model=h2.M,summary=summary,results=results),indent=2));np.savez_compressed(ROOT/('h2_strict_'+label+'_traces.npz'),**traces);print('SUMMARY',label,summary,flush=True)
