#!/usr/bin/env python3
"""Create the P11 fixed 72-row protocol, no SITL, no result reads."""
import copy
import hashlib
import json
import random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def seed(name):return int.from_bytes(hashlib.sha256(('P11-20261025|'+name).encode()).digest()[:4],'big')&0x7fffffff


def build():
    if (ROOT/'config/p11.json').exists():raise FileExistsError('never overwrite a generated/frozen P11 plan')
    src=ROOT/'config/p9.json';old=json.loads(src.read_text());plan_path=ROOT/'data/p9-20261024-freeze/plan.json';oldplan=json.loads(plan_path.read_text())
    dev=json.loads((ROOT/'data/p11-20261025-preparation/dev-observe-config.json').read_text())
    families=[
      {'id':'F1','condition':'p9-dev-arm-1','source_config':'data/p9-20261024-preparation/design-v2/config.json','events':[0,1],'group':'G15','split':'development'},
      {'id':'F2','condition':'p9-B-P9-Z-h15-g0.7','events':[0,2],'group':'G15','split':'development'},
      {'id':'F3','condition':'p9-D-07','events':[0,1],'group':'G20','split':'development'},
      {'id':'F4','condition':'p9-B-P9-Z-h45-g0.55','events':[0,1],'group':'G45','split':'heldout'},
      {'id':'F5','condition':'p9-D-08','events':[0,1],'group':'G50','split':'heldout'},
      {'id':'F6','condition':'p9-B-P9-Z-h75-g0.1','events':[0,1],'group':'G75','split':'heldout'}]
    def config(fam):
        c=copy.deepcopy(old);c.pop('p9',None)
        c['p5']['conditions']={}
        path=ROOT/fam.get('source_config','config/p9.json');source=json.loads(path.read_text())
        spec=copy.deepcopy(source['p5']['conditions'][fam['condition']]);c['p5']['conditions']['p11-case']=spec
        c['p5']['treatments']={'P11-Z':{'rini':4,'nco':0,'rtgt':0,'rtdec':2.,'rrec':0.,'description':'P11 unchanged T0'},
            'P11-C':{'rini':4,'nco':0,'rtgt':2,'rtdec':2.,'rrec':0.,'description':'P11 existing speed-matched all captures; RTDEC2'}}
        c['p11']={'schema':'p11-frozen-1','observe':True,'runner_trace':True,'ulog_storage':'hardlink_after_shutdown',
            'source':{'path':str(path.relative_to(ROOT)),'sha256':sha(path),'condition':fam['condition'],'spec_sha256':hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()},
            'budget':{'development_cap':12,'formal_cap':72,'total_cap':84},'event_mask':fam['events'],'event_shift_s':0.,
            'group':fam['group'],'model_split':fam['split'],'original_p5_frozen_criterion':old['p5']['failure_criteria'],
            'task_criterion':{'tilt_deg':45.,'tilt_operator':'>','altitude_loss_m':1.,'altitude_loss_operator':'>'},
            'observation_version':'complete-hook-v2','prediction_terminal_slack_s':.5}
        return c
    rows=[];blocks=[[],[],[],[]]
    def add(fam,rep,branch,mask,stage='main',shift=0.):
        cfg=config(fam);cfg['p11']['event_mask']=mask;cfg['p11']['event_shift_s']=shift
        name=f"{fam['id']}-r{rep}-{branch}"
        rel=f'config/p11-cases/{name}.json';write(ROOT/rel,cfg)
        row={'id':name,'stage':stage,'family':fam['id'],'group':fam['group'],'split':fam['split'],'rep':rep,'branch':branch,
            'config':rel,'config_sha256':sha(ROOT/rel),'condition':'p11-case','kind':'p5_gap','treatment':'P11-C' if branch=='REPAIR' else 'P11-Z',
            'event_mask':mask,'event_shift_s':shift,'sim_seed':seed(fam.get('seed_family',fam['id'])+f'/r{rep}'),'initial_yaw_deg':0.,
            'status':'PENDING','trajectory_fixed':True}
        rows.append(row);block=(rep-1) if fam['split']=='development' else rep+1;blocks[block].append(name)
    for f in families:
        A,B=f['events']
        for rep in [1,2]:
            for branch,mask in [('NORMAL',[]),('A',[A]),('B',[B]),('AB',[A,B]),('REPAIR',[A,B])]:add(f,rep,branch,mask)
    for rep in [1,2]:
        f=dict(families[0],id='ANCHOR-A4',events=[0,1,2],seed_family='F1');add(f,rep,'ORIGINAL',[0,1,2],'anchor')
        for source in ['D-03-P9-Z','D-09-P9-Z']:
            r=next(x for x in oldplan['runs'] if x['id']==source)
            f={'id':'ANCHOR-'+source[:4],'condition':r['condition'],'events':list(range(len(r['case']['windows_s']))),
                'group':'G80','split':'heldout'}
            add(f,rep,'ORIGINAL',f['events'],'anchor')
        for phase in [0.,.002,.006]:
            f=dict(families[0],id='PHASE'+str(round(phase*1000)),seed_family='F1')
            add(f,rep,'AB',[0,1],'phase',phase)
    for i,b in enumerate(blocks):random.Random(2026102511+i).shuffle(b)
    assert len(rows)==72 and len({x['id'] for x in rows})==72
    top={'schema':'p11-frozen-1','baseline':'1bf072c01c3fd57e939e367bc2407b17b916cd80',
        'budget':{'observation_development_cap':12,'formal_cap':72,'total_cap':84,'main':60,'anchors':6,'phases':6},
        'family_sources':families,'rows':rows,'execution_blocks':[{'index':i,'split':'development' if i<2 else 'heldout','ids':b} for i,b in enumerate(blocks)],
        'group_separation':{'development':['G15','G20'],'heldout':['G45','G50','G75','G80'],'phase_variants_never_cross_split':True},
        'model_forms':{'M0':'literal A4/P9 gains,4ms22slot p/v/q; causal self-generated capture targets, no future logs',
            'M1':'exact Dense/GRU/previous action/history; named LP8ms hold and attitude4ms transport; 13-state plant effective thrust/drag/torque coefficients; latest-command4ms transport',
            'M2':'M1 plus4 rotor-speed filter states, source asymmetric tau_up.0125/down.025; no further model class'},
        'fit':{'reads':'ONLY formal development groups; observation-development flights validate mechanisms and code, not heldout model selection',
            'least_squares':'bounded shared thrust in[0,20],three drag[0,5],three torque[-1000,1000],three angular drag[0,20]; velocity derivative only new LP samples',
            'M2_states':'4 execution states fixed from source; no GRU reduction or new neural weights',
            'selection':'retain all3; training full causal rollout p/v/tilt and predicted safety/censoring reports, select smallest normalized score if complete; freeze models before heldout phase',
            'no_timepoint_split':True,'no_post_holdout_modifications':True},
        'prediction_information':{'allowed':'one pre-stream initial state and initial clocks/history; SOURCE-generated task table and planned events; frozen model/weights',
            'forbidden':'future actual targets/observations/hidden states, actual event or termination times',
            'isolation':'bubblewrap read-only root with repository data and export hidden; only sanitized initial+plan+model inputs mounted; score runs outside sandbox',
            'future_clock':'nominal declared4ms control/8ms hold,20ms minimum publication; deterministic allowed subclass, not guaranteed actual scheduler'},
        'measurement':{'window':'common source first planned gap through source post_stream end, including no-event arm; full profile and poststream exported',
            'early_stop':'right censored; no imputed tail; known failure counts even with censored peak; unknown remains unknown',
            'pairs':'fixed warmup/task/seed, report pre-first-event .5s p/v/geodesic attitude/action/hidden differences; not exact snapshot',
            'pre_match_thresholds':{'position_m':.1,'velocity_m_s':.15,'SO3_deg':2.5,'action_max':.1,'hidden_l2':.5},
            'combination':'same absolute profile time and source trajectory; deltaAB-deltaA-deltaB; no alignment by shifted actual capture',
            'phase':'intent 0/2/6ms; actual read/LP phase and clock intervals; overlapping achieved distributions => NOT_IDENTIFIABLE',
            'primary_and_task':'original p5.failure_criteria and task tilt>45deg/altitude loss>1m side by side',
            'recovery':'original P0 bands .2m/.1m_s/.1rad_s continuous2s, gaps>20ms break continuity; after final capture at stopped trajectory',
            'model_evaluation':'one-step known-input and .5s/2s/full self-evolving rollouts; p/v/SO3/action/h/altitude where modelled; danger misses/false alarms/UNKNOWN, costs and repair ranking, success and failures separated'},
        'stops':{'new_error':'STOP affected formal batch; preserve evidence; no retry/new version bypass',
            'critical_observation':'STOP for missing control calls, invalid replay, identity confusion, protection anomaly',
            'infrastructure_pending':'same-semantic pending continuation only after stopped processes/unique identity/output audit; every begun id permanently counted and never rerun',
            'budget':'no quota borrowing or extra replacement flights','other_batches':'P12/P10 B/C/D forbidden'},
        'source_hashes':{str(src.relative_to(ROOT)):sha(src),str(plan_path.relative_to(ROOT)):sha(plan_path)}}
    write(ROOT/'config/p11.json',top)
    return top


if __name__=='__main__':
    p=build();print('Created',len(p['rows']),'rows; blocks',list(map(lambda b:len(b['ids']),p['execution_blocks'])))
