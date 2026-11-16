"""Two bounded civilian isolated SITL margin observations; no physical low-altitude obstacle."""
import argparse,sys,json,time,hashlib,fcntl,resource,traceback
from pathlib import Path
from types import SimpleNamespace
ROOT=Path('/home/car/uav_handover'); OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from handover_explore import runner as ex
from handover_explore.design import k,CASES
from cn_single import runner as original
import run_experiment as base
from preparation_batch import identity
from p9_run import host_gate
class Experiment(ex.Experiment):
 def publish(self):
  now=time.monotonic()
  if now-getattr(self,"t1_fast_last",-1.)<.004:return
  self.send_last=now-.021
  super().publish();self.t1_fast_last=now
 def state_contract(self):
  super().state_contract()
  self.command('param','set','MC_RAPTOR_RINI',str(self.cfg['t2_mode']));self.command('param','show','MC_RAPTOR_RINI')
  self.checks['t1_history']='RINI'+str(self.cfg['t2_mode'])+' requested; native verification required'
 def switch(self,current,target,iteration):
  self.event('t1_early_entry' if self.cfg['t1']['arm']=='PRE' and target=='N' else 't1_margin_trigger',arm=self.cfg['t1']['arm'],end_bound_px4_us=self.native_bound_streaming(),test_attitude_budgets_deg=[35.,45.])
  if target in ['C','MARK']:
   self.event('t1_continue_classic',end_bound_px4_us=self.native_bound_streaming());return
  return super().switch(current,target,iteration)
 def finish_subject(self,current):
  return super().finish_subject('N' if self.cfg['t1']['arm']=='PRE' else current)
def run(arm):
 with (OUT/'launch.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  ledger=OUT/'attempts.jsonl';rows=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
  starts=[x for x in rows if x['event']=='START_INTENT'];ends=[x for x in rows if x['event']=='END']
  if len(starts)>=2 or any(x['arm']==arm for x in starts) or len(starts)!=len(ends):raise RuntimeError('bounded budget or unresolved prior run')
  if arm=='N2' and not any(x['arm']=='N4' and x['status']=='PASS' and x['cleanup_error'] is None for x in ends):raise RuntimeError('N4 must end cleanly first')
  host=host_gate();d=OUT/arm;d.mkdir();base.write(d/'host-before.json',host)
  before=identity();base.write(d/'candidate-before.json',before)
  cfg=json.loads((ROOT/'config/cn_reference/quickcheck.json').read_text());cfg.pop('cn_reference',None);cfg['altitude_m']=4.;cfg['seed']=20261110
  mode=int(arm[1:]);cfg['t2_mode']=mode
  spec=dict(CASES['slow_line']);spec.update(case=arm,label='T2 slow moving GRU preparation '+arm,switches=[(3.,'N')],neural_before_profile=False,duration_s=18.,reference_kind='continuous_shared_target_250hz',state_parameters={'MC_RAPTOR_RINI':mode,'MC_RAPTOR_RTGT':0,'MC_RAPTOR_RREC':0,'MC_RAPTOR_NCO':0})
  cfg['explore']=spec;cfg['t1']=dict(arm=arm,test_attitude_budgets_deg=[35.,45.],engineering_meaning='35deg predeclared test trajectory attitude budget; original 45deg protection unchanged',history='RINI'+str(mode)+'; same actual classic action, only preparation differs',runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
  cfg['cn_single'].update(seed=20261110,subject='T2 slow line RINI2 versus RINI4',gap_profile_s=None,startup_budget=2,classic_prefix='4m takeoff, hold, continuous offboard 0.6mps line',external_reference='continuous shared trajectory',memory='RINI'+str(mode))
  base.write(d/'config.json',cfg)
  args=SimpleNamespace(kind='p1_c_to_n',config=d/'config.json',condition='single',treatment=None,output=d/'flight',startup_only=False,capture_raw_sensors=False,hover_s=None,sim_seed=20261110,initial_yaw_deg=0.)
  original.append(ledger,dict(event='START_INTENT',arm=arm,time_ns=time.time_ns(),output=str(d/'flight')))
  t=time.monotonic();e=None;status='FAIL';reason=None;clean=None
  try:e=Experiment(args);e.metadata['scenario']='t2_slow_line_history_'+arm;e.execute();status='PASS'
  except BaseException as exc:
   reason=repr(exc);traceback.print_exc()
   if e:e.event('failure',reason=reason);e.emergency_land()
  finally:clean=original.close_experiment(e)
  after=identity();base.write(d/'candidate-after.json',after)
  result=dict(event='END',arm=arm,status=status,reason=reason,cleanup_error=clean,wall_s=time.monotonic()-t,candidate_unchanged=before==after)
  base.write(d/'result.json',result);original.append(ledger,result);print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--arm',choices=['N4','N2'],required=True);run(p.parse_args().arm)
