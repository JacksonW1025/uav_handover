"""P14H actual runtime/source/format gate before countedmechanismstarts."""
import sys,json,re,shutil,subprocess,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14h.common import *

def main():
 out=register(sys.argv[1],'preflight: actual runtime snapshot, sourceclosure, recorderhost tests, idempotenceandfrozenplan');a=json.load(open(B/'source-closure-v1.json'));assert a['exact_old_tokens_after_two_new_passive_blocks_removed'];a=json.load(open(B/'buffer-host-v2/result.json'));assert a['status']=='PASS'
 from apply_p14h import apply
 source=R/'uav_lab/.local/checkouts/px4-raptor/src/modules/ekf2/EKF2.cpp';before=sha(source);apply();apply();assert sha(source)==before;assert source.read_text().count('P14H_POST_EKF_SNAPSHOT')==1
 paths=[R/'uav_lab/.local/checkouts/px4-raptor/build/px4_sitl_raptor/bin/px4',R/'data/p13-20261026-freeze/models/policy.npz',source,R/'uav_lab/.local/checkouts/px4-raptor/src/lib/handover_research/P14HSnapshot.hpp',R/'uav_lab/.local/checkouts/px4-raptor/src/modules/mc_raptor/blob/policy.tar']
 runtime={}
 for j,p in enumerate(paths):
  dst=out/f'{j:02d}-{p.name}';dst=dst.with_suffix('.bin') if p.name in ['px4','policy.tar'] else dst;shutil.copyfile(p,dst);runtime[str(p.relative_to(R))]={'copy':str(dst.relative_to(R)),'sha256':sha(p)}
 assert runtime[str(paths[1].relative_to(R))]['sha256']==json.load(open(B/'runtime-before/manifest.json'))[str(paths[1].relative_to(R))]['sha256']
 assert sha(paths[4])==json.load(open(B/'runs/p14h-d01-F4-A-before-s142710201/candidate.json'))['policy_sha256']
 plugins=[]
 for p in (R/'uav_lab/.local/checkouts/px4-raptor/build/px4_sitl_raptor').rglob('*.so'):
  if 'research' in p.name.lower():
   dst=out/(p.name+'.bin');shutil.copyfile(p,dst);plugins.append({'path':str(p.relative_to(R)),'copy':str(dst.relative_to(R)),'sha256':sha(p)})
 cap=os.statvfs(R);avail=cap.f_bavail*cap.f_frsize;assert avail>24*1024**3
 files=list((R/'tools/p14h').glob('*'))+[R/'tools/apply_p14h.py',R/'research/state/P14HSnapshot.hpp']+list((R/'config/p14h').glob('*.json'))+paths
 write(out/'gate.json',{'status':'PASS','idempotence':True,'new_hook_once':True,'source_closure':True,'buffer_normal_abnormal_overflow_host_pass':True,'frame_bytes':4320,'capacity_rows':131072,'complete0':'intentional processlifetime, exitedproducer+coverage checked separately','actual_runtime':runtime,'plugins':plugins,'available_bytes':avail,'reserve_bytes':24*1024**3,'required_remaining_raw_estimate':'16 x.6GiB + analyses4GiB + reserve8GiB; 24GiB conservativegate, no deletion','files':{str(p.relative_to(R)):sha(p) for p in files if p.is_file()},'models_and_source':'same sourceheldOP initialresidual; no oldsmallbudget/fading certification','control_or_protection_assignments_changed':False,'runner_change':'boundedreleaseandfastpollnearresume,actualtimingtreatment declared, no fakeclock/capture; fixed platform nooff-on equivalence claim'})
 print('P14H_PREFLIGHT_PASS',avail)
if __name__=='__main__':main()
