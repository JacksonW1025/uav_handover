"""Offline evidence checks. No firmware, network, simulator or third-party packages."""
import csv,hashlib,json,math
from pathlib import Path
p=Path(__file__).resolve().parent
case=json.loads((p/'case-index.json').read_text())
m=json.loads((p/'metrics.json').read_text())
for f,v in json.loads((p/'checksums.json').read_text()).items():
 assert hashlib.sha256((p/f).read_bytes()).hexdigest()==v,f
def read(f):
 with f.open() as file:return list(csv.DictReader(file))
def tilt(r):return math.degrees(math.acos(math.cos(math.radians(float(r['stabilizer.roll'])))*math.cos(math.radians(float(r['stabilizer.pitch'])))))
def truth(r):return math.degrees(math.acos(float(r['up_z'])))
for name,c in case.items():
 t0=c['marker_host_wall_s']; dt=lambda r:float(r['wall'])-t0
 for f,n in c['files'].items():assert len(read(p/name/f))==n,(name,f)
 if name.startswith('wind'):
  n=read(p/name/'native.csv')
  a=[r for r in n if r['group']=='attitude' and 0<=dt(r)<=1]
  assert abs(max(map(tilt,a))-m[name]['native_attitude_peak_deg'])<1e-8,name
  if name=='wind_high_C':
   z=next(r for r in n if r['group']=='target' and dt(r)>.10 and all(float(r[f'ctrltarget.v{k}'])==0 for k in 'xyz'))
   f=next(r for r in a if tilt(r)>45)
   assert c['status']=='bounded_abort' and dt(f)>dt(z)
   assert abs(dt(f)*1000-m[name]['first_above_45_ms'])<1e-6
 else:
  v=read(p/name/'motor-pwm.csv');a=read(p/name/'plant.csv')
  z=next(r for r in v if dt(r)>0 and not any(int(r[f'pwm{i}']) for i in range(4)))
  assert abs(dt(z)*1000-m[name]['first_zero_pwm_ms'])<1e-6
  eligible=[r for r in a if 0<=dt(r)<=min(1,dt(z)) and all(float(r[f'rpm_target{i}'])>0 for i in range(4))]
  peak=max(eligible,key=truth)
  assert abs(truth(peak)-m[name]['peak_active_truth_deg'])<1e-8,name
  assert abs(dt(peak)*1000-m[name]['peak_active_truth_ms'])<1e-6,name
  assert float(a[-1]['z'])<.07 and not any(int(v[-1][f'pwm{i}']) for i in range(4))
  if name=='mel_sharp_C':assert c['status']=='guard_stop' and truth(peak)>45
  else:assert c['status']=='landed'
r=read(p/'t2-offline-replay.csv');assert len(r)==7
ref=read(p/'mel_smooth_N'/'host.csv')
for a,b in zip(r,ref):
 assert abs(float(a['warm_vx'])-float(b['neural_vx']))<1e-9 and abs(float(a['recorded_reference_vx'])-float(b['ref_vx']))<1e-9
 assert abs(float(a['clear_variant_vx'])-float(a['warm_vx'])-float(a['clear_minus_warm_vx']))<1e-9
assert -0.13<float(r[0]['clear_minus_warm_vx'])<-0.12
assert float(r[3]['warm_vx'])>0>float(r[3]['clear_variant_vx'])
print('PASS: integrity, measured tilt, archived PWM, stopping order and replay table consistency')
