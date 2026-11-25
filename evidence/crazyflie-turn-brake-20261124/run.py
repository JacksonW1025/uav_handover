"""Nominal 2-D CrazySim references; switched outer policy still only X."""
import math,pathlib,types
import numpy as np
import cflib.crtp
here=pathlib.Path(__file__).resolve().parent
source=here.parent/'handover-pilot/runner.py'
s=source.read_text()
edits={
 'cf.commander.send_velocity_world_setpoint(sent,clamp(-1.4*y,-.20,.20),vcmdz,0)': 'vyref,py = lateral(t)\n                        vxref = ref\n                        vycmd=clamp(vyref+1.4*(py-y),-.32,.32)\n                        cf.commander.send_velocity_world_setpoint(sent,vycmd,vcmdz,0)',
 'source=source,h_before=h_before,h_after=pol.h,zref=zref,tilt=tilt,**st))':'source=source,h_before=h_before,h_after=pol.h,zref=zref,tilt=tilt,vyref=vyref,pyref=py,pxref=route_x(t),vycmd=vycmd,**st))',
}
for a,b in edits.items():
 assert s.count(a)==1
 s=s.replace(a,b)
runner=types.ModuleType('route_runner')
runner.__file__=str(source)
exec(compile(s,str(source),'exec'),runner.__dict__)
assert runner.SEED==20261123
SW=runner.SW
def smooth(z):return .5-.5*math.cos(math.pi*max(0.,min(1.,z)))
def blend(t,a,w,v0,v1):return v0+(v1-v0)*smooth((t-a)/w)
def vxx(t,amp):
 if t < .7:return amp*smooth(t/.7)
 if kind=='turn_exit':
  if t < 2.49:return blend(t,2.11,.38,amp,.045)
  return blend(t,3.15,.45,.045,0)
 if t < 2.31:return blend(t,2.14,.17,amp,-.19)
 if t < 2.75:return -.19
 return blend(t,2.75,.38,-.19,0)
def vyy(t):
 if kind=='turn_exit':
  if t<2.47:return blend(t,1.93,.54,0,.255)
  return blend(t,3.08,.54,.255,0)
 if t<2.05:return blend(t,1.6,.45,0,.29)
 if t<2.20:return .29
 return blend(t,2.20,.52,.29,0)
runner.target=vxx
cflib.crtp.init_drivers()
for name, kind, mode, port in [
 ('C_turn_exit','turn_exit','classic',29982),('N_turn_exit','turn_exit','normal',29983),
 ('C_turn_brake','turn_brake','classic',29984),('N_turn_brake','turn_brake','normal',29985)]:
 amp=.46
 grid=np.linspace(0.,4.75,4751)
 def integ(fn):
  v=np.array([fn(t) for t in grid]); return np.r_[0,np.cumsum(.0005*(v[1:]+v[:-1]))]
 x,y=integ(lambda t:vxx(t,amp)),integ(vyy)
 runner.route_x=lambda t:float(np.interp(t,grid,x))
 runner.lateral=lambda t:(vyy(t),float(np.interp(t,grid,y))) if t<4.55 else (0.,float(y[-1]))
 runner.ARMS[name]=(amp,mode)
 p=here/name
 p.mkdir(exist_ok=False)
 if runner.run(name,p,port)!='landed':break
