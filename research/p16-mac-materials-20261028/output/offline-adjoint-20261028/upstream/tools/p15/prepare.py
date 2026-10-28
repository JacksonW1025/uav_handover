"""Preregister exact new cases; task reference is identical for all candidates."""
import sys,copy,json,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p15.common import *
from run_experiment import p5_profile,Experiment
from types import SimpleNamespace

def config(family,job):
 source=R/('config/p13-formal-cases/p13-F2-b1-AB-short.json' if family=='F2' else 'config/p14h/p14h-d01-F4-A-before-s142710201.json');cfg=json.load(open(source));spec=cfg['p5']['conditions']['p11-case'];spec['gaps']['windows_s']=[[0,.30],[2.30,2.60]];spec['post_gap_s']=2.40;cfg['p11']['event_mask']={'NORMAL':[],'A':[0],'B':[1],'AB':[0,1]}[job['prefix']];cfg.pop('p14h',None);cfg['p14r']={'observer_trace':True,'version':'P14H existing passive observer, P15 full platform'};cfg['p15']=dict(job,version='p15-runner-v1',decision_phase=job.get('decision_phase','preA'),A_duration=.30,planned_B_duration=.30,planned_G=2.,decision_pre_A_s=1.5,decision_after_A_s=.20,query_time_budget_s=.10,ranking_wall_budget_s=1.2,observe_only_existing=True,physical_live=False);cfg['p11']['schema']='p15-independent';cfg['p11']['budget']={'development':8,'search':32,'map':8,'total':48};cfg['p11']['model_split']='development' if job['budget_class']=='development' else 'independent';cfg['p13']['source_id']='P15 linked '+family;cfg['p5']['conditions']['p11-case']['description']='P15 fixed6s cruise; all source cases share exact task, B selected within preregistered range before B, no future input';cfg['p12']['repair']=False
 return cfg

def materialize(rows,out):
 out=register(out,'case identities before START; same6s trajectory and source guards, no weight/protection changes');result=[]
 for row in rows:
  cfg=config(row['family'],row);path=R/'config/p15'/(row['id']+'.json');assert not path.exists();write(path,cfg);result.append(dict(row,config=str(path.relative_to(R)),config_sha256=sha(path),kind='p5_gap',condition='p11-case',treatment='P11-Z'))
 write(out/'plan.json',dict(rows=result,budget=json.load(open(R/'config/p15/protocol-v1.json'))['budget']));return result

def main():
 protocol=json.load(open(R/'config/p15/protocol-v1.json'));rows=[dict(x,budget_class='development',method='M3',decision_phase='preA',fixed_candidate=None) for x in protocol['first_cases']];materialize(rows,B/'development-stage1')
if __name__=='__main__':main()
