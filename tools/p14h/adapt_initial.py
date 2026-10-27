"""Recover actual past cache stamps; never infer age from phase modulo alone."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14h.common import *
from p12c.features import load

def adapt(doc,run,analysis):
 d=json.loads(json.dumps(doc));i=d['initial'];x=load(run,analysis);j=int(np.flatnonzero((x['sample_us']==i['sample_us'])&(x['native_us']<=i['native_us']))[-1]);assert int(x['run_wall_ns'][j])<=i['observer']['cutoff_wall_ns'];i['att_cache_sample_us']=int(x['att_sample'][j]);i['LP_cache_sample_us']=int(x['lp_sample'][j]);i['p14h_schedule_model']={'version':'source-producer-state-1','future_OP_lag_us_nominal':4000,'initial_backlog_is_state_not_future_delay':True,'producer_stage':'PRE_COMPLETE','att_extra_delivery_us':0,'unknown_future_modes':'initial/source4ms queues retained; PRE_COMPLETE isnominal, source LPthenAtt/interposed/POST cases need explicitbranch, notallfuturecoverage'}
 return d,{'cutoff_wall_ns':i['observer']['cutoff_wall_ns'],'source_row_wall_ns':int(x['run_wall_ns'][j]),'known_att_cache_sample':i['att_cache_sample_us'],'known_LP_cache_sample':i['LP_cache_sample_us'],'OP_completed_sample':i['observer']['latest_completed_update_sample_us'],'modulo_phase_not_age':True,'future_actual_used':False}

def main():
 out=register(sys.argv[1],'recovercacheages and sourceproducer initialpending fromexactpast rows, nofuture timingword');rows=[]
 for n,review in [(1,'review-d01-v1'),(2,'review-d02-v3'),(3,'review-d03-v1'),(4,'review-d04-v3')]:
  target=next((B/'runs').glob(f'p14h-d{n:02d}-*'));info=json.load(open(target/('information-v2.json' if (target/'information-v2.json').exists() else 'information.json')));a=R/info['source_analysis'] if info.get('source_analysis') else target/'analysis-v1';d=json.load(open(B/review/'source-initial/input.json'));d,proof=adapt(d,target/'run',a);write(out/f'd{n:02d}/input.json',d);rows.append({'id':n,**proof,'input_sha256':sha(out/f'd{n:02d}/input.json')})
 write(out/'result.json',{'rows':rows,'primary_candidate':'one sourceproducer/backlog/cache-state correction afterfiniteerrorstate feasibility trial','rejected_aiding_model':'feedback-fit-v1 theta unconstrainedrate negative; positive-aidingprototype not assertedclosed, retainedfinite comparison only','state_dimensions':'physical/estimatedq separate, OP ring andoutbox/pendingcache; nohistoryorDreset','no_future_measurements_used':True});print('CACHE_INITIALS_ADAPTED',len(rows))
if __name__=='__main__':main()
