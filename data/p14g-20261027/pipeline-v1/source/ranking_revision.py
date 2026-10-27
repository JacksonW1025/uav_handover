"""Independent retrospective baseline corrections, old ranking immutable.
Uniform means a seeded permutation of distinct physical candidate inputs;
old lexical ordering is kept as a nonuniform control. Nominal danger uses LP
height relative to model-predicted commonfirstgap, not the COM diagnostic.
"""
import sys,json,copy,hashlib,time,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import write,limit
from p14g.model import forecast
from p14g.delivery import Word

def main():
 inp,out=map(Path,sys.argv[1:3]);out.mkdir();limit(30);assert not any((Path('/home/car/uav_handover')/'data').iterdir());ranking=json.load(open(inp/'ranking.json'));P=dict(np.load(inp/'policy.npz'));lib=inp/'libop.bin';unique={r['physical_configuration_key']:r for r in ranking['rows']};unique=list(unique.values());newrows=[];start=time.perf_counter()
 for row in unique:
  d=json.load(open(inp/(row['case']+'.json')))
  if not row['no_event_control']:
   d['plan']['windows_profile_s'][0][1]+=row['offset_ms']/1000;d['plan']['full_source_windows_profile_s'][0][1]+=row['offset_ms']/1000
  a=d['plan']['common_first_gap_profile_s'];end=d['plan']['full_source_windows_profile_s'][0][1]+.5;r=forecast(d,{},P,word=Word(),observer_library=lib,limit=end);tr=r['trace'];z0=float(np.interp(a,tr[:,0],tr[:,44]));scope=tr[:,0]>=a;lpD=float(max(0,np.max(tr[scope,44])-z0));tilt=float(max(tr[scope,7]));margin=min((45-tilt)/45,1-lpD);row=dict(row,corrected_nominal_LP_D=lpD,corrected_nominal_tilt=tilt,corrected_nominal_task_margin=margin);newrows.append(row)
 ids=sorted(r['id'] for r in newrows);seal=json.load(open(inp/'protocol-seal.json'))['sha256'];seed=int(hashlib.sha256(('P14G-uniform:'+seal).encode()).hexdigest()[:16],16);random.Random(seed).shuffle(ids);newranks={'uniform':ids,'nominal_danger':[r['id'] for r in sorted(newrows,key=lambda x:(round(x['corrected_nominal_task_margin'],12),x['case'],x['offset_ms']))],'set_separation':ranking['rankings']['set_separation']};write(out/'ranking.json',{'rankings':newranks,'rows':newrows,'old_rankings_preserved':ranking['rankings'],'uniform_seed_from_precomputed_protocol_seal':seed,'selection_future_visible':False,'exposure':'post-exposure deterministic design/metric correction, retrospective only. No claim originalpredeclareduniformwasvalid ornewindependentforwardevidence.','reason':'lexical is notuniform; COMdiagnosticheight is notLPtaskheight. Bothoriginalbaselines retained, correctedseparately. Sourcehypothesisfeatures, separationcriterion andallcandidateinputsunchanged.','elapsed_s':time.perf_counter()-start})
if __name__=='__main__':main()
