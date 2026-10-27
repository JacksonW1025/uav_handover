"""P15 online causal selection. A dedicated bounded worker keeps scoring outside
ROS publish/control pumping. No candidate is physically probed for free.
"""
import sys,time,os,json,multiprocessing,resource,copy,signal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import run_experiment as base
from p15.state import capture
from p15.common import R,B,write
from p15.model import rank
from p15.update import local

def worker(pipe):
 os.sched_setaffinity(0,{0,1,2,3});resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'))
 while True:
  job=pipe.recv()
  if job is None:break
  try:
   before=time.perf_counter();out=rank(job['snapshot'],job['pool'],job['context'],job['parameters'],P,job['method'],np.random.default_rng(job['rng_seed']),job.get('used',()),job.get('update'));out['worker_wall_s']=time.perf_counter()-before
   if job.get('update') is not None:
    ab=rank(job['snapshot'],job['pool'],job['context'],job['parameters'],P,job['method'],np.random.default_rng(job['rng_seed']),job.get('used',()),None);out['no_update_ablation']=ab;out['update_changed_choice']=ab['selected']['id']!=out['selected']['id']
   pipe.send(out)
  except BaseException as e:pipe.send({'error':repr(e)})

class Experiment(base.Experiment):
 def __init__(self,args):
  super().__init__(args);self.env['HANDOVER_P14H_TRACE_DIR']=str(self.out/'gz-motor');self.p15=self.cfg['p15'];self.p15_done=False;self.p15_wait=False;self.p15_snapshots=[];self.p15_last_height=None;self.p15_max_L=0.;self.p15_failed=False;self.p15_H0=None;self.p15_used=self.p15.get('used_candidates',[]);self.pipe,other=multiprocessing.Pipe();self.worker=multiprocessing.get_context('fork').Process(target=worker,args=(other,));self.worker.start();self.event('p15_model_worker_started',pid=self.worker.pid);self.metadata['processes'].append({'name':'p15-model-worker','pid':self.worker.pid,'command':['multiprocessing fork, bounded P15 scoring worker']});self.files.append(self);self.p15_request=None;
  if self.p15.get('local_update_path'):
   source=R/self.p15['local_update_path'];assert source.exists(),'declared past map update unavailable';self.p15['local_update']=json.load(open(source));write(self.out/'p15-inherited-update.json',{'source':str(source.relative_to(R)),'sha256':base.digest(source),'update':self.p15['local_update'],'source_role':'past map record only, independent new seed validation'})
  self.p15_prior=None;self.p15_prior_wait=False;self.p15_prior_requested=False
 def close(self):
  if getattr(self,'worker',None):
   if self.worker.is_alive():self.pipe.send(None);self.worker.join(3)
   if self.worker.is_alive():self.worker.terminate();self.worker.join(3)
   self.event('p15_model_worker_stopped',pid=self.worker.pid,exit_code=self.worker.exitcode);self.worker=None
 def receive(self,name,msg):
  super().receive(name,msg)
  if self.stream_t0 is not None:
   t=time.monotonic()-self.stream_t0;A=self.p5_gap_windows()[0][0]
   if name=='vehicle_local_position':
    if not getattr(self,'p15_A_H0',False) and t>=A:self.p15_H0=-float(msg.z);self.p15_A_H0=True;self.p15_max_L=0.
    if self.p15_H0 is not None:self.p15_max_L=max(self.p15_max_L,float(msg.z)+self.p15_H0)
   if name=='vehicle_attitude' and t>=A:
    q=np.array(msg.q);self.p15_failed=self.p15_failed or bool(1-2*(q[1]**2+q[2]**2)<np.cos(np.pi/4))
   if t>=A:self.p15_failed=self.p15_failed or self.p15_max_L>1.
 def context(self):
  total=base.Experiment.profile_duration(self)+self.pcfg['end_hold_s'];times=np.arange(0,total+.008,.004);axis=np.array(self.pcfg['motion_axis_ned']);org=np.array(self.stream_state['origin']);table=[]
  for t in times:
   x,v,_=self.p1_profile(float(t));table.append(np.r_[org+axis*x,axis*v].tolist())
  return dict(H0_LP=self.p15_H0,D_LP=self.p15_max_L,prefix_failed=self.p15_failed,A_start=self.p5_gap_windows()[0][0],A_duration=self.p15['A_duration'],stream_end=total,task_end=total+self.pcfg['post_stream_s'],reference_table=table,table_t0=0.,yaw=self.stream_state['yaw'],prefix=self.p15['prefix'],physical_state_source='LP output dynamics proxy, not true COM')
 def begin_decision(self):
  s=capture(self,'P15_'+self.p15['decision_phase']);A=self.p5_gap_windows()[0][0];available=(s['available_by_ns']/1e9-self.stream_t0);assert (available<A if self.p15['decision_phase']=='preA' else available>=A+self.p15['A_duration']), 'decision information phase violation';assert (s['available_by_ns']-s['query_before_ns'])/1e9<=self.p15['query_time_budget_s'],'query exceeded predeclared bound';self.p15_snapshots.append(s);write(self.out/'p15-decision-state.json',s);context=self.context();pool=json.load(open(R/'config/p15/candidate-pool-v1.json'))['candidates'];prefix=self.p15['prefix'];pool=[dict(c,prefix=prefix) for c in pool if c['D'] in self.p15.get('allowed_D',[.24,.30,.38])];params=json.load(open(R/'config/p15/model-v1.json'));update=self.p15.get('local_update')
  if self.p15.get('map_loop') and self.p15_prior:
   prior=self.p15_prior['rows'][0]['prediction'];update=local(prior,s,self.p15_prior_context);write(self.out/'p15-local-update.json',update)
  request=dict(snapshot=s,pool=pool,context=context,parameters=params,method=self.p15['method'],rng_seed=self.sim_seed+self.p15.get('trial',0)*1009,used=self.p15_used,update=update);write(self.out/'p15-selection-input.json',request);self.pipe.send(request);self.p15_request=request;self.p15_wait=True;self.p15_request_time=time.monotonic();self.event('p15_decision_requested',available_by_ns=s['available_by_ns'],profile_s=s['profile_s'],method=self.p15['method'],prefix=prefix,information_class=self.p15['decision_phase'],source='completed P11/direct row + last consumed execution; future physical raw unavailable and excluded')
 def apply_choice(self,out):
  assert 'error' not in out,out;fixed=self.p15.get('fixed_candidate');c=fixed or out['selected'];out['executed_candidate']=c;out['fixed_development_override']=fixed is not None;A=self.p5_gap_windows()[0][0];b0=A+self.p15['A_duration']+c['G'];b1=b0+c['D'];assert time.monotonic()-self.stream_t0<b0-.10,'decision too late for legal B';assert self.p15['decision_phase']!='preA' or time.monotonic()-self.stream_t0<A,'preA selection completed after A';self.p15_windows[:]=[(A,A+self.p15['A_duration'])] if self.p15['prefix']=='AB' else []
  if self.p15['prefix'] in ['AB','B']:self.p15_windows.append((b0,b1))
  if self.p15['prefix']=='A':self.p15_windows[:]=[(A,A+self.p15['A_duration'])]
  if self.p15['prefix']=='NORMAL':self.p15_windows[:]=[]
  write(self.out/'p15-selection.json',out);write(self.out/'p15-realized-plan.json',dict(windows_profile_s=self.p15_windows,B_planned_start=b0,B_planned_end=b1,A_planned_start=A,prefix=self.p15['prefix'],selected=c,source_config_unmodified=True,decision_finished_ns=time.monotonic_ns(),no_trajectory_change=True));self.p15_wait=False;self.p15_done=True;self.event('p15_choice_applied',candidate=c,prefix=self.p15['prefix'],windows_profile_s=self.p15_windows,decision_latency_s=time.monotonic()-self.p15_request_time)
 def start_stream(self,*args,**kw):
  # Mutable list is shared only with the original gap injector. Changes happen
  # before B; original base trajectory and wall/sample clocks remain intact.
  gaps=kw.get('gaps',());self.p15_windows=list(gaps);kw['gaps']=self.p15_windows;super().start_stream(*args,**kw);original=self.stream
  def publish():
   if self.stream_t0 is None:return original()
   t=time.monotonic()-self.stream_t0
   if self.p15_H0 is None and 'vehicle_local_position' in self.latest:self.p15_H0=-float(self.latest['vehicle_local_position'].z)
   if 'vehicle_local_position' in self.latest and self.p15_H0 is not None:self.p15_max_L=max(self.p15_max_L,float(self.latest['vehicle_local_position'].z)+self.p15_H0)
   A=self.p5_gap_windows()[0][0];decision=A-self.p15['decision_pre_A_s'] if self.p15['decision_phase']=='preA' else A+self.p15['A_duration']+self.p15['decision_after_A_s']
   if self.p15.get('map_loop') and not self.p15_prior_requested and t>=A-2.:
    ss=capture(self,'P15_map_preA');ct=self.context();pool=[dict(c,prefix=self.p15['prefix']) for c in json.load(open(R/'config/p15/candidate-pool-v1.json'))['candidates'] if c['D'] in self.p15.get('allowed_D',[.24,.30,.38])];request=dict(snapshot=ss,pool=pool,context=ct,parameters=json.load(open(R/'config/p15/model-v1.json')),method='M3',rng_seed=self.sim_seed);write(self.out/'p15-map-prior-input.json',request);self.pipe.send(request);self.p15_prior_context=ct;self.p15_prior_requested=True;self.p15_prior_wait=True
   if self.p15_prior_wait and self.pipe.poll():
    self.p15_prior=self.pipe.recv();assert 'error' not in self.p15_prior;write(self.out/'p15-map-prior.json',self.p15_prior);self.p15_prior_wait=False
   if not self.p15_done and not self.p15_wait and t>=decision:
    assert not self.p15_prior_wait,'map preA forecast must complete before postA request';self.begin_decision()
   if self.p15_wait:
    if self.pipe.poll():self.apply_choice(self.pipe.recv())
    elif time.monotonic()-self.p15_request_time>self.p15['ranking_wall_budget_s']:raise RuntimeError('P15_SELECTION_DEADLINE_NO_B_SUBSTITUTION')
   return original()
  self.stream=publish
base.Experiment=Experiment
if __name__=='__main__':raise SystemExit(base.main())
