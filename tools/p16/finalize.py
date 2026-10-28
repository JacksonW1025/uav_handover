"""Prepare fixed pool, past-only common initial templates, policy inputs."""
import json,copy,numpy as np
from pathlib import Path
from p16.common import *
from p16.prepare import GS,MAIN_SEED,REPL_SEED,configuration,scenario
from p16.greybox import forecast,parameters,core
from p16.workflow import digest
from p12b.read_trace import load
from p12.execution import DTYPE

def initial_from_dev(rid,out):
 t=B/'runs'/rid;run=t/'run';analysis=next(a for a in [t/'analysis-v2',t/'analysis-v1'] if (a/'result.json').exists() and json.load(open(a/'result.json'))['valid']);d=np.load(analysis/'observation/synchronized.npz');ev=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()];epoch=next(e['run_wall_ns'] for e in ev if e['event']=='p12_confirmed_native_stream_anchor');dr=load(run/'gz-motor/read-p12b.bin');i=int(np.flatnonzero(d['read_wall_ns']<epoch)[-1]);sample=int(d['sample_us'][i]);native=int(d['native_us'][i]);ii=np.flatnonzero((dr['timestamp_sample']==sample)&(dr['timestamp']==native));assert len(ii)==1;j=int(ii[0]);assert not dr['gate_pending'][j] and dr['force_sync_pre'][j]==2
 filters=[];commands=[];ages=[]
 for rotor in range(4):
  x=np.fromfile(run/f'gz-motor/execution-p12-{rotor}.bin',DTYPE);idx=np.flatnonzero(x['end_ns']<d['read_wall_ns'][i]);assert len(idx);z=x[int(idx[-1])];filters.append(float(z['filter_after']));commands.append(float(z['command']));ages.append((int(d['read_wall_ns'][i])-int(z['end_ns']))/1000)
 init=dict(position=d['position'][i].tolist(),velocity=d['velocity'][i].tolist(),attitude=d['attitude'][i].tolist(),omega=d['omega'][i].tolist(),h=d['h_after'][i].tolist(),previous=d['action'][i].tolist(),history=d['input'][i,18:].tolist(),history_count=0 if d['committed'][i] else 1,target_p=d['target_p'][i].tolist(),target_v=d['target_v'][i].tolist(),target_yaw=float(d['target_yaw'][i]),stale=bool(d['stale'][i]),last_read_us=int(dr['last_valid_read_post'][j]),sample_us=sample,native_us=native,lp_phase_us=int(d['lp_sample'][i])%8000,commit_phase_us=sample%8000,profile_s=(int(d['run_wall_ns'][i])-epoch)/1e9,call_index=int(dr['call_index_pre'][j])+1,force_sync=2,external_seen=bool(dr['external_seen_pre'][j] or (dr['read_updated'][j] and dr['read_valid'][j])),rotor_filter=filters,pending_command=commands)
 write(out,dict(initial=init,source=rid,source_index=i,epoch_ns=epoch,completed_ns=int(d['read_wall_ns'][i]),strict_past=True,execution_age_us=ages,pending_interpretation='last consumed command as legacy model initial pending; exact transport slot not claimed',future_record_states_used=False,new_main_realized_state_used=False));return init

def prepare():
 out=B/'freeze-inputs-v4';out.mkdir(exist_ok=False);inits={f:initial_from_dev(r,out/(f+'-initial.json')) for f,r in [('F2','p16-d01-F2-NORMAL'),('F4','p16-d02-F4-AB')]};pool=[];rows={};pred={};traces={};mainplans=[]
 for f in ['F2','F4']:
  for prefix in ['B','AB']:
   for G in GS:
    cell=f'{f}-{prefix}-G{G:.3f}';rid='p16-main-'+cell;c=configuration(f,prefix,G,'main');path=Path('config/p16')/(rid+'.json');write(R/path,c);pl=scenario(c,G);item=dict(id=cell,family=f,prefix=prefix,G=G,curve_id=f'{f}/{prefix}/fixed6s_D.36',suffix_plan='fixed6s_D.36');pool.append(item);row=dict(id=rid,cell_id=cell,stage='main',role='main_cell',family=f,prefix=prefix,G=G,seed=MAIN_SEED,config=str(path),config_sha256=sha(R/path),absolute_A_profile_s=pl['A_start'],absolute_B_profile_s=pl['A_start']+.36+G);rows[cell]=row;mainplans.append(row)
    doc=dict(id=cell,family=f,prefix=prefix,phase=c['p12']['phase'],initial=copy.deepcopy(inits[f]),plan=pl);p,z=forecast(doc,parameters());pred[cell]=p;traces[cell]=z;row['reuse_seam_profile_s']=(p.get('capture_ledger') or {}).get('time');row['reuse_expected_commit_phase']=(p.get('reuse_signature') or {}).get('commit_phase');row['reuse_plan_hash']=pl['suffix_plan_hash'];write(out/'model-inputs'/f'{cell}.json',doc)
 # Fixed before any MAIN label; two cross-history pairs and two old boundary probes.
 specs=[('F2','B',2.,'transfer_donor_safe'),('F2','AB',2.,'transfer_receiver_long'),('F4','B',1.42,'matched_suffix_reference'),('F4','AB',1.42,'inheritance_or_margin_reject'),('F2','AB',.55,'short_tilt_boundary'),('F4','AB',.55,'short_height_boundary')];rep=[]
 for f,prefix,G,role in specs:
  cell=f'{f}-{prefix}-G{G:.3f}';rid='p16-rep-'+cell;c=configuration(f,prefix,G,'replication');path=Path('config/p16')/(rid+'.json');write(R/path,c);pl=scenario(c,G);rep.append(dict(reuse_plan_hash=pl['suffix_plan_hash'],reuse_seam_profile_s=(pred[cell].get('capture_ledger') or {}).get('time'),reuse_expected_commit_phase=(pred[cell].get('reuse_signature') or {}).get('commit_phase'),id=rid,cell_id=cell,stage='replication',role=role,family=f,prefix=prefix,G=G,seed=REPL_SEED,config=str(path),config_sha256=sha(R/path),absolute_A_profile_s=pl['A_start'],absolute_B_profile_s=pl['A_start']+.36+G))
 write(out/'pool.json',pool);write(out/'rows.json',rows);write(out/'initial-predictions.json',pred);np.savez_compressed(out/'initial-traces.npz',**traces);write(out/'main-plan.json',dict(rows=mainplans));write(out/'replication-plan.json',dict(rows=rep,fixed_before_any_main_result=True,model_update_allowed=False,initial_state='same development template; newseed realstate only diagnostic'))
 return out
if __name__=='__main__':print(prepare())
