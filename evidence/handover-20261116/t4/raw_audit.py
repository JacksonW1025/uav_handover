from pathlib import Path
import sys,json,time,hashlib
import numpy as np
from pyulog import ULog
R=Path('/home/car/uav_handover');P=Path(__file__).parent
sys.path.insert(0,str(R/'tools'))
from output_chain import read_trace
start=time.monotonic();out={'execution_host':'Thor','source':'original ULog and per-motor binaries','gate':[],'delivery':[]}
for kind in ['final','verified']:
 p=R/f'data/{kind}-repeated_handover/flight.ulg'
 u=ULog(str(p),message_name_filter_list=['research_actuator'])
 d=u.get_dataset('research_actuator').data
 ix=np.flatnonzero(d['owner'][1:]!=d['owner'][:-1])+1
 ts=[{'px4_us':int(d['actuator_timestamp'][i]),'from':int(d['owner'][i-1]),'to':int(d['owner'][i])} for i in ix if d['owner'][i] in [1,2] and d['owner'][i-1] in [1,2]]
 out['gate'].append({'run':kind,'dropouts':len(u.dropouts),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'transitions':ts})
for run in sorted((R/'data/handover-t4-fullstack-20261115').glob('*/flight')):
 p=run/'flight.ulg';u=ULog(str(p),message_name_filter_list=['research_actuator','actuator_motors','research_output'])
 d={x.name:x.data for x in u.data_list if x.multi_id==0};o=d['research_actuator'];a=d['actuator_motors'];b=d['research_output']
 ev=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
 bound=next(x['end_bound_px4_us'] for x in ev if x['event']=='handover_requested' and x.get('subject'))
 oi=int(np.flatnonzero((o['owner']==1)&(o['timestamp']>=bound))[0]);pub=int(o['actuator_timestamp'][oi])
 owned={}
 for i in range(len(o['timestamp'])):owned.setdefault(int(o['actuator_timestamp'][i]),[]).append(i)
 smap={}
 for j,t in enumerate(a['timestamp']):
  for i in owned.get(int(t),[]):
   if all(abs(float(o[f'control[{k}]'][i])-float(a[f'control[{k}]'][j]))<1e-6 for k in range(4)):
    smap.setdefault(int(a['timestamp_sample'][j]),set()).add(int(o['owner'][i]))
 ai=np.flatnonzero(a['timestamp']==pub);assert len(ai)==1;first_sample=int(a['timestamp_sample'][ai[0]])
 br={}
 for j,s in enumerate(b['timestamp_sample']):br.setdefault(int(s),[]).append(j)
 case={'run':str(run),'first_publication_us':pub,'first_sample_us':first_sample,'dropouts':len(u.dropouts),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'motors':[]}
 for file in sorted((run/'gz-motor').glob('*.bin')):
  mid,t,tail=read_trace(file)
  ids=np.flatnonzero((t['sim_us']>=pub)&(t['sim_us']<=pub+24000));rows=[]
  for j in ids:
   sample=int(t['applied_sample_us'][j]);tm=int(t['sim_us'][j]);val=float(t['ref_motor_input'][j])
   matches=[k for k in br.get(sample,[]) if int(b['timestamp'][k])<=tm]
   err=min([abs(val-float(b[f'motor_speed[{mid}]'][k])) for k in matches],default=None)
   assert err==0
   rows.append({'sim_us':tm,'sample_us':sample,'owner':sorted(smap.get(sample,set())),'value':val,'bridge_error':err,'received':int(t['received'][j])})
  first=next(x for x in rows if x['owner']==[1]);expected=next(x for x in rows if x['sim_us']==pub+4000)
  case['motors'].append({'motor':mid,'tail_bytes':tail,'first_N_delay_us':first['sim_us']-pub,'first_N_sample_us':first['sample_us'],'expected_step_owner':expected['owner'],'first_sample_ever_applied':bool(np.any(t['applied_sample_us']==first_sample)),'window':rows,'bin_sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
 out['delivery'].append(case)
out['wall_s']=time.monotonic()-start
(P/'raw-audit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'gate_counts':[len(x['transitions']) for x in out['gate']],'delivery':[(x['first_publication_us'],[(m['motor'],m['first_N_delay_us'],m['first_sample_ever_applied']) for m in x['motors']]) for x in out['delivery']],'wall_s':out['wall_s']},indent=2))
