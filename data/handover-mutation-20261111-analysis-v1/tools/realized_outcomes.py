"""Add scenario realization and observed physical outcomes without replacing primary records."""
import hashlib
from pathlib import Path
import metrics_base as m
def decorate(results):
 for r in results:
  run=Path(r['source_run']).parent;cp=run/'candidate-before.json';r['candidate_record_sha256']=hashlib.sha256(cp.read_bytes()).hexdigest() if cp.exists() else None;r['candidate_record_path']=str(cp)
  spec=r.get('explore',{});requires_timeout=spec.get('active_timeout_after_s') is not None or spec.get('reference_kind')=='fresh_at_request_then_natural_timeout';r['scenario_realization']='NO_SUBJECT_HANDOVER';physical=[];tasks=[]
  for b in r.get('boundaries',[]):
   if 'owner_boundary' not in b:continue
   start=b['owner_boundary']['timestamp_us'];end=b['subject_end_us'];phys=m.frozen(b['windows']['subject'],b['frozen_joint_recovery'],r.get('completion',{}).get('safety_protection_triggered',False) and b['subject_end_reason']=='failure');task=(b['windows']['subject'] or {}).get('local_task_envelope','UNKNOWN');b['observed_physical_frozen']=phys;b['observed_physical_task']=task;physical.append(phys['status']);tasks.append(task)
   scenario='OBSERVED_REQUESTED_HANDOVER'
   if requires_timeout:
    captures=[c for c in r.get('target_capture_events',[]) if start<=c['timestamp']<=end and c.get('activation')==0];ref=b.get('reference_evidence',{});read=(ref.get('sender_match') or {}).get('read_native_us');fresh=ref.get('first_any_source_valid') or {};verified=[c for c in captures if read is not None and start<=read<c['timestamp'] and fresh and start<=fresh['timestamp']<c['timestamp'] and not fresh.get('stale',1)]
    scenario='VERIFIED_ACTIVE_TIMEOUT' if verified else ('UNVERIFIED_TIMEOUT_SEQUENCE' if captures else 'NOT_REALIZED_ACTIVE_TIMEOUT')
    b['scenario_sequence_evidence']={'post_owner_nonactivation_captures':captures,'first_sender_matched_active_read_us':read,'first_fresh_active_row_us':fresh.get('timestamp'),'verified_capture_timestamps_us':[c['timestamp'] for c in verified]}
   b['scenario_realization']=scenario;r['scenario_realization']=scenario
  def combine(xs):return 'FAILURE' if 'FAILURE' in xs else ('SUCCESS' if xs and all(x=='SUCCESS' for x in xs) else 'UNKNOWN')
  r['observed_physical_frozen_status']=combine(physical);r['observed_physical_task_status']=combine(tasks)
 return results
