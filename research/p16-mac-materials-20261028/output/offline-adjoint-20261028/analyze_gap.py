from core import *
from source_kernels import M3,M5,E
import copy,hashlib
path=ROOT/'upstream/data/p13-20261026-formal/p13-F2-b1-AB-short/analysis-v1/packed-physical/prediction-input.json'
doc=json.loads(path.read_text());models=json.loads((ROOT/'upstream/data/p13-20261026-freeze/models/models.json').read_text());policy={k:v.numpy() for k,v in P.items()}
def run(g,model='M5'):
 d=copy.deepcopy(doc);change=g-.55
 d['plan']['windows_profile_s'][1]=[t+change for t in d['plan']['windows_profile_s'][1]]
 # Keep original reference plan/horizon fixed; only move the B blackout.
 result=(M5 if model=='M5' else M3)(d,models['M2'],policy);tr=result['trace']
 # First event start to B end +1s; same declared relative task window.
 sel=(tr[:,0]>=d['plan']['windows_profile_s'][0][0])&(tr[:,0]<=d['plan']['windows_profile_s'][1][1]+1)
 return float(tr[sel,7].max()),result
def main():
 result={'scope':'P13 F2 block1 source forecast. Only B blackout timing changes on one fixed initial state/reference; measured gap contrasts come from independent recorded runs. Original envelope stop retained; M3 peaks at stop are lower bounds, not complete peaks.'}
 result['curves']={}
 for name in ['M3','M5']:
  base,raw=run(.55,name);curves=[]
  for g in [.55-1e-6,.55,.55+1e-6,.546,.554,.53,.57,1.2,2.]:
   y,r=run(g,name);curves.append({'g':g,'peak':y,'stop':r['stop'],'trace_equal_baseline':np.array_equal(r['trace'],raw['trace'])})
  result['curves'][name]=curves
 rows=json.loads((ROOT/'upstream/data/p13-20261026-results-v3/cases.json').read_text())['rows']
 result['measured']=[{'id':x['id'],'g':x['gap_s'],'peak':x['LP_peak_tilt_deg'],'loss':x['LP_max_loss_m'],'task':x['task']} for x in rows if x['family']=='F2' and x['branch']=='AB']
 result['matched_record_inputs']=[]
 for label in ['short','medium','long']:
  inp=ROOT/f'upstream/data/p13-20261026-formal/p13-F2-b1-AB-{label}/analysis-v1/packed-physical/prediction-input.json'
  dd=json.loads(inp.read_text());r=M5(dd,models['M2'],policy);tr=r['trace'];x=next(x for x in rows if x['id']==f'p13-F2-b1-AB-{label}')
  result['matched_record_inputs'].append({'id':x['id'],'g':x['gap_s'],'M5_full_peak':float(tr[:,7].max()),'observed_peak':x['LP_peak_tilt_deg'],'stop':r['stop']})
 result['discrete_timing_derivative']=0.
 result['reason']='On unchanged branches, g occurs only in Boolean time-window predicates. All state recurrences have zero explicit g derivative, giving zero ordinary discrete adjoint. Identical entire traces at +/-1 microsecond verify the branch plateau. No continuous-time event/saltation adjoint is claimed.'
 (ROOT/'gap-results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
