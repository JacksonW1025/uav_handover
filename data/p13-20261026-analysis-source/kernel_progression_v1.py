"""Existing source-kernel diagnostic progression; identical45deg witness scale.
Earlier50deg and later80deg stop domains remain unchanged and are not compared
as if identical. M4 forced physical initial is a diagnostic outside its LP fit.
"""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));from p9_model import write,sha
files=[('M4_with_direct_physical_initial_and_actual_future_rotor','data/p13-20261026-diagnostics/dev01-open-plant/arrays.npz','M4_physical_initial_known_rotor','COM_position','body_q'),('source_average_rotor_inertia_actual_future_rotor','data/p13-20261026-diagnostics/dev01-open-plant/arrays.npz','source_physics_candidate_known_rotor','COM_position','body_q'),('source_anisotropic_inertia_actual_future_rotor','data/p13-20261026-diagnostics/dev01-anisotropic-open-plant/arrays.npz','source_physics_candidate_known_rotor','COM_position','body_q'),('source_discrete_FreeJoint_actual_future_command_only','data/p13-20261026-theory/source-discrete-audit-v1/dev01-F2-NORMAL/arrays.npz','known_command_open','COM_p_post','body_q_post')];loaded=[]
for label,f,key,p,q in files:
 x=np.load(R/f);loaded.append((label,f,x['profile_s'],x[key],x[p],x[q]))
common=min(len(x[3]) for x in loaded);t=loaded[0][2];rows=[]
for label,f,tt,a,p,q in loaded:
 assert np.array_equal(tt,t);assert np.max(abs(p-loaded[0][4]))<1e-12;w=np.flatnonzero(a[:,-1]>45);rows.append({'variant':label,'source_file':f,'sha256':sha(R/f),'first_predicted45deg_witness_s':None if not len(w) else float(tt[w[0]]),'stored_rows':len(a),'common_early_rows':common,'common_early_position_max_error_m':float(np.max(np.linalg.norm(a[:common,:3]-p[:common],axis=1))),'future_inputs':'actual selected command only, own filter/phase/body' if 'command_only' in label else 'actual future force-phase rotor and next filter','M4_scope_warning':'empirical controller/LP plant forced physical q/omega initial is diagnostic, not frozen autonomous M4 score' if label.startswith('M4') else None})
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);write(out/'progression.json',{'schema':'p13-source-kernel-progression-1','case':'dev01-F2-NORMAL','rows':rows,'scale':'same45deg witness, old50/new80 stop rules retained separately; not a comparison of domain-exit times','source_relations_changed':'source thrust/drag and anisotropic rotor inertia, then FreeJoint coordinate update','not_new_frozen_model':True,'not_heldout_prediction_grade':True,'true_physical_normal_never45deg':'see actualrecord','new_SITL':0});print(rows)
