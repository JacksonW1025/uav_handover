"""Independent physical step continuity and file-read integrity; no write-error overclaim."""
import json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p13.physics import read,BODY,ROTOR
from p9_model import sha,write
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
for target in sorted((R/'data/p13-20261026-development').iterdir()):
 run=target/'run';p=run/'gz-motor/physics-p13-body.bin'
 if not p.exists():continue
 b,h=read(p,BODY,b'P13BODY1')
 if not h['complete']:continue
 pre=b[b['phase']==0];post=b[b['phase']==1];same=(post[:-1]['valid']==63)&(pre[1:]['valid']==63)
 report={}
 for key in ['com_p','com_v','base_p','base_q','base_v','base_omega','origin_p','origin_q','link_com_p','link_com_v']:
  a=post[:-1][key][same];c=pre[1:][key][same]
  report[key]=float(abs(a-c).max())
 timing={'same_step_pre_post':bool(np.array_equal(pre['step'],post['step'])),'same_sim_time_pre_post':bool(np.array_equal(pre['sim_ns'],post['sim_ns'])),'next_pre_sim_delta_equals_dt':bool(np.array_equal(pre['sim_ns'][1:]-post['sim_ns'][:-1],pre['dt_ns'][1:])),'step_increment_one':bool(np.all(pre['step'][1:]-post['step'][:-1]==1)),'post_before_next_pre_host':bool(np.all(pre['wall_ns'][1:]>post['wall_ns'][:-1]))}
 files=[]
 for f,dtype,magic in [(p,BODY,b'P13BODY1')]+[(run/f'gz-motor/physics-p13-rotor-{k}.bin',ROTOR,b'P13ROTR1') for k in range(4)]:
  a,hh=read(f,dtype,magic);files.append({'path':str(f.relative_to(R)),'rows':len(a),'header':hh,'full_read_sha256':sha(f),'file_length_exact':f.stat().st_size==64+len(a)*dtype.itemsize})
 rows.append({'id':target.name,'state_post_to_next_pre_max_difference':report,'timing':timing,'files':files,'status':'PASS' if all(timing.values()) and max(report.values())<=1e-10 and all(x['header']['complete']==1 and x['header']['dropped']==x['header']['errors']==0 for x in files) else 'FAIL'})
write(out/'continuity.json',{'schema':'p13-independent-continuity-1','records':rows,'writer_error_detection_scope':'initial/header/data writes checked partly; final header rewrite and fclose return not checked in runtime v1. errors=0 does NOT prove all IO errors detected. Independent complete-file read/length/step/validity/hash checks above establish present readable evidence, not fsync/powerloss durability guarantee. No runtime mutation/new flight for this offline check.','new_starts':0});print([(x['id'],x['status'],max(x['state_post_to_next_pre_max_difference'].values())) for x in rows])
