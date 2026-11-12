"""Read-only stdlib verification of published derived evidence; no SITL or ULog required."""
import csv,gzip,hashlib,json,math
from pathlib import Path
A=Path(__file__).resolve().parent
R=A.parents[1]
load=lambda p:json.loads(p.read_text())
for r in load(A/'publication-source-manifest.json'):
 p=R/r['path'];assert p.stat().st_size==r['bytes'];assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],p
rows=[]
for folder in sorted(A.glob('*-a1')):
 def read(n):
  with gzip.open(folder/n,'rt') as f:return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
 z=load(folder/'score.json');v=read('V-native.csv.gz');att=read('physical-attitude.csv.gz');pos=read('physical-position.csv.gz')
 values=[(r['ev_m_s']/2)**2+(r['tilt_deg']/45)**2+.25*(r['omega_rad_s']/2)**2 for r in v]
 residual=[x-values[0]*math.exp(-.5*(r['t_s']-v[0]['t_s'])) for x,r in zip(values,v)]
 for x,r,m in zip(values,v,residual):
  assert math.isclose(x,r['V'],abs_tol=1e-10);assert math.isclose(m,r['growth_margin'],abs_tol=1e-10)
 g=sum(max(m for m,r in zip(residual,v) if r['t_s']<=h+1e-9) for h in [.1,.12,.16])/3
 peak=max(r['tilt_deg'] for r in att);loss=max(r['altitude_loss_entry_m'] for r in pos)
 assert math.isclose(g,z['G_mean_100_120_160'],abs_tol=1e-10)
 assert math.isclose(peak,z['physical']['peak_tilt_deg'],abs_tol=1e-8)
 assert math.isclose(loss,z['physical']['altitude_loss_entry_m'],abs_tol=1e-6)
 rows.append((folder.name.removesuffix('-a1'),g,v[0]['ev_m_s'],peak))
 print(folder.name,'G=',round(g,6),'tilt=',round(peak,6),'loss=',round(loss,6))
sel=load(A/'prospective-selection.json');pilots=rows[:4]
assert max(pilots,key=lambda x:x[1])[0]==sel['V_parent'];assert max(pilots,key=lambda x:x[2])[0]==sel['speed_parent']
ledger=[json.loads(l) for l in (R/'data/handover-physical-v-20261112/attempts.jsonl').read_text().splitlines()]
for event in ['START_INTENT','PHYSICAL_END','END']:assert sum(r['event']==event for r in ledger)==6
children=[r for r in ledger if r['event']=='START_INTENT' and r['case'].startswith(('005','006'))]
assert all(sel['created_ns']<r['time_ns'] for r in children)
assert sum(r[3]>45 for r in rows)==5
print('PASS: source hashes, six scores/physical summaries, two selections, pre-launch ordering and 18 ledger rows. Derived data consistency is not an independent ULog audit.')
