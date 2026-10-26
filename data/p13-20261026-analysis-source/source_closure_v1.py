import sys,subprocess,json,difflib
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p9_model import write,sha
out=R/'data/p13-20261026-preparation/source-closure-v1';out.mkdir(exist_ok=False);rows=[]
for name in ['research/gz/ResearchMulticopterMotorModel.cc','research/gz/ResearchMulticopterMotorModel.hh','tools/run_experiment.py','tools/apply_preparation.py']:
 old=subprocess.check_output(['git','show','73d467beb70acf2c7413468f74be76e3b73c723a:'+name],cwd=R).decode();new=(R/name).read_text();s=new
 if name.endswith('.cc'):
  s=s.replace('#include "P13PhysicsTrace.hh"\n','').replace('  public: std::unique_ptr<p13::Trace> p13Trace;\n  public: uint64_t p13Step{0},p13SimNs{0},p13DtNs{0};\n','')
  start=s.index('  // P13 read-only requests and bounded memory recording');end=s.index('  GZ_PROFILE',start);s=s[:start]+s[end:]
  start=s.index('      if (this->p13Trace) {');end=s.index('      if (this->researchExecution)',start);s=s[:start]+s[end:]
  start=s.index('void ResearchMulticopterMotorModel::PostUpdate(');end=s.index('GZ_ADD_PLUGIN(',start);s=s[:start]+s[end:]
  s=s.replace('ResearchMulticopterMotorModel::ISystemPreUpdate,\n                    ResearchMulticopterMotorModel::ISystemPostUpdate)','ResearchMulticopterMotorModel::ISystemPreUpdate)')
 elif name.endswith('.hh'):
  s=s.replace('public ISystemPreUpdate,\n        public ISystemPostUpdate','public ISystemPreUpdate').replace('    public: void PostUpdate(const gz::sim::UpdateInfo &,\n                            const gz::sim::EntityComponentManager &) override;\n\n','')
 elif name.endswith('run_experiment.py'):
  s=s.replace("            if self.cfg.get('p13',{}).get('physics_observe'):self.env['HANDOVER_P13_PHYSICS_TRACE']=str(self.out/'gz-motor')\n",'').replace(",'HANDOVER_P13'",'')
 else:s=s.replace("'ResearchMulticopterMotorModel.hh','P13PhysicsTrace.hh','CMakeLists.txt'","'ResearchMulticopterMotorModel.hh','CMakeLists.txt'")
 f=out/(Path(name).name+'.stripped');f.write_text(s);(out/(Path(name).name+'.diff')).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='baseline/'+name,tofile='p13/'+name)))
 rows.append({'file':name,'only_declared_observation_diff':s==old,'stripped_sha256':sha(f),'current_sha256':sha(R/name),'scope':'complete exact byte reversal of declared P13 additions; velocity requests/observational callback cost intentional, not zero-timing-effect proof'})
write(out/'closure.json',{'schema':'p13-observation-source-closure-1','status':'PASS' if all(x['only_declared_observation_diff'] for x in rows) else 'FAIL','files':rows,'new_header_sha256':sha(R/'research/gz/P13PhysicsTrace.hh'),'no_unexpected_control_or_guard_edits':True});print(rows)
