"""Apply unchanged1mm airborne check to full research phase, retain full-run FAIL.
Original optional task_end parameter was omitted by campaign, admitting classic
LAND/contact cleanup into a task-airborne approximation. No threshold changes.
"""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'tools'),str(Path(__file__).parent)]
from p13.physics import analyze,read,BODY
from p9_model import write,sha
from analysis_paths_v1 import analysis_dir

def validate(target,out):
 run=target/'run';a=analysis_dir(target);legacy=json.load(open(a/'physics/physics.json'));ev=[json.loads(s) for s in (run/'events.jsonl').read_text().splitlines()];send=[json.loads(s) for s in (run/'p11-sends.jsonl').read_text().splitlines()];start=round(next(s['stream_t0_monotonic_s'] for s in send if s['stream_t0_monotonic_s'] is not None)*1e9);doc=json.load(open(a/'packed/prediction-input.json'));failed=[v for v in ev if v['event']=='failure'];classic=[v for v in ev if v['event']=='p1_phase_started' and v.get('label')=='return_classic']
 if failed:end=failed[0]['monotonic_ns'];boundary='unchanged scientific failure/valid prefix boundary'
 elif classic:end=classic[0]['monotonic_ns'];boundary='actual return_classic phase entry, includes complete poststream and neural-to-classic transition'
 else:raise RuntimeError('missing explicit research task terminal')
 if not failed and end<start+round(doc['plan']['nominal_horizon_profile_s']*1e9):raise RuntimeError('research phase ended before fixed task horizon')
 report=analyze(run,out,task_start_ns=start,task_end_ns=end);other=all(v for k,v in legacy['gates'].items() if k!='integration_check');b,_=read(run/'gz-motor/physics-p13-body.bin',BODY,b'P13BODY1');p=b[(b['phase']==1)&(b['wall_ns']>=start)&(b['valid']==63)];dt=np.diff(p['sim_ns'])/1e9;res=np.linalg.norm(np.diff(p['com_p'],axis=0)-p['com_v'][1:]*dt[:,None],axis=1);bad=np.flatnonzero(res>.001);lands=[v for v in ev if v['event']=='command_requested' and v.get('command')==21];badinfo=[{'profile_s':(int(p['wall_ns'][j+1])-start)/1e9,'step':int(p['step'][j+1]),'residual_m':float(res[j]),'origin_H_m':float(p['origin_p'][j+1,2]),'COM_H_m':float(p['com_p'][j+1,2]),'after_research_phase':int(p['wall_ns'][j+1])>end,'after_explicit_LAND_command':bool(lands and int(p['wall_ns'][j+1])>lands[0]['monotonic_ns'])} for j in bad];ok=report['status']=='PASS' and other and all(x['after_research_phase'] and x['after_explicit_LAND_command'] for x in badinfo)
 result={'schema':'p13-physics-phase-applicability-4','id':target.name,'decision':'PASS_RESEARCH_PHASE_WITH_FULL_RAW_COVERAGE' if ok else 'FAIL','unchanged_threshold_m':.001,'legacy_fullrun_status_preserved':legacy['status'],'legacy_fullrun_integration_max_m':legacy['metrics']['COM_semiimplicit_position_step_residual_m'],'all_other_fullrun_gates_pass':other,'research_phase_boundary':boundary,'research_window_profile_s':[0,(end-start)/1e9],'fixed_nominal_horizon_profile_s':doc['plan']['nominal_horizon_profile_s'],'scoped_integration_max_m':report['metrics']['COM_semiimplicit_position_step_residual_m'],'out_of_research_phase_violations':badinfo,'contact_mode':'physical source getters/fields retained. Landing near plane violates airborne semiimplicit approximation; no new lambda/contact-mode data fabricated or claim of all-contact dynamic certification.','raw_body_sha256':sha(run/'gz-motor/physics-p13-body.bin'),'source_sha256':sha(Path(__file__)),'experimental_layer_changes':False,'new_SITL':0};write(out/'scope-decision.json',result)
 if not ok:raise RuntimeError('scope cannot restore trustworthy physical evidence '+target.name)
 return result
if __name__=='__main__':validate(Path(sys.argv[1]),Path(sys.argv[2]))
