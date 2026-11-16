from pathlib import Path
import sys,json,csv
import numpy as np
from pyulog import ULog
P=Path(__file__).parent;R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from output_chain import read_trace
out=[]
for r in json.loads((P/'raw-audit.json').read_text())['delivery']:
 run=Path(r['run']);pub=r['first_publication_us'];first_apply=r['motors'][0]['window'][next(i for i,v in enumerate(r['motors'][0]['window']) if v['owner']==[1])]['sim_us']
 u=ULog(str(run/'flight.ulg'),message_name_filter_list=['actuator_motors','research_actuator','research_output'])
 o=u.get_dataset('research_actuator').data;a=u.get_dataset('actuator_motors').data;b=u.get_dataset('research_output').data
 pubs=[int(o['actuator_timestamp'][i]) for i in range(len(o['timestamp'])) if o['owner'][i]==1 and pub<=o['actuator_timestamp'][i]<first_apply]
 sids=[]
 for ts in pubs:
  ai=np.flatnonzero(a['timestamp']==ts);assert len(ai)==1;sids.append(int(a['timestamp_sample'][ai[0]]))
 log=list(csv.DictReader((run/'relay.csv').open()))
 motors=[read_trace(f)[1] for f in sorted((run/'gz-motor').glob('*.bin'))]
 detail=[]
 for sid in sorted(set(sids)):
  ev=[x for x in log if int(x['sample_us'])==sid and x['event'] in ['source','held','forward','release_latest']]
  applied=[bool(np.any(t['applied_sample_us']==sid)) for t in motors]
  released=any(e['event'] in ['forward','release_latest'] for e in ev)
  detail.append({'sample_us':sid,'events':[e['event'] for e in ev],'relay_source_monotonic_ns':[int(e['wall_ns']) for e in ev if e['event']=='source'],'relay_forward_monotonic_ns':[int(e['wall_ns']) for e in ev if e['event'] in ['forward','release_latest']],'four_applied':applied,'classification':'applied' if all(applied) else ('forwarded_but_not_applied' if released else 'held_then_superseded_in_relay')})
 rel=next(x for x in log if x['event']=='release_latest')
 active=next(x for x in r['events'] if x['event']=='t4_fresh_active_observed')
 begin=next(x for x in log if x['event']=='window_begin')
 out.append({'run':run.parent.name,'first_N_native_us':pub,'first_N_apply_native_us':first_apply,'relay_release_clock_snapshot_us':int(rel['sim_us']),'relay_clock_release_minus_first_N_ms':(int(rel['sim_us'])-pub)/1000,'host_active_observed_ns':active['received_ns'],'host_release_ns':int(rel['wall_ns']),'host_release_minus_active_ms':(int(rel['wall_ns'])-active['received_ns'])/1e6,'actual_hold_clock_ms':(int(rel['sim_us'])-int(begin['sim_us']))/1000,'native_neural_publications_before_first_apply':len(pubs),'unique_samples':len(set(sids)),'sample_details':detail})
(P/'sample-accounting.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
