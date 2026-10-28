"""P16 fixed task, sixG cross-history pool, no live choice changes."""
import copy,json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from p16.common import *
from run_experiment import Experiment,p5_profile
GS=[.55,.84,1.13,1.42,1.71,2.0]
MAIN_SEED=162810101;REPL_SEED=162810102

def configuration(family,prefix,G,stage):
 source=R/('config/p13-formal-cases/p13-F2-b1-AB-short.json' if family=='F2' else 'config/p14h/p14h-d01-F4-A-before-s142710201.json');c=json.load(open(source));c.pop('p14h',None);c.pop('p15',None);c['p14r']={'observer_trace':False,'version':'P16 essentials only, samebinary no OP/fusion/fullP diagnostic'}
 s=c['p5']['conditions']['p11-case'];s['gaps']['windows_s']=[[0.,.36],[.36+G,.72+G]];s['post_gap_s']=5.-(.72+G);s['description']='P16 fixed6s cruise, source .36/.36 gaps, only G/presenceA changes, same end';c['p11']['event_mask']={'NORMAL':[],'A':[0],'B':[1],'AB':[0,1]}[prefix];c['p11']['schema']='P16-fixed-grid';c['p11']['budget']=dict(development=2,main=24,replication=6,total=32);c['p11']['model_split']=stage;c['p12']['repair']=False;c['p13']['source_id']='P16 '+family;c['p16']=dict(stage=stage,family=family,prefix=prefix,G=G,version='P16-essential-platform-1');return c

def scenario(c,G):
 s=c['p5']['conditions']['p11-case'];pcfg=p5_profile(c['p5'],s);cfg=copy.deepcopy(c);cfg['p1_speed_m_s']=s['speed_m_s'];ns=SimpleNamespace(cfg=cfg,pcfg=pcfg);A=Experiment.reposition(ns,0.)[3]+pcfg['reference_hold_s']+pcfg['accel_s']+pcfg['pre_gap_s'];total=Experiment.profile_duration(ns)+pcfg['end_hold_s'];times=np.arange(-.02,total+.008,.004);axis=np.asarray(pcfg['motion_axis_ned']);org=np.asarray(c['p12']['common_world_reference']['position_ned_m']);table=[]
 for t in times:
  p,v,_=Experiment.p1_profile(ns,float(t));table.append(np.r_[org+axis*p,axis*v].tolist())
 # Same G and family/Bshape/horizon plans match across A/B history. State-gated
 # translation tolerance is separately checked, never rotate LP by attitude yaw.
 from p16.workflow import digest
 profile=dict(table_t0_s=-.02,table=table,yaw=c['p12']['common_world_reference']['yaw_rad'])
 plan=dict(profile=profile,A_start=A,A_duration=.36,B_duration=.36,G=G,stream_end=total,horizon=total+pcfg['post_stream_s']+c['p11'].get('prediction_terminal_slack_s',.5))
 plan['suffix_plan_hash']=digest(dict(family=c['p16']['family'],G=G,profile=profile,B_start=A+.36+G,duration=.36,end=plan['horizon']))
 return plan

def create_development():
 rows=[]
 for i,f,p,g in [(1,'F2','NORMAL',1.42),(2,'F4','AB',1.42)]:
  rid=f'p16-d{i:02d}-{f}-{p}';path=Path('config/p16')/(rid+'.json');c=configuration(f,p,g,'development');write(R/path,c);pl=scenario(c,g);rows.append(dict(id=rid,stage='development',role='interface',family=f,prefix=p,G=g,seed=162810000+i,config=str(path),config_sha256=sha(R/path),absolute_A_profile_s=pl['A_start'],absolute_B_profile_s=pl['A_start']+.36+g))
 write(B/'development-plan.json',dict(rows=rows));return rows
if __name__=='__main__':create_development()
