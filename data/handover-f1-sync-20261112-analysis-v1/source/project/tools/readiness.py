"""Bounded readiness from fresh raw/selected pressure and valid local position."""
import math
class Readiness:
    def __init__(self,dwell_s=2.,max_age_s=.5):
        self.dwell_s=dwell_s;self.max_age_s=max_age_s;self.since=None;self.first={}
    def update(self,latest,received,now):
        names=['sensor_baro','vehicle_air_data','vehicle_local_position']
        reasons=[];stamps={};values={}
        for name in names:
            msg=latest.get(name)
            if msg is None:reasons.append(name+': missing');continue
            stamps[name]=int(msg.timestamp)
            if now-received.get(name,float('-inf'))>self.max_age_s:reasons.append(name+': stale reception')
            if stamps[name]<=0:reasons.append(name+': zero timestamp')
        raw=latest.get('sensor_baro');air=latest.get('vehicle_air_data');local=latest.get('vehicle_local_position')
        if raw is not None:
            values['raw_pressure_pa']=float(raw.pressure);values['raw_device_id']=int(raw.device_id)
            if not math.isfinite(raw.pressure) or raw.pressure<=0:reasons.append('raw pressure invalid')
        if air is not None:
            values['selected_pressure_pa']=float(air.baro_pressure_pa);values['selected_device_id']=int(air.baro_device_id)
            if not math.isfinite(air.baro_pressure_pa) or air.baro_pressure_pa<=0:reasons.append('selected pressure invalid')
        if raw is not None and air is not None and (not raw.device_id or raw.device_id!=air.baro_device_id):reasons.append('selected barometer differs from raw instance0')
        if local is not None:
            if not local.xy_valid or not local.z_valid:reasons.append('local position invalid')
            if not all(math.isfinite(float(getattr(local,k))) for k in ['x','y','z','vx','vy','vz']):reasons.append('local state nonfinite')
        if reasons:self.since=None;self.first={}
        elif self.since is None:self.since=now;self.first=stamps.copy()
        # Both host dwell and advancing native publications are required.
        advancing=bool(self.first) and all(stamps.get(n,0)-self.first[n]>=self.dwell_s*1e6 for n in names)
        ready=not reasons and advancing and now-self.since>=self.dwell_s
        return {'ready':bool(ready),'reasons':reasons,'continuous_host_s':now-self.since if self.since is not None else 0.,'native_publication_stamps':stamps,**values}
