#!/usr/bin/env python3
"""Past-only direct-history/filter initial information for M3, in a NEW directory."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from pyulog import ULog
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p11.pack import pack
from p12.execution import DTYPE
from p9_model import write,sha


def create(run,sync,out):
    manifest=pack(run,sync,out)
    doc=json.loads((out/'prediction-input.json').read_text());i=manifest['initial_index'];initial=doc['initial']
    cfg=json.loads((run/'config.json').read_text());cutoff=manifest['initial_cutoff_host_ns']
    d=next(x.data for x in ULog(str(run/'flight.ulg'),['research_p12']).data_list if x.name=='research_p12')
    hit=np.flatnonzero(d['timestamp_sample']==initial['sample_us'])
    if len(hit)!=1:raise RuntimeError('direct history initialization row not unique')
    j=int(hit[0]);initial.update(history=[float(d[f'history_after[{k}]'][j]) for k in range(4)],
        history_count=int(d['history_count_after'][j]),call_index=int(d['call_index_after'][j]),force_sync=2,
        external_seen=bool(d['external_seen'][j]))
    filters=[];commands=[];ages=[];sources=[]
    for k in range(4):
        path=run/f'gz-motor/execution-p12-{k}.bin';r=np.fromfile(path,dtype=DTYPE)
        eligible=np.flatnonzero(r['end_ns']<min(cutoff,manifest['initial_max_host_ns']))
        if not len(eligible):raise RuntimeError('no past-only execution state')
        b=int(eligible[-1]);filters.append(float(r['filter_after'][b]));commands.append(float(r['command'][b]))
        ages.append((manifest['initial_max_host_ns']-int(r['end_ns'][b]))/1000)
        sources.append({'path':str(path),'sha256':sha(path),'row':b,'end_ns':int(r['end_ns'][b]),'cutoff_ns':cutoff})
    initial.update(rotor_filter=filters,pending_command=commands)
    doc['schema']='p12-causal-input-1';doc['plan'].update(p12_repair=cfg['p12']['repair'],p12_phase=cfg['p12']['phase'],
        declared_schedule={'name':'nominal-independent-clock','native_offsets_us':{},'meaning':'declared scenario only, not measured future scheduler'})
    write(out/'prediction-input.json',doc)
    # Bind the final P12 input, retaining the base packer's intermediate receipt.
    (out/'manifest.json').rename(out/'p11-packing-base.json')
    write(out/'manifest.json',{**manifest,'schema':'p12-packing-1',
        'base_input_sha256':manifest['input_sha256'],'input_sha256':sha(out/'prediction-input.json'),
        'base_manifest_sha256':sha(out/'p11-packing-base.json')})
    write(out/'p12-initial-manifest.json',{'schema':'p12-past-only-1','sources':sources,'execution_age_us':ages,
        'state_alignment':'last completed execution state before controller initial host bound; async age retained, not exact plant snapshot',
        'input_sha256':sha(out/'prediction-input.json'),'formal_or_heldout':False,
        'initialization_not_steady_command':True})
    return doc


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--sync',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();create(a.run,a.sync,a.output)
