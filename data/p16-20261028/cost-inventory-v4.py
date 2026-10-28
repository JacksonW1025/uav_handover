"""Named non-overlapping measured costs. Unknowns remain unknown, no fit/update."""
import sys,json,time,datetime
from pathlib import Path
sys.path.insert(0,'tools')
from p16.common import B,write,now
r=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False,parents=True);base=json.load(open(r/'costs.json'));delivery=json.load(open(r/'delivery.json'));cpu=[];walls=[]
def add(name,path,cpu_key=None,wall_key=None,layer=None):
 x=json.load(open(B/path))
 for key,val in [('CPU',cpu_key),('wall',wall_key)]:
  v=x
  if val is not None:
   for part in val.split('.'):v=v[part]
  else:v=None
  record=dict(name=name,source=path,value_s=v,layer=layer,scope='distinct actualprocess, nested components notadded twice')
  (cpu if key=='CPU' else walls).append(record)
add('oldseam calibration v1, retained engineering cost','reuse-calibration-history/summary.json','CPU_s',None,'research engineering')
add('captureseam calibration v2, deployedR prep','reuse-calibration-history-v2/summary.json','CPU_s',None,'R setup')
add('exact repeat of frozen24 forecasts','frozen-forecast-reproduce-v1/result.json','CPU_s','wall_s','diagnostic/verification')
add('OE alternate sensitivity, neverselected','OE-sensitivity-before-main/receipt.json','CPU_s','wall_s','diagnostic/verification')
add('developer2 mandatory analysisrepair','runs/p16-d02-F4-AB/analysis-v2/result.json','cost.CPU_s','cost.wall_s','common development')
add('new capture returnfield extraction probe onoldraw','return-field-probe-v1/analysis/result.json','cost.CPU_s','cost.wall_s','common integration')
add('material fullrefit validation','material-acceptance-v1/full.json',None,'elapsed_seconds','common material acceptance')
add('prequery cheapmap diagnostic','cheap-initial-prequery.json','CPU_s','wall_s','diagnostic/verification')
add('original G/R manager, alloutsidecampaign','execution-complete.json','manager_CPU_s',None,'original policy manager combined')
# Reproduced A/Grid, policies and figures are included in the postprocess childaggregate.
add('finalreport +tests +audit aggregate','postprocessing-complete.json','children_CPU_s',None,'postprocessing, nestedcomponents excluded')
if (B/'main-score-results-v1/result.json').exists():add('independent main-only scoring checkpoint','main-score-results-v1/result.json','CPU_s','wall_s','posthoc scoring')
if (B/'auxiliary-analysis-cost.json').exists():add('three independent supplements/figures','auxiliary-analysis-cost.json','children_CPU_s','wall_s','posthoc diagnosis/figures')
initialCPU=sum(x['CPU_s'] for x in json.load(open(B/'frozen/initial-predictions.json')).values());cpu.append(dict(name='original24 EE forecasts',value_s=initialCPU,source='frozen/initial-predictions.json eachCPU_s exactlyonce',layer='G/R primary sharedsetup'))
postfix=json.load(open(B/'runs/p16-d02-F4-AB/analysis-v2/result.json'))['cost'];probe=json.load(open(B/'return-field-probe-v1/analysis/result.json'))['cost'];common_extra_CPU=postfix['CPU_s']+probe['CPU_s'];common_extra_wall=postfix['wall_s']+probe['wall_s'];views={}
for method,value in delivery['methods'].items():
 views[method]=[]
 for p in value['series']:
  views[method].append(dict(query=p['query'],pairwise_half_prep_wall_lower_s=p['pairwise_half_prep_wall_lower_s']+common_extra_wall/2,standalone_full_prep_wall_lower_s=p['standalone_full_prep_wall_lower_s']+common_extra_wall,pairwise_half_prep_CPU_lower_with_replay_estimate_s=p['pairwise_half_prep_CPU_lower_s']+common_extra_CPU/2,standalone_full_prep_CPU_lower_with_replay_estimate_s=p['standalone_full_prep_CPU_lower_s']+common_extra_CPU,original_policyworkflow_CPU_permethod=None,reason='newreview/probe costs added to commonC consistentlyhalf/full, frozenattribution unchanged; originalG/R manageronlyaggregate, replay isestimate'))
a=json.load(open(B/'host-release-before-main.json'));z=json.load(open(B/'execution-complete.json'));formalwall=(datetime.datetime.fromisoformat(z['time'])-datetime.datetime.fromisoformat(a['time'])).total_seconds();firstwait=(B/'wait-host-before-main.log').read_text().splitlines()[0].split(' ')[0];externalwait=(datetime.datetime.fromisoformat(a['time'])-datetime.datetime.fromisoformat(firstwait)).total_seconds()
knownCPU=base['actual_CPU_measured_lower_s']+sum(x['value_s'] for x in cpu if x['value_s'] is not None)
write(out/'inventory.json',dict(time=now(),v2_costs_retained=str(r/'costs.json'),actual_unique_START=base['actual_unique_START'],actual_physical_andcampaign_CPU_lower_s=base['actual_CPU_measured_lower_s'],additional_measured_components_CPU=cpu,additional_measured_components_wall=walls,project_named_measured_CPU_lower_s=knownCPU,formal_elapsed_wall_s=formalwall,formal_outside_campaign_wall_s=formalwall-sum(x['wall_s'] for x in base['actual_records'] if x['stage']!='development'),active_development_plus_formal_envelope_wall_s=base['setup_development_wall_s']+formalwall,previous_inventory_retained='cost-inventory-results-v3/inventory.json',external_ToDesk_guard_wait_wall_s=externalwait,supplementary_commonprep_sensitivity_views=views,primary_frozen_cost_views_retained=str(r/'costs.json'),late_reconstruction_disclosure='namedrepair/probe amounts recovered afterexposure; primaryv2 lowercostviews retained, supplementary commonC half/full disclosed not selected to favor method',unknowns=base['unknown_costs']+['CPU materialfullvalidation','calibrationv1/v2 wall','otherpreparation commands/tests CPU andsomewall','originalG/R managerperpolicy split','publication shell/human cost'],not_added_twice=['campaignmanager wallincludes physical/review','finalpostprocess CPU alreadyincludes baseline/policyreplay/report/figures/tests/audit','primaryR53calibration inpolicyviews notaddedagain as secondprocess'],interpretation='namedactualcost lowerbound plus explicitlymarkedreplayestimates; not complete totalcostsaving certification, no zero for UNKNOWN',attribution='primaryv2frozen views unchanged; namedactualproject additions and disclosedsupplementary commonC sensitivity bothreported, no favorableviewselected',policy_scores_changed=False))
