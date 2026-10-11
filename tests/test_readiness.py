from pathlib import Path
from types import SimpleNamespace as NS
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from readiness import Readiness

def messages(stamp):
    return {'sensor_baro':NS(timestamp=stamp,pressure=101325.,device_id=1),
            'vehicle_air_data':NS(timestamp=stamp,baro_pressure_pa=101325.,baro_device_id=1),
            'vehicle_local_position':NS(timestamp=stamp,xy_valid=True,z_valid=True,x=0,y=0,z=0,vx=0,vy=0,vz=0)}

def test_requires_both_continuity_and_advancing_publications():
    g=Readiness();m=messages(1000000)
    assert not g.update(m,{n:0 for n in m},0)['ready']
    assert not g.update(m,{n:2.1 for n in m},2.1)['ready']
    m=messages(3100000)
    assert g.update(m,{n:2.1 for n in m},2.1)['ready']

def test_stale_pressure_restarts_dwell():
    g=Readiness();m=messages(1000000);g.update(m,{n:0 for n in m},0)
    m=messages(3100000);received={n:2.1 for n in m};received['sensor_baro']=1
    assert not g.update(m,received,2.1)['ready']
    assert not g.update(m,{n:2.2 for n in m},2.2)['ready']

def test_missing_nonfinite_or_different_selected_sensor_is_not_ready():
    g=Readiness();assert not g.update({}, {},0)['ready']
    m=messages(1);m['sensor_baro'].pressure=float('nan')
    assert 'raw pressure invalid' in g.update(m,{n:0 for n in m},0)['reasons']
    m=messages(1);m['vehicle_air_data'].baro_device_id=2
    assert 'selected barometer differs from raw instance0' in g.update(m,{n:0 for n in m},0)['reasons']
