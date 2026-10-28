"""After-run evidence inventory. Never starts/stops simulation or changes old data."""
import os,sys,json,subprocess,time,resource,hashlib
from pathlib import Path
sys.path.insert(0,'tools')
from p16.common import B,R,sha,write,now
from p16.dual import both_terminal
import psutil
from p2_batch import host_state

def main(out):
 st=time.process_time();out=Path(out);out.mkdir(exist_ok=False,parents=True);active=[]
 for proc in psutil.process_iter(['pid','name','cmdline']):
  try:
   name=proc.info['name'] or '';args=proc.info['cmdline'] or []
   if name in ['px4','MicroXRCEAgent'] or (name in ['gz','gz-sim-server'] and 'sim' in args):active.append(proc.info)
  except psutil.Error:pass
 assert not active,'active simulator; inspect ownership before hashing live raw files'
 host=host_state();write(out/'host.json',dict(snapshot=host,read_only_final_audit=True,start_host_guard_unchanged=True,active_simulators=active));(out/'host-processes.txt').write_text(subprocess.check_output(['ps','-eo','pid,ppid,stat,etimes,comm'],text=True))
 ledger=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];starts=[x for x in ledger if x['event']=='START_INTENT'];assert len({x['id'] for x in starts})==len(starts)<=32
 counts={k:sum(x['stage']==k for x in starts) for k in ['development','main','replication']};assert counts['development']<=2 and counts['main']<=24 and counts['replication']<=6
 unresolved=[x['id'] for x in starts if not any(y.get('id')==x['id'] and y['event'] in ['FINISH','SCOPED_REVIEW_RESOLVED'] for y in ledger)]
 seal=json.load(open(B/'freeze-data-seal.json'));data_changed=[p for p,h in seal['files'].items() if sha(R/p)!=h];gate=json.load(open(B/'preflight-formal/gate.json'));source_changed=[p for p,h in gate['files'].items() if sha(R/p)!=h];assert not data_changed and not source_changed
 companion=json.load(open(B/'pre-main-output-supplement.json'));companion_changed=[p for p,h in companion['files'].items() if sha(R/p)!=h];assert not companion_changed
 terminal=both_terminal() if all((B/f'policies/{p}/terminal-seal.json').exists() for p in ['G','R']) else None
 manifest=[];inodes={};identity=[]
 for run in starts:
  t=B/'runs'/run['id'];e=json.load(open(t/'execution.json')) if (t/'execution.json').exists() else None;identity.append(dict(id=run['id'],execution_present=e is not None,candidate_unchanged=(e or {}).get('candidate_unchanged'),PX4_exit=(e or {}).get('PX4_exit'),unique_START_count=1))
  # rootfs ULog hardlinks and CLI symlinks are aliases, not new byte storage.
  paths=[t/'run/flight.ulg',t/'run/telemetry.jsonl',t/'run/resources.jsonl']+list((t/'run/gz-motor').glob('*'))
  for p in paths:
   if not p.is_file() or p.is_symlink():continue
   stat=p.stat();key=(stat.st_dev,stat.st_ino);first=inodes.get(key)
   if first is None:inodes[key]=str(p.relative_to(R))
   manifest.append(dict(path=str(p.relative_to(R)),bytes=stat.st_size,allocated_bytes=stat.st_blocks*512,sha256=sha(p),same_inode_as=first,mtime_ns=stat.st_mtime_ns))
 write(out/'raw-manifest.json',manifest)
 old='d0f3924c762e7fbaf5d799ae582a5b59ebb578f0';diff=subprocess.check_output(['git','diff',old,'--name-status'],text=True);(out/'baseline-worktree-diff.txt').write_text(diff);old_changed=[l for l in diff.splitlines() if l and l[0] in 'DMRT' and l.split('\t')[-1]!='.gitignore'];assert not old_changed,'old tracked content was changed'
 status=dict(time=now(),counts=counts,total_START=len(starts),unresolved=unresolved,source_config_runtime_fields_checked=len(gate['files']),source_changed=source_changed,frozen_data_fields_checked=len(seal['files']),frozen_data_changed=data_changed,companion_output_changed=companion_changed,both_terminal=terminal,identities=identity,raw_files=len(manifest),raw_unique_inodes=len(inodes),raw_logical_bytes_unique=sum(x['bytes'] for x in manifest if x['same_inode_as'] is None),old_tracked_changed=old_changed,history_scope='all oldtracked files vs baseline commit excluding authorizedgitignore; raw all newruns hashed, no claim entirehistoricalraw reread',host_no_owned_simulators=True,CPU_s=time.process_time()-st,complete_expected=counts==dict(development=2,main=24,replication=6) and not unresolved and terminal is not None)
 write(out/'audit.json',status);print(json.dumps({k:status[k] for k in ['counts','unresolved','source_changed','old_tracked_changed','complete_expected']},indent=2))
if __name__=='__main__':main(sys.argv[1])
