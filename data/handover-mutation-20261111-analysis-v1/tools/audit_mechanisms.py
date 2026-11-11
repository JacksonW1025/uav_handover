"""Supplementary causal-limitation/target/memory audit, only immutable finalized analyses."""
from pathlib import Path
import json
import numpy as np
from pyulog import ULog
import metrics_base as m
OUT=Path(__file__).resolve().parents[1]
def write(p,v):p.write_text(json.dumps(m.clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def payload(z,i,prefix=''):
 row=m.row(z,int(i));return m.vector(row,prefix+'position')+m.vector(row,prefix+'velocity')
def analyze(r):
 f=Path(r['source_run']);u=ULog(str(f/'flight.ulg'),message_name_filter_list=['research_p11','trajectory_setpoint','research_target','research_memory','research_actuator']);d={v.name:v.data for v in u.data_list if v.multi_id==0};p=d.get('research_p11',{});pt=np.asarray(p.get('timestamp',[]));owner=d.get('research_actuator',{});ot=np.asarray(owner.get('actuator_timestamp',[]));mem=d.get('research_memory',{});mt=np.asarray(mem.get('timestamp',[]));mk=np.asarray(mem.get('kind',[]));target=d.get('research_target',{});tt=np.asarray(target.get('timestamp',[]));events=m.lines(f/'events.jsonl');sends=m.lines(f/'explore-setpoints.jsonl');spec=r.get('explore',{})
 out={'attempt':r['attempt_id'],'source_run':str(f),'raw_retained':{name:{'exists':(f/name).exists(),'bytes':(f/name).stat().st_size if (f/name).exists() and (f/name).is_file() else None} for name in ['flight.ulg','events.jsonl','telemetry.jsonl','explore-setpoints.jsonl','gz-motor']},'recorded_ulog_hash_matches':r.get('source_integrity',{}).get('matches'),'boundaries':[]}
 for b in r['boundaries']:
  if 'owner_boundary' not in b:continue
  t=b['owner_boundary']['timestamp_us'];end=b['subject_end_us'];lower=b['request_native_lower_us'];pi=np.flatnonzero((pt>=t)&(pt<=end)&np.asarray(p.get('active',[]),bool));bb={'number':b['number'],'owner_us':t,'four_motors_observed':b.get('four_motors_observed'),'motor_applications':b.get('first_physical_motor_applications'),'native_reference_requested':spec.get('handover_reference')=='native','active_external_valid_samples':int(np.count_nonzero(p['external_valid'][pi])),'active_stale_samples':int(np.count_nonzero(p['stale'][pi])),'active_samples':len(pi),'first_active':m.row(p,int(pi[0])) if len(pi) else None}
  # Native timeout captures differ from activation. Keep both, do not assume RTGT1 handles active timeout.
  captures=[]
  for j in np.flatnonzero((tt>=lower-500000)&(tt<=end)&(np.asarray(target.get('kind',[]))==1)):
   row=m.row(target,int(j));stamp=int(tt[j]);near=int(np.searchsorted(pt,stamp,side='right'))-1;pr=m.row(p,near) if near>=0 else {};active=bool(pr.get('active')) if pr else None;activation=bool(row.get('activation'));mode=int(row['mode']);v=np.array(m.vector(row,'velocity'));vv=np.array(m.vector(row,'vehicle_velocity'));match=(mode==1 and activation) or (mode==2 and (activation or active));residual=float(abs(v[:2]-(vv[:2] if match else 0)).max());captures.append({'row':row,'after_owner_s':(stamp-t)/1e6,'active_p11_evidence':{k:pr.get(k) for k in ['timestamp','active','activation','external_valid','stale','last_valid_read_us']},'capture_type':'activation' if activation else ('active_timeout' if active else 'inactive_capture'),'expected_horizontal':'vehicle velocity' if match else 'zero','horizontal_residual_m_s':residual,'status':'VERIFIED' if residual<=1e-6 and v[2]==0 else 'NOT_VERIFIED'})
  bb['target_captures']=captures
  # Verify entry semantics from actual controller-thread memory, not requested parameter alone.
  mi=np.flatnonzero((mk==2)&(mt>=lower)&(mt<=t+100000));ma={'candidate_count':len(mi),'expected_RINI':spec.get('state_parameters',{}).get('MC_RAPTOR_RINI'),'status':'UNKNOWN'}
  if len(mi)==1:
   i=int(mi[0]);row=m.row(mem,i);mode=int(row['entry_mode']);result=int(row['entry_result']);g=np.array(m.vector(row,'gru',16));gb=np.array(m.vector(row,'gru_before_entry',16));a=np.array(m.vector(row,'previous_action',4));ab=np.array(m.vector(row,'previous_action_before_entry',4));ca=np.array(m.vector(row,'classic_action',4));checks={'requested_mode_matches':mode==ma['expected_RINI']};res={}
   if mode==0:res={'gru_zero':float(abs(g).max()),'action_zero':float(abs(a).max())};checks['entry_result_expected']=result==0
   elif mode==1:res={'gru_preserve':float(abs(g-gb).max()),'action_preserve':float(abs(a-ab).max())};checks['entry_result_expected']=result==0
   elif mode==4:res={'gru_preserve':float(abs(g-gb).max()),'action_classic_match':float(abs(a-ca).max())};checks.update(entry_applied=result==1,fresh_classic_action=0<=int(mt[i])-int(row['classic_actuator_timestamp'])<=50000)
   else:checks['implemented_in_audit']=False
   hi=np.flatnonzero((mk==1)&(mt>=mt[i]-1000000)&(mt<mt[i])&~np.asarray(mem.get('active',[]),bool));forced=np.asarray(mem.get('teacher_forced',[]),bool)[hi]
   if mode==4:checks['inactive_teacher_forced']=bool(len(hi) and forced.all())
   ma.update(entry_row=row,residuals=res,checks=checks,inactive_samples_preceding_1s=len(hi),teacher_forced_samples=int(forced.sum()),status='VERIFIED' if res and all(checks.values()) and all(np.isfinite(v) and v<=1e-7 for v in res.values()) else 'NOT_VERIFIED')
  bb['memory_entry_audit']=ma
  # Find payload-confirmed external reference before N ownership. Published != classic actually consumed.
  changes=[e for e in events if e['event']=='hundred_reference_transition' and abs(e.get('monotonic_ns',0)-b['request'].get('monotonic_ns',0))<1000000000]
  external=[];tr=d.get('trajectory_setpoint',{});trt=np.asarray(tr.get('timestamp',[]))
  for ev in changes:
   br=m.host_bracket(p,ev['monotonic_ns']);postsend=[s for s in sends if s.get('before_ns',0)>=ev['monotonic_ns']];found=None
   for j in np.flatnonzero((trt>=((br or {}).get('native_lower_us') or lower))&(trt<=min(end,t+100000))):
    val=payload(tr,j)
    matches=[s for s in postsend[:10] if np.allclose(val,s['position']+s['velocity'],atol=1e-5,rtol=0)]
    if matches:
     stamp=int(trt[j]);oi=int(np.searchsorted(ot,stamp,side='right'))-1;found={'trajectory_row':m.row(tr,int(j)),'matching_send':matches[0],'before_owner_us':t-stamp,'owner_at_publication':int(owner['owner'][oi]) if oi>=0 else None,'classic_owner_publications_after_reference_before_N':int(np.count_nonzero((ot>=stamp)&(ot<t)&(owner['owner']==2))),'claim_scope':'Reference was published while C owned motors; no direct classic input-consumption trace, so do not overclaim exact classic consumption.'};break
   external.append({'transition_event':ev,'host_to_native_bracket':br,'first_matched_published_reference':found,'causal_limitation':'Pre-N reference exposure is permitted by design and confounds an N-only target-change claim.'})
  bb['external_transition_audit']=external;out['boundaries'].append(bb)
 return m.clean(out)
def run(results):
 reports=[]
 for r in results:
  if not r.get('boundaries'):continue
  path=OUT/'runs'/r['attempt_id']/'mechanism-audit.json'
  if path.exists():audit=m.load(path)
  else:audit=analyze(r);write(path,audit)
  reports.append(audit)
 write(OUT/'mechanism-audit.json',reports)
 lines=['# 目标、记忆和电机证据审计','','原生捕获事件不等于神经最终消费目标，必须与P11实际网络目标并看。发布到trajectory_setpoint且C持权，不自动证明经典控制器具体哪次循环读取，但足以禁止“仅N受到目标突变”因果表述。','']
 for r in reports:
  lines += [f"## {r['attempt']}",f"原始ULog哈希一致={r['recorded_ulog_hash_matches']}；原始数据保留={r['raw_retained']}。"]
  for b in r['boundaries']:
   lines += [f"- 四电机应用={b['four_motors_observed']}；RINI={b['memory_entry_audit'].get('expected_RINI')}，记忆机制={b['memory_entry_audit']['status']}。",f"- 主体active采样={b['active_samples']}，external_valid={b['active_external_valid_samples']}，stale={b['active_stale_samples']}。native设计={b['native_reference_requested']}。"]
   for c in b['target_captures']:
    if c['after_owner_s']>=-.1:lines += [f"- {c['capture_type']}，owner后{c['after_owner_s']:.6f}s，模式{c['row']['mode']}，预期水平目标={c['expected_horizontal']}，残差={c['horizontal_residual_m_s']:.8f}m/s，{c['status']}。"]
   for e in b['external_transition_audit']:
    if e['transition_event'].get('method') not in ['freeze','brake']:continue
    a=e['first_matched_published_reference'];lines += [f"- 外部{e['transition_event']['method']}：首个匹配发布相对N owner提前{a['before_owner_us']/1000:.3f}ms，发布时owner={a['owner_at_publication']}（2=C），后续C电机发布{a['classic_owner_publications_after_reference_before_N']}条。不能称N独有目标突变。" if a else '- 外部参考到达时序未找到匹配，不能推测。']
  lines += ['']
 (OUT/'mechanism-audit.zh.md').write_text('\n'.join(lines)+'\n')
 return reports
if __name__=='__main__':run(m.load(OUT/'summary.json',[]))
