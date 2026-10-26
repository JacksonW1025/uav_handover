"""P13 prospective development identities; formal parameters selected only before freeze."""
import json,sys,copy
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p9_model import write,sha
P=R/'data/p13-20261026-preparation';C=R/'config/p13-cases'
def config(family,branch,split='development',gap=None):
 src=next(x for x in json.load(open(R/'config/p12-cont.json'))['rows'] if x['family']==family and x['phase']==1 and x['branch']==('NORMAL0' if branch=='NORMAL' else branch))
 c=json.load(open(R/src['config']));c['p11']['schema']='p13-fixed-physical-platform-1';c['p11']['model_split']=split;c['p11']['budget']={'development':12,'formal':72,'total':84,'old_P12_series_starts':66}
 c['p12b']={'schema':'p13-fixed-native-read-1','observe':True,'read_trace_schema':'direct-v2','solver_observe':False}
 c['p12c_platform']={'version':'p13-physical-buffered-1','canonical':'direct pre-read + P11/P12 ULog + per-step motor + buffered P13 direct physical state','heavy_solver':False}
 c['p13']={'version':'physical-buffered-1','physics_observe':True,'phase_contract':'PreUpdate physical input and PostUpdate integrated state share iterations/simTime; physical state never from callback difference','buffer_rows':{'body':131072,'per_rotor':65536},'source_id':src['id'],'source_config_sha256':src['config_sha256'],'new_task':gap is not None}
 if gap is not None:
  s=c['p5']['conditions']['p11-case'];s['gaps']['windows_s']=[[0.,.36],[.36+gap,.72+gap]];s['post_gap_s']=5.0-(.72+gap);s['description']='P13 fixed cruise6s, A[0,.36], B shifted only; post_gap compensates B endpoint without changing reference trajectory; new task, historical source retained';s.pop('safety_budget_m',None)
 c['p11']['event_mask']={'NORMAL':[],'A':[0],'B':[1],'AB':[0,1],'REPAIR':[0,1]}[branch]
 return c,src

def main():
 if (P/'development-v1.json').exists():raise FileExistsError('never overwrite design')
 C.mkdir(exist_ok=False)
 spec={'schema':'p13-engineering-prespec-1','declared_before_starts':0,'scope':'fixed light-on and physical-buffered platform; old off/on FAIL retained, not new global gate','hard':{'source':'observational-only diff; no changes to control/read/capture/history/filter/guards/weights','native':'same-call pre-read contract, input/history/continuous replay existing1e-4 and1e-5 single; no unexplained reset/loss','motor':'original filter replay1e-9; consumer age<=8ms, cycle p99<=2500us','physics':'body and4rotors complete1/dropped0/errors0; full task valid; unique physical step/phase; original motor same step exact<=1e-12','geometry_position_m':1e-8,'geometry_velocity_m_s':1e-7,'post_next_pre_position_m':1e-10,'COM_position_semiimplicit_step_m':.001,'source_drag_N':1e-12,'numeric_scale_basis':'geometry floating point checks; integral1mm step engineering tolerance accommodates finite rotation term, not dynamics error certificate','cache':'retain true physical sample to callback/native read intervals, no callback-difference velocity admitted as direct','coverage':'invalid initialization explicitly marked; no missing valid task rows; interrupted buffer never accepted'},'decisions':{'hard_error':'pause affected queue, no replacement; independent version and diagnosis; develop may continue only distinct preregistered identity after cause fixed','analysis':'pure deterministic report/path/serialization fixes isolated analysis versions, recheck affected records; no treatment/threshold/parameter changes','scientific':'count and retain failure/NOT_REACHED, does not stop reliable platform','offon':'optional diagnostics only, no nonsignificance equivalence claim'},'theory_gate':'independent, full proof not prerequisite to mechanism experiment','development_selection':'first4 specific interface cases, remaining<=8 only questions identified from actual evidence; each before corresponding start','storage':'remaining84 worst .6GB/start +20GB analysis/build+10GB reserve, verify before each start; all raw retained'}
 write(P/'engineering-spec.json',spec)
 rows=[]
 for i,(fam,branch,purpose) in enumerate([('F2','NORMAL','COM/time initialization, step/geometry/integration/force/cache interface'),('F2','A','full capture/hold/resume/tail with direct physical state'),('F4','AB','historical boundary physical/LP/COM and time-process diagnosis'),('F4','REPAIR','capture-only repair, full residual descent and costs')],1):
  ident=f'dev{i:02d}-{fam}-{branch}';c,src=config(fam,branch);path=C/(ident+'.json');write(path,c);rows.append({'id':ident,'family':fam,'phase':1,'branch':branch,'sim_seed':1335130000+i,'kind':'p5_gap','condition':'p11-case','treatment':'P11-Z','config':str(path.relative_to(R)),'config_sha256':sha(path),'source_id':src['id'],'question':purpose})
 write(P/'development-v1.json',{'schema':'p13-development-design-1','rows':rows,'starts_before':0,'spec_sha256':sha(P/'engineering-spec.json'),'budgets':{'development':12,'formal':72,'total':84},'old_count':66})
 print('P13 DEV DESIGN4;0 starts')
if __name__=='__main__':main()
