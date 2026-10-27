"""Recheck archived raw clocks and exact A4 arithmetic without rerunning old source."""
import json,sys,gzip,itertools,math
from pathlib import Path
from fractions import Fraction as F
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p14.common import write,sha

def inverse(a):
 n=len(a);m=[r[:]+[F(i==j) for j in range(n)] for i,r in enumerate(a)]
 for i in range(n):
  z=m[i][i];m[i]=[x/z for x in m[i]]
  for j in range(n):
   if j!=i:
    z=m[j][i];m[j]=[x-z*y for x,y in zip(m[j],m[i])]
 return [r[n:] for r in m]

def exact_A4():
 base=ROOT/'data/p10-20261025-a3/source-08';manifest=json.load(open(base/'manifest.json'))
 artifacts={p:sha(base/p)==v for p,v in manifest['files'].items()};assert all(artifacts.values())
 raw=json.load(open(ROOT/'data/p10-20261024-a2/construction-reviewed/certificate.json'))['P_integer'];P=[[F(raw[i][j],10**10) for j in range(3)] for i in range(3)];inv=inverse(P);w=[F(119,10)*inv[i][2] for i in range(3)];n2=sum(w[i]*P[i][j]*w[j] for i in range(3) for j in range(3));assert n2<9
 startup=json.load(open(base/'startup-observation.json'));rows=list(itertools.islice((json.loads(l) for l in gzip.open(base/'trace.jsonl.gz','rt')),22));assert all(not r['oracle'][1] for r in rows)
 yaw=startup['origin_event']['yaw_rad'];origin=np.array(startup['origin_event']['origin_ned_m'][:2]);f=rows[0]['input'];p=np.array([f[10],f[12]])-origin;v=np.array([f[11],f[13]])
 rot=lambda x:np.array([np.cos(yaw)*x[0]+np.sin(yaw)*x[1],np.sin(yaw)*x[0]-np.cos(yaw)*x[1]])
 rr=rot(p);vv=rot(v);p0=startup['relative_position_flu'][0];v0=startup['velocity_flu'][0];q0=F.from_float(startup['q_flu'][0]);u0=-F.from_float(8.790378768672879)*F.from_float(p0-rr[0])-F.from_float(5.453065498984149)*F.from_float(v0-vv[0]);assert u0>=0
 lo=sum((-F(1,20))**j/math.factorial(j) for j in range(20));hi=sum((-F(1,20))**j/math.factorial(j) for j in range(21));q=q0*lo**22+u0*(1-hi**22)+w[2]*sum(lo**j for j in range(22));original=json.load(open(ROOT/'data/p10-20261025-a4/contract-counterexample-final/counterexample.json'))
 assert str(q)==original['q_forward_lower'] and [str(t) for t in w]==original['per_step_w_p_v_q']
 return {'source_artifacts_all_bound':artifacts,'exact_norm2':str(n2),'exact_q22':str(q),'q22_display':float(q),'exact_equal_original':True,'interpretation':'independent archived-mathematics reconstruction; does not regenerate native source from changed current dependencies. Old CLI source guard failure retained, not disabled.'}

def main():
 out=Path(sys.argv[1]);out.mkdir(exist_ok=False)
 p=ROOT/'data/p11-20261025-formal/F5-r2-NORMAL/run/flight.ulg';u=ULog(str(p),['research_p11']);d=next(x.data for x in u.data_list if x.name=='research_p11');a=d['active'].astype(bool);ts=d['timestamp_sample'][a].astype(np.int64);nt=d['timestamp'][a].astype(np.int64);wall=d['run_wall_ns'][a].astype(np.int64);j=np.flatnonzero(np.diff(nt)==0)
 write(out/'P11-run70.json',{'raw_sha256':sha(p),'active_rows':len(ts),'native_plateaus':len(j),'sample_non4ms':int(np.sum(np.diff(ts)!=4000)),'examples':[{'sample_us':ts[max(0,i-1):i+3].tolist(),'native_us':nt[max(0,i-1):i+3].tolist(),'host_ns':wall[max(0,i-1):i+3].tolist()} for i in j[:5]],'guard_difference_claim':'old actual guard flip count0 retained; constructing other guard word is separate','old_validity':'INVALID_UNCHANGED'})
 p=ROOT/'data/p12-cont-20261026-formal/b3-ph2-NORMAL1/run/flight.ulg';u=ULog(str(p),['research_p11','research_p12']);d=next(x.data for x in u.data_list if x.name=='research_p11');i=int(np.flatnonzero(d['active'])[0]);p12=next(x.data for x in u.data_list if x.name=='research_p12')
 write(out/'P12-formal27.json',{'raw_sha256':sha(p),'first_active_sample_us':int(d['timestamp_sample'][i]),'first_active_read_valid':bool(d['external_valid'][i]),'p12_fields':list(p12),'pre_read_initialized_recorded':False,'inference_limit':'cannot distinguish initialized=false vs force-sync-not-ready bypass from missing pre-read fields; lastGRU and actualcommit are not substitutes','old_validity':'AUDIT_REJECTED_UNCHANGED'})
 write(out/'A4-exact-archived.json',exact_A4())
if __name__=='__main__':main()
