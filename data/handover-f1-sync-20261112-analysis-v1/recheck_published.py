"""Read-only, standard-library review of the frozen F1 evidence. No flight."""
import csv, gzip, hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
m=json.loads((HERE/'freeze-manifest.json').read_text())
for row in m['files']:
    p=ROOT/row['path']
    assert p.stat().st_size==row['bytes'],p
    assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],p
summary=json.loads((HERE/'f1-summary.json').read_text())
assert len(summary['rows'])==6
for row in summary['rows']:
    d=HERE/(row['case']+'-a1')
    with gzip.open(d/'physical-attitude.csv.gz','rt') as f: a=list(csv.DictReader(f))
    with gzip.open(d/'physical-position.csv.gz','rt') as f: z=list(csv.DictReader(f))
    peak=max(float(x['tilt_deg']) for x in a)
    loss=max(float(x['altitude_loss_entry_m']) for x in z)
    assert abs(peak-row['physical']['peak_tilt_deg'])<1e-8
    assert abs(loss-row['physical']['altitude_loss_entry_m'])<1e-6 # CSV float32 text rounding
    chain=row.get('chain')
    gap=None
    if chain:
        gap=(chain['first_read_us']-chain['first_four_application_us'])/1000
        assert gap==chain['first_read_minus_first_four_ms']
        assert len(chain['four_motor_records'])==4
        assert chain['first_send']['before_ns']>max(x['step_wall_ns'] for x in chain['four_motor_records'])
    print(row['case'],f'tilt={peak:.3f}deg loss={loss:.3f}m reference_gap={gap}ms')
print('PASS:',len(m['files']),'file hashes; six native trajectory maxima; four switch timing chains.')
