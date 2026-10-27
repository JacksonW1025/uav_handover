#!/usr/bin/env python3
"""P14H staged offline analysis, independently reserved and CPU-capped tools. Original fullrun gates preserved."""
import json,sys,subprocess,shutil
from pathlib import Path
import numpy as np
from pyulog import ULog
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));PY=R/'uav_lab/.local/venv/bin/python'
from p9_model import write
from p14h.common import run as metered_run

def process(run,out,models,predict=True):
 out.mkdir(parents=True,exist_ok=False);cfg=json.load(open(run/'config.json'));on=cfg['p12b']['observe']
 def tool(name,args,label,allow=False):
  target=out/('resource-'+label);q=metered_run([PY,R/'tools'/name,*args],target,cpu=60,wall=90,scope='postflight analysis '+label)
  shutil.copyfile(target/'process.log',out/(label+'.log'))
  if q['rc'] and not allow:raise RuntimeError('offline evidence tool failed '+label)
 tool('p14h/observe_scoped.py',[run,'--output',out/'observation'],'observation');tool('p12/execution.py',[run,'--output',out/'execution'],'execution');sync=out/'observation/synchronized.npz'
 if on:tool('p12b/audit.py',[run,'--output',out/'native'],'native')
 else:
  tool('p12/audit.py',[run,'--output',out/'native-legacy'],'native-legacy',allow=True)
  n=json.load(open(out/'native-legacy/native-audit.json'));n['schema']='p12c-off-shared-state-audit-1';n['status']='MEASURED_READINESS_UNOBSERVED';n['readiness']='OFF new canonical fields absent by design, no inferred initialization and no first-row exemption';n['read_phase_legacy_NOT_used_for_release']=n['gates']['read_phase'];n['shared_state_gates']={k:v for k,v in n['gates'].items() if k!='read_phase'};(out/'native').mkdir();shutil.copy2(out/'native-legacy/history.npz',out/'native/history.npz');write(out/'native/native-audit.json',n)
 tool('p12c/target_replay.py',[sync,'--config',run/'config.json','--output',out/'target'],'target');tool('p11/synchronize.py',[run,'--output',out/'send-read'],'send-read');tool('p12c/pack.py',[run,'--sync',sync,'--output',out/'packed'],'pack');tool('p11/pack.py',['measure',run,'--sync',sync,'--output',out/'measured'],'measure')
 tool('p12c/validate.py',['--run',run,'--analysis',out,'--output',out/'source-validation.json'],'source-validation',allow=not on)
 native=json.load(open(out/'native/native-audit.json'));source=json.load(open(out/'source-validation.json'));ob=json.load(open(out/'observation/observation.json'));ex=json.load(open(out/'execution/execution.json'));target=json.load(open(out/'target/target-replay.json'));meas=json.load(open(out/'measured/measurement.json'));base=ob['baseline'];topics=ULog(str(run/'flight.ulg'),['research_p12b']);extra=[x for x in topics.data_list if x.name=='research_p12b'];cfgon=bool((run/'gz-motor/read-p12b.bin').exists())
 tests={'observation':ob['status']=='PASS','execution':ex['status']=='PASS','target':target['status']=='PASS','measurement':meas['status']=='MEASURED','source_common_contract':all(v for k,v in source['tests'].items() if k!='native'),'native_enabled_contract':native['status']=='PASS' if on else all(native['shared_state_gates'].values()),'direct_presence_matches_switch':cfgon==on,'zero_ULog_publisher':not extra,'heavy_disabled':not list((run/'gz-motor').glob('dart-solver-*.bin')) and not cfg['p12b']['solver_observe'],'sample_no_loss':base['sample_missed_total']==base['duplicate_total']==base['regressed_total']==0,'sample4ms':base['control_sample_dt_us']['min']==base['control_sample_dt_us']['max']==4000,'cycle_p99':base['whole_observation_cycle_us']['p99']<=2500}
 result={'schema':'p12c-platform-run-engineering-1','status':'PASS' if all(tests.values()) else 'FAIL','tests':tests,'on':on,'on_scope':'source actual pre-read plus shared base state' if on else 'base state only; pre-read initialization intentionally UNOBSERVED, not accepted or synthesized','whole':meas['whole'],'task_outcome':meas['task_outcome'],'censored':meas['censored'],'theory_gate':'NOT_PROVEN_FULL_FEEDBACK, not engineering veto'};write(out/'engineering.json',result)
 if not all(tests.values()):raise RuntimeError('critical P12c platform evidence check failed '+str([k for k,v in tests.items() if not v]))
 if predict:
  tool('p12c/isolated.py',['--packed',out/'packed','--models',models,'--output',out/'prediction'],'prediction');tool('p12/score.py',['--predictions',out/'prediction','--packed',out/'packed','--measurement',out/'measured/measurement.json','--output',out/'score'],'score')
 return meas
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--models',type=Path,required=True);a=p.parse_args();process(a.run,a.output,a.models)
