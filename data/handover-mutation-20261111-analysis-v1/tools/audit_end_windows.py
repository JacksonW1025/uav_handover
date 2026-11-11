"""Separate subject, uncertain event bracket and post-protection tail, never rewrite per-run primary."""
import json
from pathlib import Path
import numpy as np
from pyulog import ULog
import metrics_base as m
OUT=Path(__file__).resolve().parents[1]
def run(results):
 reports=[]
 for r in results:
  if not r.get('boundaries'):continue
  flight=Path(r['source_run']);u=ULog(str(flight/'flight.ulg'));d={v.name:v.data for v in u.data_list if v.multi_id==0};events=m.lines(flight/'events.jsonl');p=d.get('research_p11',{});a=d.get('vehicle_attitude',{});tt=np.asarray(a.get('timestamp',[]),dtype=np.int64)
  if not len(tt):continue
  tilt=np.degrees(np.arccos(np.clip(1-2*(a['q[1]']**2+a['q[2]']**2),-1,1)))
  for b in r['boundaries']:
   if 'owner_boundary' not in b:continue
   start=b['owner_boundary']['timestamp_us'];end=b['subject_end_us']
   def peak(lo,hi):
    ix=np.flatnonzero((tt>=lo)&(tt<=hi))
    if not len(ix):return None
    j=ix[np.argmax(tilt[ix])];return {'tilt_deg':float(tilt[j]),'native_us':int(tt[j]),'after_owner_s':(int(tt[j])-start)/1e6,'window_start_us':int(lo),'window_end_us':int(hi)}
   fail=[e for e in events if e['event']=='failure'];brackets=[m.host_bracket(p,e.get('monotonic_ns')) for e in fail];emergency=[e for e in events if e['event'].startswith('explore_emergency_landing')]
   valid=[v for v in brackets if v and v.get('native_lower_us') is not None and v.get('native_upper_us') is not None and v['native_lower_us']>=start]
   f=valid[0] if valid else None
   reports.append({'attempt':r['attempt_id'],'boundary':b['number'],'subject_end_reason':b['subject_end_reason'],'subject_end_us':end,'subject_peak':peak(start,end),'failure_brackets':brackets,'uncertain_failure_bracket_peak':peak(f['native_lower_us']+1,f['native_upper_us']-1) if f else None,'strictly_after_failure_bracket_tail_peak':peak(f['native_upper_us'],int(u.last_timestamp)) if f else None,'post_subject_tail_peak':peak(end+1,int(u.last_timestamp)),'tail_note':'Excluded from subject, frozen and task outcomes. The tail may contain LAND request or controller transitions; not an unconstrained continuation. A LAND acknowledgement is not observed landing.','emergency_landing_events':emergency,'landing_observed':r.get('completion',{}).get('landed_observed'),'disarm_observed':r.get('completion',{}).get('disarmed_observed'),'ulog_last_us':int(u.last_timestamp)})
 (OUT/'subject-vs-cleanup-audit.json').write_text(json.dumps(m.clean(reports),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 lines=['# 主体与保护后尾段：严格分离','','主体指标保留原分析，不受下列尾段极值影响。failure为host事件，使用P11采样夹逼，主体截至原生下界；上下界间不确定区间及上界之后尾段独立列出。无落地观测不等于已落地。','']
 for r in reports:
  if r['failure_brackets']:
   lines += [f"## {r['attempt']}",f"主体峰值：{r['subject_peak']}",f"failure时间夹逼：{r['failure_brackets']}",f"不确定夹逼区间峰值：{r['uncertain_failure_bracket_peak']}",f"明确保护事件后尾段峰值（非主体）：{r['strictly_after_failure_bracket_tail_peak']}",f"落地观测={r['landing_observed']}，disarm观测={r['disarm_observed']}；事件={[e['event'] for e in r['emergency_landing_events']]}。",'']
 (OUT/'subject-vs-cleanup.zh.md').write_text('\n'.join(lines)+'\n')
 return reports
if __name__=='__main__':run(m.load(OUT/'summary.json',[]))
