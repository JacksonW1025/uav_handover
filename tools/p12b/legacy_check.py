"""Old logs lack pre-read readiness: separate inference, never old validity rewrite."""
import json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import write,sha
out=R/'data/p12b-20261026-preparation/legacy-contract-review.json'
if out.exists():raise FileExistsError(out)
rows=[]
for p in sorted((R/'data/p12-cont-20261026-formal').glob('*/analysis/native/native-audit.json')):
 old=json.load(open(p));run=p.parents[2]/'run';d=next(x.data for x in ULog(str(run/'flight.ulg'),['research_p12']).data_list if x.name=='research_p12');m=d['active'].astype(bool);bypass=(d['call_index_before']==0)&d['gate_permit'].astype(bool)&(d['requested_phase']==2)&m
 rows.append({'id':run.parent.name,'old_status_unchanged':old['status'],'old_audit_sha256':sha(p),'pre_read_state_available':False,'initialization_inference':'at index0 active PH2 permit implies initialized=false OR force_sync=0 under source; cannot select one or fill old fields','index0_permit_samples':d['timestamp_sample'][bypass].tolist(),'new_retrospective_acceptance':'UNKNOWN_READINESS_NOT_RECLASSIFIED'})
write(out,{'schema':'p12b-legacy-contract-review-1','records':rows,'scope':'no new observations invented for old logs; original FAIL and other validity retained','SITL_starts':0});print('LEGACY_REVIEW',len(rows))
