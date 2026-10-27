import sys,json,numpy as np
from pathlib import Path
R=Path('/home/car/uav_handover');sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(Path(__file__).resolve().parent))
from p15.common import B,write,sha
from p15.model import rollout as original
from model_taps import rollout
x=json.load(open(sys.argv[1]));c=json.load(open(sys.argv[2]))['executed_candidate'];context=dict(x['context'],full_task_forecast=True);P=dict(np.load(R/'data/p13-20261026-freeze/models/policy.npz'));a=original(x['snapshot'],c,context,x['parameters'],P,x.get('update'));b=rollout(x['snapshot'],c,context,x['parameters'],P,x.get('update'));assert np.array_equal(a['full_prefix'],b['full_prefix']);assert a['successor']==b['successor'];out=Path(sys.argv[3]);out.mkdir();np.savez_compressed(out/'taps.npz',trace=np.asarray(b['full_prefix']),taps=np.asarray(b.pop('analysis_taps')));write(out/'result.json',dict(core_bit_identical=True,input_sha256=sha(Path(sys.argv[1])),core_source_sha256=sha(R/'tools/p15/model.py'),tap_source_sha256=sha(Path(__file__).parent/'model_taps.py'),future_inputs=False,CPU_original=a['model_CPU_s'],CPU_tapped=b['model_CPU_s'],scope='instrumentation only, allfrozen scores retained',successor=a['successor'],branches=a['branches']));print('TAPS_BIT_IDENTICAL',len(a['full_prefix']))
