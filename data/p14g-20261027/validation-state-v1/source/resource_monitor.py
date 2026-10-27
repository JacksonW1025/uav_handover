"""Owned offline manager CPU+children accounting; not a simulator/processkiller."""
import sys,time,json,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psutil
from p14g.common import *

def main():
 out=Path(sys.argv[1]);register(out,'recover still-live B manager cumulative CPU and livechild CPU, legacy missing remains bounded notzero');matches=[]
 for p in psutil.process_iter(['pid','cmdline']):
  args=p.info['cmdline'] or []
  if any(x.endswith('/p14g/batch_sets.py') for x in args) and 'B' in args and any(x.endswith('B-v2') for x in args):matches.append(p)
 assert len(matches)==1,matches;p=matches[0];birth=p.create_time();last=None;seen=0
 while True:
  t=time.time()
  try:
   if p.create_time()!=birth or p.status()==psutil.STATUS_ZOMBIE:break
   cpu=p.cpu_times();kids=p.children(recursive=True);total=cpu.user+cpu.system+cpu.children_user+cpu.children_system;rss=p.memory_info().rss
   for k in kids:
    try:c=k.cpu_times();total+=c.user+c.system;rss+=k.memory_info().rss
    except psutil.Error:pass
   row={'epoch_s':t,'manager_pid':p.pid,'manager_birth':birth,'CPU_s_parent_reaped_plus_live':total,'rss_all_current_bytes':rss,'live_children':[k.pid for k in kids]}
   with (out/'samples.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
   last=row;seen+=1
  except psutil.Error:break
  time.sleep(.25)
 assert last is not None;gap=time.time()-last['epoch_s'];write(out/'result.json',{'last':last,'sample_count':seen,'tail_CPU_upper_s':4*(gap+.25),'CPU_upper_s':last['CPU_s_parent_reaped_plus_live']+4*(gap+.25),'CPU_is_not_wall':True,'scope':'owned B-v2 manager only; process CPU cumulative children plus livechild, 4affinity CPUs bound unsampled tail. PID birthchecked. Older exited managers missingCPU not reconstructed.'})
if __name__=='__main__':main()
