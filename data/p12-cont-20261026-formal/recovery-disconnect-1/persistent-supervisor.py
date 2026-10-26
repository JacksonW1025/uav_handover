#!/usr/bin/env python3
"""Same frozen P12 calls in a persistent host user unit; skip every spent identity."""
import sys,json,datetime
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'))
from p12c.campaign import verify,execute
from p9_model import write
P=R/'data/p12-cont-20261026-preparation';F=R/'data/p12-cont-20261026-formal'
plan,g=verify()
for block in range(1,5):
 for row in plan['rows']:
  if row['block']!=block:continue
  items=[json.loads(s) for s in (P/'attempts.jsonl').read_text().splitlines()]
  if any(s['event'] in ['STOP','EXCEPTION'] for s in items):raise RuntimeError('critical stop present')
  begun=[s for s in items if s['event']=='START_INTENT' and s['id']==row['id']]
  if begun:
   result=F/row['id']/'result.json'
   if result.exists() and json.load(open(result))['evidence_ok']:continue
   recovery=F/row['id']/'interruption.json'
   if row['id']=='b1-ph2-NORMAL1' and recovery.exists() and json.load(open(recovery))['owned_pids_ended']:
    print('SPENT_INVALID_NO_RETRY',row['id'],flush=True);continue
   raise RuntimeError('uncertain existing identity; never relaunch '+row['id'])
  execute(row,g)
 items=[json.loads(s) for s in (P/'attempts.jsonl').read_text().splitlines()];starts=[s for s in items if s['event']=='START_INTENT'];fin=[s for s in items if s['event']=='FINISH' and s['budget_class']=='formal']
 write(F/f'checkpoint-restored-block-{block}.json',{'block':block,'status':'ALL_FROZEN_BLOCK_IDENTITIES_SPENT','old_starts':9,'new_preparation':12,'formal_starts':sum(s['budget_class']=='formal' for s in starts),'valid_formal':sum(s.get('evidence_ok',False) for s in fin),'infra_invalid_formal':sum(not s.get('evidence_ok',False) for s in fin),'cumulative':9+len(starts),'strict_pairs':0,'same_frozen_identity':'68dfb73b26695a630f9fdb2c4534af3797a284a3'})
 print('RESTORED_BLOCK_CLOSED',block,flush=True)
print('ALL48_FROZEN_IDENTITIES_SPENT_NO_EXTRA_STARTS',flush=True)
