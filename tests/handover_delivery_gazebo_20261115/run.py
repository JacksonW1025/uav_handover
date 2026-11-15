import subprocess,os,time,signal,json,hashlib
from pathlib import Path
import argparse,uuid
parser=argparse.ArgumentParser(description="Explicitly launches two single-rotor Gazebo runs, no PX4")
parser.add_argument('--plugin',type=Path,required=True)
parser.add_argument('--driver',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--gazebo-cpus',default='12-13')
parser.add_argument('--driver-cpus',default='4-5')
a=parser.parse_args();source=Path(__file__).parent;A=a.output.resolve()
plugin=a.plugin.resolve();driver=a.driver.resolve()
assert plugin.is_file() and driver.is_file()
assert hashlib.sha256(plugin.read_bytes()).hexdigest()=='21211d96e9d929b3d3f5a6dea32ba4d319dca82b353617105cefde4cc6fb58ea', 'wrong plugin binary'
A.mkdir(exist_ok=False)
import xml.sax.saxutils
(A/'world.sdf').write_text((source/'world.sdf').read_text().replace('@MOTOR_PLUGIN@',xml.sax.saxutils.escape(str(plugin),{'"':'&quot;'})))
partition='handover-t4-'+uuid.uuid4().hex

out=[]
for arm in ['normal','lag']:
 p=A/arm;p.mkdir(exist_ok=False);env=dict(os.environ,GZ_PARTITION=partition+'-'+arm,HANDOVER_GZ_MOTOR_TRACE=str(p),GZ_SIM_RESOURCE_PATH='',GZ_IP='127.0.0.1');t=time.monotonic()
 with (p/'gazebo.log').open('w') as f:
  proc=subprocess.Popen(['taskset','-c',a.gazebo_cpus,'gz','sim','-s','--headless-rendering',str(A/'world.sdf')],env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   time.sleep(3)
   with (p/'driver.log').open('w') as d:r=subprocess.run(['taskset','-c',a.driver_cpus,str(driver),arm],env=env,stdout=d,stderr=subprocess.STDOUT,timeout=25)
   if r.returncode:raise RuntimeError('driver exit '+str(r.returncode))
  finally:
   os.killpg(proc.pid,signal.SIGINT)
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:raise RuntimeError('Gazebo cleanup timeout')
  out.append({'arm':arm,'driver_exit':r.returncode,'gazebo_exit':proc.returncode,'wall_s':time.monotonic()-t,'partition':env['GZ_PARTITION']})
 (A/'execution.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
