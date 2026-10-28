"""Historical local-increment transfer error scale. No P16 main/seed2 labels.
Pairs are old P13 B/AB, NORMAL template; not independent future coverage proof.
"""
import json,copy,math,time,numpy as np
from p16.common import *
from p16.greybox import OUT,legacy_fixture,parameters
from p16.analyze import prefix_truth
from p16.reuse import gate

def main():
 out=B/'reuse-calibration-history-v2';out.mkdir(exist_ok=False);rows=json.load(open(OUT/'offline-adjoint-20261028/upstream/data/p13-20261026-results-v3/cases.json'))['rows'];records={};st=time.process_time()
 for r in rows:
  if r['branch'] not in ['B','AB']:continue
  root=R/'data/p13-20261026-formal'/r['id'];run=root/'run';init=copy.deepcopy(next(x['initial'] for x in rows if x['family']==r['family'] and x['block']==r['block'] and x['branch']=='NORMAL'));pred,z=legacy_fixture(r,init,parameters());seam=pred.get('capture_ledger');sync=root/'analysis-v1/observation/synchronized.npz';meas=json.load(open(root/'analysis-v1/measured/measurement.json'));item=dict(id=r['id'],family=r['family'],G=r['gap_s'],block=r['block'],prefix=r['branch'],censored=meas['censored'],predicted_signature=pred['reuse_signature'],sync_sha256=sha(sync))
  if seam and not meas['censored']:
   events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()];epoch=next(e['run_wall_ns'] for e in events if e['event']=='p12_confirmed_native_stream_anchor');raw=np.load(sync);ts=(raw['run_wall_ns'].astype(np.int64)-epoch)/1e9;ids=np.flatnonzero(np.diff(raw['stale'].astype(int))==1)+1;ids=[i for i in ids if 13.615+r['gap_s']<=ts[i]<=13.975+r['gap_s']];actual=prefix_truth(run,raw,events,meas,epoch,float(ts[ids[0]]),float(raw['position'][ids[0],2]))['suffix'] if ids else {'available':False}
   if actual['available']:item.update(error_delta=actual['delta_loss']-pred['capture_suffix']['delta_loss'],error_tilt=actual['peak_tilt']-pred['capture_suffix']['peak_tilt'])
  records[r['id']]=item
 pairs=[]
 for b in records.values():
  if b['prefix']!='B':continue
  ab=next(x for x in records.values() if x['prefix']=='AB' and all(x[k]==b[k] for k in ['family','G','block']));passed,why=gate(b['predicted_signature'],ab['predicted_signature'])
  pair=dict(B=b['id'],AB=ab['id'],gate_pass=passed,condition=why)
  if 'error_delta' in b and 'error_delta' in ab:pair.update(transfer_height_abs=abs(b['error_delta']-ab['error_delta']),transfer_tilt_abs=abs(b['error_tilt']-ab['error_tilt']))
  pairs.append(pair)
 valid=[p for p in pairs if 'transfer_height_abs' in p];assert valid
 # Use all complete paired records, not a favorable admitted-only subpopulation.
 h=max(p['transfer_height_abs'] for p in valid);t=max(p['transfer_tilt_abs'] for p in valid);epsH=max(.05,math.ceil(h/.05)*.05);epsT=max(1.,float(math.ceil(t)))
 write(out/'records.json',records);write(out/'pairs.json',pairs);write(out/'summary.json',dict(epsilon_height=epsH,epsilon_tilt=epsT,empirical_max_height=h,empirical_max_tilt=t,complete_pairs=len(valid),all_pairs=len(pairs),predicted_gate_pass=sum(p['gate_pass'] for p in pairs),CPU_s=time.process_time()-st,scope='retrospective P13 complete matched B/AB residual differences, actual old donor capture outcomes vs prior modelcapture; P16 main data excluded; empirical interval scale not futurehardbound or exact reachability domain',source_model_sha256=sha(OUT/'model-search-20261028/h2_strict_singles.json')));print('REUSE_SCALE',epsH,epsT,len(valid),flush=True)
if __name__=='__main__':main()
