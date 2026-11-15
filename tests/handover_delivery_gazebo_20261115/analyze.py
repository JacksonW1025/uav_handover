"""Read-only trace recheck; standard library only, no simulator, no output writes."""
import argparse,struct,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args()
row=struct.Struct('<QQQQQIId'); first={}
for arm in ['normal','lag']:
 raw=(a.input/arm/'motor-0.bin').read_bytes();assert raw[:8]==b'HOMTRC01'
 size,motor=struct.unpack('<II',raw[8:16]);assert size==row.size and motor==0
 assert len(raw[16:])==32*size
 rows=list(row.iter_unpack(raw[16:])); by_time={r[0]:r for r in rows}
 assert by_time[8000][2]==1000
 assert by_time[12000][2]==(4000 if arm=='normal' else 1000)
 first[arm]=next(r[0] for r in rows if r[2]==4000)
 assert first[arm]==(12000 if arm=='normal' else 20000)
assert first['lag']-first['normal']==8000
print(json.dumps({'assertions':'PASS','first_N_sim_us':first,'extra_sim_us':8000,'marker_is_not_generation_time':True}))
