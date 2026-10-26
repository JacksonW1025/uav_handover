#!/usr/bin/env python3
"""Create reviewable P12c freeze after all three engineering gates, never flies."""
import json,sys,shutil,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import sha,write
from p12c_platform.campaign import baseline,P,Z
import p2_batch

def main():
 baseline();a=json.load(open(P/'acceptance.json'))
 if a['engineering_status']!='PASS' or any(v!='PASS' for v in a['gates'].values()):raise RuntimeError('no formal freeze: engineering not released')
 Z.mkdir(exist_ok=False);shutil.copytree(R/'data/p12-cont-20261026-freeze/models',Z/'models');write(Z/'candidate.json',p2_batch.identity());files=dict(json.load(open(P/'preflight-seal.json'))['files']);files.update({str(x.relative_to(R)):sha(x) for x in (Z/'models').iterdir() if x.is_file()});files[str((P/'acceptance.json').relative_to(R))]=sha(P/'acceptance.json');files[str((P/'attempts.jsonl').relative_to(R))]=sha(P/'attempts.jsonl')
 # Preparation ledger necessarily grows during formal; only its pre-formal digest is retained as evidence,
 # not a live frozen mutation check.
 prefix_digest=files.pop(str((P/'attempts.jsonl').relative_to(R)))
 write(Z/'manifest.json',{'schema':'p12c-formal-freeze-1','files':files,'preparation_ledger_sha256':prefix_digest,'case_count':24,'models':'unchanged M3/M4 and baseline variants','minimal_light_on':True,'heavy_solver':False,'theory':'NOT_PROVEN separately; no fit/new candidate','receipt':'after normal commit/push+remote readback, then autonomous formal'})
 print('FREEZE_FILES_CREATED; commit/push/readback before receipt and formal')
if __name__=='__main__':main()
