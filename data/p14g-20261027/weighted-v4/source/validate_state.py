"""Necessary restoration regression for the new conditional observer state."""
import sys,json,time,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from p14g.common import *
from p14g.model import forecast

def main():
 out=Path(sys.argv[1]);register(out,'new fading observer checkpoint retainsqueues/history/D andabsoluteinnovationreference; notnewvariantsearch');limit(10);d=json.load(open(B/'inputs-v1/d02/input.json'));a,b=d['plan']['full_source_windows_profile_s'][:2];d['plan']['windows_profile_s']=[a,b];end=b[1]+.15;cut=a[1]+.1;P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));lib=OLD/'offline-build-v2/libop.bin';whole=forecast(d,{},P,observer_library=lib,limit=end,checkpoint_times=[cut]);cp=whole['checkpoints'][0];continued=forecast(dict(d,initial=cp['initial']),{},P,observer_library=lib,limit=end);j=np.flatnonzero(whole['trace'][:,0]>=cp['actual_time']-1e-9)[0];N=min(len(continued['trace']),len(whole['trace'])-j);err={k:float(np.nanmax(abs(continued[k][:N]-whole[k][j:j+N]))) for k in ['states','trace','cache_samples']};assert max(err.values())<1e-9
 write(out/'result.json',{'max_difference':err,'matched_rows':N,'preserved_D':cp['initial']['physical_D0_m'],'preserved_LP_D':cp['initial']['LP_D0_m'],'preserved_count':cp['initial']['history_count'],'original_innovation_reference_retained':cp['initial']['p14g_innovation']==d['initial']['p14g_innovation'],'scope':'conditional point-state serialization throughplannedsecond event, notcontinuoussetcontainment oractualfuturecoverage'})
if __name__=='__main__':main()
