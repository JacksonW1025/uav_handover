"""Independent analysis revision for already endedrawrun; never launches SITL."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from p14h.common import *
from p14h.workflow import process
from p14h.scope_audit import audit
from p13.physics import analyze

def main():
 target=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();m=process(target/'run',out,R/'data/p12-cont-20261026-freeze/models',predict=False);s=audit(target/'run',out,out/'neural-scope');p=analyze(target/'run',out/'physics');assert p['status']=='PASS';info={'engineering':'PASS_CRITICAL_NEURAL_STATE_SCOPE','legacy_analysis':'analysis-v1 observationFAIL missingauxiliaryTimingtail retained','task_outcome':m['task_outcome'],'censored':m['censored'],'observer':'PASS (original audit unchanged)','physics':p['status'],'role':'mechanism','source_analysis':str(out.relative_to(R)),'unobserved_auxiliary_tail':json.load(open(out/'observation/observation.json'))['unobserved_auxiliary_timing_tail_sample_us'],'initial_difference_preserved':True};write(target/'information-v2.json',info);append(B/'attempts.jsonl',{'event':'OUTCOME_RESOLVED','id':target.name,'new_scope':'P14H critical P11/direct complete; auxiliaryTimingtailUNKNOWN','legacy_FAIL_retained':True,'new_analysis':str(out.relative_to(R)),'task_outcome':m['task_outcome'],'censored':m['censored'],'no_reflight':True});print('REANALYZED',target.name,m['task_outcome'])
if __name__=='__main__':main()
