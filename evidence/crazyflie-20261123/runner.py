"""Single-aircraft CrazySim SITL, host outer-loop C->learned; no hardware route."""
import argparse,csv,json,math,os,pathlib,signal,socket,subprocess,sys,threading,time
import numpy as np
import cflib.crtp
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
ROOT=pathlib.Path(__file__).resolve().parents[1]
SIM=ROOT/'CrazySim/crazyflie-firmware/tools/crazyflie-simulation/simulator_files/mujoco/crazysim.py'
SEED=20261123
DT=.04
SW=2.2
ARMS={
 'C_fast':(.47,'classic'), 'N_fast':(.47,'normal'),
 'C_slow':(.22,'classic'), 'N_slow':(.22,'normal'),
 'H_clear':(.22,'clear'), 'R_stale':(.22,'stale'), 'D_hold':(.22,'hold'),
}
def clamp(x,a,b): return float(np.clip(x,a,b))
class Learned:
    def __init__(self):
        rng=np.random.default_rng(SEED)
        self.w=rng.normal(0,.55,(3,24))
        self.b=rng.normal(0,.12,24)
        self.h=0.
        # Fixed random tanh recurrent features with a learned scalar readout.
        # Imitation target is a smooth classical feedforward outer loop.
        xx=[]; yy=[]
        for _ in range(150):
            u,h=0.,0.
            for i in range(100):
                if i%10==0: u=rng.uniform(-.24,.24)
                v=clamp(h+rng.normal(0,.045),-.26,.26)
                h=.91*h+.09*u
                xx.append(self.features(u,v,h))
                yy.append(.65*u+.35*h+.20*(u-v))
        X=np.asarray(xx); Y=np.asarray(yy)
        self.out=np.linalg.solve(X.T@X+0.05*np.eye(X.shape[1]),X.T@Y)
        self.fit_rmse=float(np.sqrt(np.mean((X@self.out-Y)**2)))
    def features(self,u,v,h):
        return np.r_[np.tanh(np.array([u,v,h])/.22@self.w+self.b),1.]
    def step(self,u,v):
        self.h=.91*self.h+.09*u
        return clamp(self.features(u,v,self.h)@self.out,-.53,.53)

def target(t,amp):
    if t<0: return 0.
    if t<.7: return amp*(1-math.cos(math.pi*t/.7))/2
    if t<SW: return amp
    return -.05 if t<SW+.75 else 0.

class Telemetry:
    def __init__(self,cf):
        self.latest={}; self.raw=[]; self.lock=threading.Lock(); self.cfgs=[]
        groups={
         'position':['stateEstimate.x','stateEstimate.y','stateEstimate.z','stateEstimate.vx','stateEstimate.vy','stateEstimate.vz'],
         'attitude':['stabilizer.roll','stabilizer.pitch','stabilizer.yaw'],
         'target':['ctrltarget.vx','ctrltarget.vy','ctrltarget.vz'],
         'motors':['motor.m1req','motor.m2req','motor.m3req','motor.m4req'],
        }
        for group,names in groups.items():
            cfg=LogConfig(group,20)
            for n in names: cfg.add_variable(n)
            cf.log.add_config(cfg)
            cfg.data_received_cb.add_callback(self.capture)
            cfg.start(); self.cfgs.append(cfg)
    def capture(self,ts,data,cfg):
        now=time.monotonic()
        with self.lock:
            self.latest.update(data); self.latest[cfg.name+'_wall']=now
            self.raw.append(dict(wall=now,firmware_ms=ts,group=cfg.name,**data))
    def state(self):
        with self.lock: return dict(self.latest)
    def close(self):
        for cfg in self.cfgs: cfg.stop()

def clean_processes(sim,docker,name):
    if sim.poll() is None: sim.terminate()
    if docker is not None:
        subprocess.run(['docker','stop','--time','2',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=7)
        try: docker.wait(timeout=3)
        except subprocess.TimeoutExpired: docker.terminate(); docker.wait(timeout=3)
    try: sim.wait(timeout=3)
    except subprocess.TimeoutExpired: sim.kill(); sim.wait(timeout=3)

def writecsv(path,rows):
    if not rows:return
    with path.open('w') as f:
        w=csv.DictWriter(f,sorted({k for r in rows for k in r})); w.writeheader(); w.writerows(rows)

def run(arm,out,port):
    amp,kind=ARMS[arm]; pol=Learned()
    label=f'cf-handover-pilot-{os.getuid()}-{os.getpid()}-{port}'
    for p in [port,port-100]:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s: s.bind(('127.0.0.1',p))
    rows=[]; raw=[]; status='not_started'; errors=[]
    with (out/'physics.log').open('w') as pl,(out/'firmware.log').open('w') as fl:
        sim=subprocess.Popen([sys.executable,'-u',str(SIM),'--host','127.0.0.1','--port',str(port),'--model-type','cf2x_L250','--','0,0'],stdout=pl,stderr=subprocess.STDOUT)
        fw=None
        try:
            time.sleep(.8)
            if sim.poll() is not None: raise RuntimeError('physics process exited')
            fw=subprocess.Popen(['docker','run','--rm','--name',label,'--platform','linux/arm64','--network','host','--user',f'{os.getuid()}:{os.getgid()}','--cap-drop=ALL','--security-opt=no-new-privileges','--read-only','--tmpfs','/tmp','--workdir','/tmp','--mount',f'type=bind,src={ROOT}/jammy,dst=/firmware,readonly','ubuntu:22.04','timeout','45','stdbuf','-oL','-eL','/firmware/cf2',str(port),'127.0.0.1'],stdout=fl,stderr=subprocess.STDOUT)
            time.sleep(4)
            if fw.poll() is not None: raise RuntimeError('firmware container exited')
            def startup_timeout(*_): raise TimeoutError('CFLib startup timed out')
            signal.signal(signal.SIGALRM,startup_timeout); signal.alarm(12)
            with SyncCrazyflie(f'udp://127.0.0.1:{port-100}') as scf:
                signal.alarm(0)
                cf=scf.cf; telemetry=Telemetry(cf); raw=telemetry.raw
                try:
                    limit=time.monotonic()+2
                    while 'position_wall' not in telemetry.state():
                        if time.monotonic()>limit: raise RuntimeError('no telemetry')
                        time.sleep(.04)
                    cf.platform.send_arming_request(True); last_u=0.; held=None; had_switch=False
                    start=time.monotonic()
                    # Preflight 4 s: takeoff and settle; manoeuvre ~4 s; controlled descent.
                    for i in range(322):
                        scheduled=start+i*DT
                        time.sleep(max(0,scheduled-time.monotonic()))
                        now=time.monotonic(); t=now-start-4.; st=telemetry.state()
                        x=st['stateEstimate.x']; y=st['stateEstimate.y']; z=st['stateEstimate.z']; vx=st['stateEstimate.vx']
                        roll=st.get('stabilizer.roll',0.); pitch=st.get('stabilizer.pitch',0.)
                        tilt=math.degrees(math.acos(np.clip(math.cos(math.radians(roll))*math.cos(math.radians(pitch)),-1,1)))
                        if now-st['position_wall']>.35 or tilt>28 or z>.85 or abs(x)>1.7 or abs(y)>.70 or (0<t<4.55 and z<.18):
                            status='bounded_abort'
                            raise RuntimeError(f'flight bound t={t:.3f} z={z:.3f} x={x:.3f} y={y:.3f} tilt={tilt:.2f}')
                        zref=clamp((t+4)*.27,.025,.43) if t<4.55 else clamp(.43-(t-4.55)*.20,.018,.43)
                        vcmdz=clamp(1.9*(zref-z),-.21,.29)
                        ref=target(t,amp)
                        classic=clamp(ref+.28*(ref-vx),-.53,.53)
                        after=t>=SW
                        h_before=pol.h
                        if after and not had_switch:
                            held=last_u; had_switch=True
                            if kind=='clear': pol.h=0.
                        nref=amp if after and kind=='stale' and t<SW+.30 else ref
                        neural=pol.step(nref,vx)
                        source='C'; sent=classic
                        if after and kind!='classic':
                            source='N'; sent=neural
                            if kind=='hold' and t<SW+.30: source='C_buffer'; sent=held
                        if t>=4.55: source='land'; sent=0.
                        cf.commander.send_velocity_world_setpoint(sent,clamp(-1.4*y,-.20,.20),vcmdz,0)
                        last_u=sent
                        rows.append(dict(t=t,wall=now,ref=ref,nref=nref,classic=classic,neural=neural,sent_vx=sent,
                                         source=source,h_before=h_before,h_after=pol.h,zref=zref,tilt=tilt,**st))
                        if t>7.3 and z<.075: status='landed'; break
                    else: status='landing_window_expired'
                finally:
                    for _ in range(4):
                        cf.commander.send_stop_setpoint(); time.sleep(.04)
                    cf.platform.send_arming_request(False)
                    time.sleep(.18)
                    telemetry.close()
        except Exception as e:
            errors.append(repr(e)); print(f'{arm}: {errors[-1]}',flush=True)
        finally:
            signal.alarm(0)
            clean_processes(sim,fw,label)
    writecsv(out/'host.csv',rows); writecsv(out/'native.csv',raw)
    post=[x for x in rows if SW<=x['t']<=SW+1]
    pre=[x for x in rows if SW-.08<=x['t']<SW]
    z0=pre[-1]['stateEstimate.z'] if pre else None
    def extract(x):
        return {k:x.get(k) for k in ('t','stateEstimate.x','stateEstimate.z','stateEstimate.vx','tilt','ref','nref','classic','neural','sent_vx','source','h_before','h_after','ctrltarget.vx')}
    res=dict(arm=arm,kind=kind,seed=SEED,fit_rmse=pol.fit_rmse,rows=len(rows),native_rows=len(raw),status=status,errors=errors,entry=extract(pre[-1]) if pre else None,
             first=extract(post[0]) if post else None,last=extract(rows[-1]) if rows else None)
    if post:
        res.update(peak_tilt=max(x['tilt'] for x in post),min_vx=min(x['stateEstimate.vx'] for x in post),
                   drift_x=post[-1]['stateEstimate.x']-pre[-1]['stateEstimate.x'] if pre else None,
                   loss_z=max(0,z0-min(x['stateEstimate.z'] for x in post)) if z0 is not None else None,
                   mean_v_error=sum(abs(x['stateEstimate.vx']-x['ref']) for x in post)/len(post))
    (out/'summary.json').write_text(json.dumps(res,indent=2)+'\n')
    print(json.dumps(res),flush=True)
    return status

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('out',type=pathlib.Path); p.add_argument('arms',nargs='+',choices=ARMS); p.add_argument('--port',type=int,default=29963)
    a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=False)
    cflib.crtp.init_drivers()
    for j,arm in enumerate(a.arms):
        sub=a.out/arm; sub.mkdir()
        status=run(arm,sub,a.port+j)
        if status not in ('landed','bounded_abort'): break
