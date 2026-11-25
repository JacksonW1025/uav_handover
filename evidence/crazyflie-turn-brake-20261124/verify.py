"""Verify the published turn-brake evidence offline; no simulator required."""
import bisect, csv, hashlib, json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
manifest = json.loads((ROOT / 'manifest.json').read_text())
metrics = json.loads((ROOT / 'metrics.json').read_text())

def rows(case, filename):
    path = ROOT / case / filename
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest['files'][f'{case}/{filename}']['published_sha256']
    with path.open() as stream:
        values = list(csv.DictReader(stream))
    assert len(values) == manifest['files'][f'{case}/{filename}']['published_rows']
    return values

def sample(data, at, keys):
    i = bisect.bisect_left([float(r['wall']) for r in data], at)
    assert 0 < i < len(data)
    a,b=data[i-1:i+1]
    f=(at-float(a['wall']))/(float(b['wall'])-float(a['wall']))
    return [float(a[k])+f*(float(b[k])-float(a[k])) for k in keys]

for case in ('C_turn_brake','N_turn_brake'):
    host = rows(case,'host.csv'); native = rows(case,'native.csv')
    first = next(r for r in host if float(r['t']) >= 2.2)
    assert first['source'] == case[0] and first['ref'] == first['nref']
    t0 = float(first['wall'])
    p = [r for r in native if r['group']=='position']
    a = [r for r in native if r['group']=='attitude']
    m = [r for r in native if r['group']=='motors']
    target = [r for r in native if r['group']=='target']
    assert all(int(m[-1][f'motor.m{i}req'])==0 for i in range(1,5))
    assert float(p[-1]['stateEstimate.z']) < 0.075
    adopt=next(r for r in target if 0<=float(r['wall'])-t0<=.14 and all(abs(float(r[f'ctrltarget.v{k}'])-float(first[fld]))<1e-5 for k,fld in [('x','sent_vx'),('y','vycmd')]))
    assert abs((float(adopt['wall'])-t0)*1000-metrics[case]['first_pair_firmware_target_callback_ms'])<1e-6
    for dt in (.3,.4):
        vx,vy = sample(p,t0+dt,('stateEstimate.vx','stateEstimate.vy'))
        roll,pitch=sample(a,t0+dt,('stabilizer.roll','stabilizer.pitch'))
        tilt=math.degrees(math.acos(math.cos(math.radians(roll))*math.cos(math.radians(pitch))))
        v=metrics[case]['phases'][str(dt)]
        assert abs(vx-v['vx'])<1e-6 and abs(vy-v['vy'])<1e-6 and abs(tilt-v['tilt'])<1e-6
        aim,=sample(host,t0+dt,('ref',))
        assert math.isclose(aim,-.19)
        print(f'{case} +{dt:.2f}s: vx={vx:+.6f}, vy={vy:+.6f} m/s, bearing from +Y={math.degrees(math.atan2(vx,vy)):+.3f}°, tilt={tilt:.3f}°')
    s=json.loads((ROOT/case/'summary.json').read_text())
    assert s['status']=='landed' and s['seed']==manifest['seed'] and not s['errors']
print('PASS: source, reference, observed target, motion and landing evidence')
