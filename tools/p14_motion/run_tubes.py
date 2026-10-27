import sys,json,resource,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14_motion.tube import run
from p14.common import write,sha

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);cfg=json.load(open(ROOT/'config/p14-motion-offline.json'));P=dict(np.load(ROOT/'data/p13-20261026-freeze/models/policy.npz'));results=[]
 write(out/'seal.json',{'before_compute':True,'protocol_sha256':sha(ROOT/'config/p14-motion-offline.json'),'sources':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'tools/p14_motion').glob('*.py')},'cases':cfg['tube_cases'],'radii':cfg['radius_scales'],'new_SITL':0})
 for case in cfg['tube_cases']:
  doc=json.load(open(ROOT/'data/p14-motion-20261027/inputs-v3'/case/'edge-input.json'));A=doc['plan']['full_source_windows_profile_s'][0];B=doc['plan']['full_source_windows_profile_s'][1]
  # Same planned reference and absolute B time; deleting B never moves it.
  end=max(A[1]+2,B[1]+.5);scales=cfg['radius_scales']+([0] if case=='p13-F2-b1-AB-short' else [])
  for scale in scales:
   for variant in (cfg['tube_variants'] if scale else ['joint']):
    name=f'{case}-r{scale}-{variant}';st=time.perf_counter();r,s=run(doc,P,scale,variant,end=end)
    stages={'64ms':doc['initial']['profile_s']+.064,'planned_hold_and_resume':A[1]+.024,'resume_plus_p5':A[1]+.5,'resume_plus2':A[1]+2,'B_start':B[0],'B_resume':B[1]+.024}
    r['requested_stages']={k:{'end_s':v,'reached':bool(r['last_completed_t']>=v-.0041),'status':'CONDITIONAL_REACHED' if r['last_completed_t']>=v-.0041 else 'BLOCKED_BY_PREDECESSOR_DOMAIN','last_row':next((x for x in reversed(r['rows']) if x['t']<=v),None)} for k,v in stages.items()}
    r['composition_attempt']={'A_to_B_same_internal_state':True,'B_start_s':B[0],'A_reference_end_s':A[1],'reinitialization_at_B':False,'D_reset':False,'rebox_only_at_first_resume':variant=='rebox_at_resume','B_reached_by_tube':r['requested_stages']['B_start']['reached'],'B_successor':r['successor'] if r['requested_stages']['B_start']['reached'] else 'TOP_PREDECESSOR_NOT_CERTIFIED','nominal_end_s':end,'finite_sequence_extension':'same transition operator can iterate arbitrary finite legal words; coverage/precision must be checked at every edge, no claim uniform all-length bound'}
    write(out/name/'tube.json',r)
    np.savez_compressed(out/name/'successor-local.npz',**{k+'_center':v.c for k,v in s.items()},**{k+'_generators':v.pad() for k,v in s.items()})
    results.append({'name':name,'case':case,'scale':scale,'variant':variant,'last_completed_t':r['last_completed_t'],'first_precision_loss':r['first_precision_loss'],'first_domain_loss':r['first_domain_loss'],'requested_stages':r['requested_stages'],'composition':r['composition_attempt'],'elapsed_s':r['elapsed_s'],'peak_rss_kib':r['peak_rss_kib'],'final_generators':r['final_generators']});print('TUBE',name,'last',r['last_completed_t'],'loss',r['first_domain_loss'],'seconds',time.perf_counter()-st,flush=True)
 write(out/'summary.json',{'schema':'p14-motion-tubes-1','records':results,'new_SITL':0,'conditional_model_only':True,'actual_initial_membership':'NOT_ASSERTED','branches':1,'future_actual_words_used':False})
if __name__=='__main__':main()
