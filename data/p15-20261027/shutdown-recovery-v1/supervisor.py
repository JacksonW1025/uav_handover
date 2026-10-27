"""Owned post-DISARM shutdown ordering only, never modifies a live task."""
import sys,json,time,subprocess,os,signal,resource
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p15.common import B,PY,write,append

def eligible(ev):
 return not any(e['event']=='failure' for e in ev) and any(e['event']=='p5_stream_ended' for e in ev) and all(any(e['event']=='p1_phase_ended' and e.get('label')==name for e in ev) for name in ['post_stream','return_classic']) and any(e['event']=='landing_requested' for e in ev) and any(e['event']=='ready' and e.get('condition')=='disarmed' for e in ev) and not any(e['event']=='process_stopped' and e.get('name')=='px4' for e in ev)

def run(ident,plan,out):
 out=Path(out);out.mkdir(exist_ok=False,parents=True);write(out/'before.json',dict(id=ident,rule='onlycompletedtask+disarmed ownGazeboSIGINT beforePX4teardown',same_frozen_physics_andcontroller=True));proc=subprocess.Popen([PY,R/'tools/p15/campaign.py',ident,plan]);file=B/'runs'/ident/'run/events.jsonl';offset=0;buffer='';events=[];sent=False;st=time.perf_counter();self0=resource.getrusage(resource.RUSAGE_SELF)
 while proc.poll() is None:
  if file.exists():
   with file.open() as f:f.seek(offset);text=f.read();offset=f.tell()
   buffer+=text
   while '\n' in buffer:
    line,buffer=buffer.split('\n',1)
    if line:events.append(json.loads(line))
   if not sent and eligible(events):
    gz=next(e for e in events if e['event']=='process_started' and e['name']=='gazebo');px=next(e for e in events if e['event']=='process_started' and e['name']=='px4');pid=gz['pid'];cmd=(Path('/proc')/str(pid)/'cmdline');pxpath=Path('/proc')/str(px['pid']);assert cmd.exists() and pxpath.exists();raw=cmd.read_bytes();assert b'gz' in raw and b'sim' in raw and os.getpgid(pid)==pid
    disarm=next(e for e in reversed(events) if e['event']=='ready' and e.get('condition')=='disarmed');assert time.monotonic_ns()-disarm['monotonic_ns']<500000000,'late disarmobserver, do not signal uncertainphase';os.killpg(pid,signal.SIGINT);sent=True;write(out/'signal.json',dict(gazebo_pid=pid,PX4_still_alive=True,signal='SIGINT',signal_ns=time.monotonic_ns(),disarmed_marker_ns=disarm['monotonic_ns'],scientific_post_stream_end_ns=next(e['monotonic_ns'] for e in events if e['event']=='p1_phase_ended' and e.get('label')=='post_stream'),no_parameter_or_command_injection=True))
  time.sleep(.002 if any(e['event']=='landing_requested' for e in events) and not sent else .02)
 after=resource.getrusage(resource.RUSAGE_SELF);write(out/'end.json',dict(rc=proc.returncode,postdisarm_signal_sent=sent,wall_s=time.perf_counter()-st,CPU_s_manager=after.ru_utime+after.ru_stime-self0.ru_utime-self0.ru_stime,scope='supervisor ownCPU, childphysical/analysis separatelycharged'));return proc.returncode
if __name__=='__main__':raise SystemExit(run(sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3])))
