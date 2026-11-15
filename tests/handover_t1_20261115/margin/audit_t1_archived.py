import os
import pathlib,sys,json,hashlib
import numpy as np
from pyulog import ULog
ROOT=pathlib.Path(os.environ['HANDOVER_RESEARCH_ROOT']);sys.path.insert(0,str(ROOT/'tools'))
from output_chain import read_trace
from analyze import clean
out=[]
for case,end in [('tight_turn_1p8',54020000),('tight_control_raptor_preentered',56672000)]:
 root=ROOT/'data/handover-explore-20261110'/(case+'-a1')/'flight';u=ULog(str(root/'flight.ulg'));d={x.name:x.data for x in u.data_list if x.multi_id==0};p=d['research_p11'];o=d['research_actuator'];t=p['timestamp'];m=(t>=end-2000000)&(t<=end);native=m&(p['native_step']==1)
 r=dict(case=case,ulog_sha256=hashlib.sha256((root/'flight.ulg').read_bytes()).hexdigest(),start=end-2000000,end=end,p11_samples=int(m.sum()),native_steps=int(native.sum()),stale=int(p['stale'][m].sum()),invalid_positive_increments=int(np.maximum(np.diff(p['invalid_total'][m].astype(np.int64)),0).sum()),activations=int(p['activation'][m].sum()),all_active=bool(np.all(p['active'][m])),max_ref_age_us=int((t[m]-p['last_valid_read_us'][m]).max()),native_gru_commits=int(p['gru_committed'][native].sum()),motors={})
 for j in range(4):
  mid,z,tail=read_trace(root/'gz-motor'/f'motor-{j}.bin');zm=(z['sim_us']>=end-2000000)&(z['sim_us']<=end);zz=z[zm];ii=np.searchsorted(o['actuator_timestamp'],zz['applied_sample_us'],side='right')-1
  r['motors'][str(j)]=dict(steps=len(zz),max_gap_us=int(np.diff(zz['sim_us']).max()),max_age_us=int((zz['sim_us']-zz['applied_sample_us']).max()),owners=np.unique(o['owner'][ii]).tolist(),identity_match=bool(np.all(o['actuator_timestamp'][ii]==zz['applied_sample_us'])),tail_bytes=tail)
 out.append(r)
p=ROOT/'data/handover-t1-margin-20261115-v1/archived-late-window-audit.json';p.write_text(json.dumps(clean(out),indent=2)+'\n');print(p)
