#!/usr/bin/env python3
"""Independent P12b IDs; retain pending source order, never replace old starts."""
import sys,json,random
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import write,sha
P=R/'data/p12b-20261026-preparation';C=R/'config/p12b-cases'
LIB='data/p12b-20261026-source-local/libP12bDartTrace.so'
def config(source,observe=True,solver=True,split='heldout'):
 c=json.load(open(R/source));c['p12b']={'schema':'p12b-pre-read-and-dart-2','observe':observe,'solver_observe':solver,'solver_library':LIB};c['p11']['schema']='p12b-independent-1';c['p11']['model_split']=split;c['p11']['budget']={'old_P12_starts':48,'preparation_cap':8,'formal_cap':45,'P12b_cap':53,'all_P12_cap':101};return c

def main():
 if (R/'config/p12b.json').exists():raise FileExistsError('no design overwrite')
 C.mkdir(exist_ok=False);old=json.load(open(R/'config/p12-cont.json'));pending=json.load(open(R/'data/p12-cont-20261026-delivery-v2/startup-exclusion-ledger.json'));ids={r['id'] for r in pending if r['status']=='NOT_STARTED'};rows=[]
 for o in old['rows']:
  if o['id'] not in ids:continue
  row=dict(o,id='carry-'+o['id'],source_id=o['id'],source_input_sha256=o['config_sha256'],cohort='old21_new_protocol',old_ordinal=old['rows'].index(o)+1);path=C/(row['id']+'.json');write(path,config(o['config']));row.update(config=str(path.relative_to(R)),config_sha256=sha(path));rows.append(row)
 assert len(rows)==21
 rng=random.Random(2026102612)
 for block,seed in [(5,1334275356),(6,1334276365)]:
  candidates=[]
  for phase in [1,2]:
   for branch in ['NORMAL0','NORMAL1','A','B','AB','REPAIR']:
    source=next(r for r in old['rows'] if r['block']==2 and r['phase']==phase and r['branch']==branch);row=dict(source,id=f'new-b{block}-ph{phase}-{branch}',source_id=source['id'],source_input_sha256=source['config_sha256'],cohort='new24_F4_cross_block',block=block,sim_seed=seed);path=C/(row['id']+'.json');write(path,config(source['config']));row.update(config=str(path.relative_to(R)),config_sha256=sha(path));candidates.append(row)
  rng.shuffle(candidates);rows.extend(candidates)
 write(R/'config/p12b.json',{'schema':'p12b-design-1','baseline':'62f0ad947d94c0f0ea60e753f64d8c7ce6611dee','caps':{'preparation':8,'formal':45,'total':53,'old_P12':48,'cumulative':101},'rows':rows,'randomization':{'seed':2026102612,'algorithm':'random.Random shuffle all12 labels within new block; carry21 original frozen order','new_block_seeds':{'5':1334275356,'6':1334276365},'independence':'two read strategies within one seed/block are not independent blocks'},'primary':'two NEW complete F4 blocks; per assigned gate A/B success vs AB failure, margin and REPAIR-AB effects; no achieved-phase/survival selection','carry21_scope':'source cases under new pre-read audit/observer; source associations exact; cannot splice old/new acceptance or call cross-version block a pure P12b complete block','effect_scales':{'tilt_deg':5,'height_loss_m':.2,'tracking_m':.2,'source':'unchanged old pre-frozen P12 safety/task/recovery scale; not P12b outcomes'},'models':'unchanged M3/M4 and existing baseline variants; zero new candidate and no refit','theory_gate':'separate NOT_PROVEN; not an experimental stop','clock_scope':'nominal native strategy; no new catchup intervention','stop_rules':'critical observation/identity/source semantics/protection error stops affected queue; scientific failures retained; defined infra interruption: confirm owned processes ended and unchanged frozen input before continuing never-started identities only; no replacements','analysis':'event tables and fixed pre-A .5s covariates; raw blocked contrasts primary; record cache differences; no strict same-initial claim; F4 new blocks n<=2 descriptive range, no population certainty; historic F4 block separately cross-version sensitivity; primary/task/world/prefix/window denominators distinct'})
 prep=[]
 for n,fam,phase,branch,on in [(1,'F2',2,'NORMAL0',False),(2,'F2',2,'NORMAL0',True),(3,'F2',2,'NORMAL0',True),(4,'F4',1,'AB',False),(5,'F4',1,'AB',True),(6,'F4',2,'AB',True),(7,'F4',1,'REPAIR',True),(8,'F4',2,'REPAIR',True)]:
  source=next(r for r in old['rows'] if r['family']==fam and r['phase']==phase and r['branch']==branch);ident=f'prep{n:02d}-{fam}-ph{phase}-{branch}-'+('on' if on else 'off');path=P/(ident+'.json');write(path,config(source['config'],on,on,'development'));prep.append({'id':ident,'ordinal':n,'family':fam,'phase':phase,'branch':branch,'observe':on,'solver_observe':on,'config':str(path.relative_to(R)),'config_sha256':sha(path),'sim_seed':1334270311,'source_id':source['id'],'kind':'p5_gap','condition':'p11-case','treatment':'P11-Z','split':'development'})
 write(P/'protocol.json',{'schema':'p12b-preparation-protocol-1','rows':prep,'starts_before_protocol':0,'no_retry':True,'on_off_scope':'same compiled candidate, only passive observation switches differ; not a deterministic state fork','observational_behavior_gates':{'known_input_replay':'existing P11/P12 tolerances unchanged','full_cycle_p99_us':2500,'output_age_us_max':8000,'same_branch_tilt_difference_deg':5,'same_branch_loss_difference_m':.2,'basis':'unchanged meaningful-effect/latency envelope; compare on/off and same-on repeat, retain actual prestate/caches','solver_relation_rad_s':1e-7,'solver_relation_scope':'independent matrix eta, actual post velocity, source command clipping/modes; empirical numerical check not future bound'},'discrete_continuous_MME':'separate inherited P12 diagnostics, never outcome exclusion','scope':'all8 fixed before flight; failures count, no unused prep transfer','abnormal_classification':'critical new log/identity/protocol/safety error stops affected protocol; scientific failure retained; infra recovery only unchanged candidate, owned processes ended, unstarted IDs'})
 print('DESIGN_CREATED formal45 carry21 new24; prep8; no starts')
if __name__=='__main__':main()
