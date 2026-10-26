import sys,json
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'tools'),str(Path(__file__).parent)]
from hold_axes_v1 import create as old
from hold_axes_v2 import create as new
from p9_model import write,sha
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
for p in sorted((R/'data/p13-20261026-formal-analysis-v2').glob('*/receipt.json')):
 ident=p.parent.name;target=R/'data/p13-20261026-formal'/ident;events=p.parent/'events/event-states.json';a=old(target,events,out/ident/'legacy-v1');b=new(target,events,out/ident/'canonical-v2')
 rows.append({'id':ident,'events':[{'event':x['event'],'legacy_rows':x.get('rows'),'canonical_rows':y.get('rows'),'legacy_position_clip_rows':x.get('position_clip_rows_all3'),'canonical_position_clip_rows':y.get('position_clip_rows_all3'),'legacy_velocity_clip_rows':x.get('velocity_clip_rows_all3'),'canonical_velocity_clip_rows':y.get('velocity_clip_rows_all3'),'native_capture_call_included':y.get('capture_call_included'),'status':y['status']} for x,y in zip(a,b)]})
write(out/'recheck.json',{'schema':'p13-hold-recheck-2','rows':rows,'records':len(rows),'new_source_sha256':sha(Path(__file__).parent/'hold_axes_v2.py'),'no_experimental_change':True,'new_SITL':0});print('RECHECKED_HOLDS',len(rows))
