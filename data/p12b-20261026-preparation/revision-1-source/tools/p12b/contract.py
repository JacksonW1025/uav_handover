"""P12b contract shares the unchanged delivery decision; no inferred readiness."""
def decision(phase,active,initialized,force_sync_initialized,index,force_sync):
 applies=bool(active and phase!=0 and initialized and force_sync!=0)
 permit=True if not applies else (index%force_sync==0 if phase==1 else index%force_sync!=0 if phase==2 else False)
 return {'gate_applicable':applies,'gate_permit':permit,'force_sync_flag':bool(force_sync_initialized),'readiness_source':'same-call pre-read fields; flag recorded separately from source gate predicate'}
