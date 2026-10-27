"""Plugin payload selection has no timestamp-regression check. Do not pretend
an ordered transport condition is a universal source invariant.
"""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *
from output_chain import read_trace

def main():
 out=Path(sys.argv[1]);register(out,'H1 command-consumption conditional monotonic guard and componentoverride audit');rows=[]
 for n,c in cases().items():
  for motor in range(4):
   p=R/c['raw_run']/f'gz-motor/motor-{motor}.bin';_,r,partial=read_trace(p);v=r['applied_sample_us'].astype(np.int64);rows.append({'id':n,'motor':motor,'rows':len(r),'partial_bytes':partial,'payload_sample_regressions':int(np.sum(np.diff(v)<0)),'component_override_rows':int(np.sum((r['flags']&2)!=0)),'source_sha256':sha(p)})
 write(out/'result.json',{'rows':rows,'total_payload_regressions':sum(x['payload_sample_regressions'] for x in rows),'source':'ResearchMulticopterMotorModel.cc:586..625, lastreceived slot under mutex; Actuators component takes precedence; no explicit payload timestamp monotonic check','guard_scope':'synthetic generated-ID consumption monotone ONLY under ordered singleproducer transport/no componentoverride. RepeatedheldIDallowed; reordered/componentmode explicit, notsilently rejectedasuniversallyillegal','same_source_mode_must_be_preserved':True,'all_actual_rows_satisfy_ordered_mode':all(x['payload_sample_regressions']==0 and x['component_override_rows']==0 for x in rows)})
if __name__=='__main__':main()
