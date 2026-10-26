#!/usr/bin/env python3
"""Actual event table plus COM geometry/velocity provenance; writes new outputs only."""
import json,sys,math,importlib.util
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(R/'data/p12b-20261026-analysis-source'))
from event_tables import create
from p12c.features import load
from p3_memory import rotation

def process(parent,out):
 if out.exists():raise FileExistsError(out)
 create(parent/'run',parent/'analysis',out);table=json.load(open(out/'event-states.json'));d=load(parent/'run',parent/'analysis');r=.24186913101803548;rows=[]
 for row in table['rows']:
  if not row.get('state'):continue
  hits=np.flatnonzero(d['sample_us']==row['sample_us']);assert len(hits)==1;i=int(hits[0]);qt=d['truth_q'][i];qc=d['attitude'][i];R0=rotation(qc).reshape(3,3);omega=d['omega'][i];term=r*(R0[2,0]*omega[1]-R0[2,1]*omega[0]);ct=1-2*(qt[1]**2+qt[2]**2);geom=r*ct;rows.append({'label':row['label'],'sample_us':int(d['sample_us'][i]),'native_us':int(d['native_us'][i]),'host_read_interval_ns':[int(d['run_wall_ns'][i]),int(d['read_wall_ns'][i])],'H_model_source':'held Gazebo model-origin pose, H=-z','H_model_m':row['state']['world_height_m'],'H_COM_correlated_geometry_estimate_m':row['state']['world_height_m']+geom,'truth_attitude_age_us':int(d['sample_us'][i]-d['truth_q_sample'][i]),'truth_position_age_us':int(d['sample_us'][i]-d['truth_pv_sample'][i]),'W_model_callback_difference_m_s':row['state']['world_down_velocity_callback_difference_m_s'],'W_LP_m_s':row['state']['LP_down_velocity_m_s'],'COM_geometry_derivative_from_controller_cache_m_s':float(term),'W_COM_if_coincident_states_m_s':row['state']['world_down_velocity_callback_difference_m_s']-float(term),'velocity_scope':'W_model callback finite difference and attitude/gyro cache have distinct times; COM W is a mixed-source estimate, NOT direct physical velocity or certified interval','exact_relation':'H_model=H_COM-ez R r; W_model=W_COM+ez R(omega cross r); transforms NED/FRD to world-up/body-up consistently, derivative of r*R33','candidate_domain_velocity_term_abs_bound_m_s':r*math.sin(math.radians(50))*math.sqrt(2)*8,'future_velocity_error_interval':'UNKNOWN until callback differentiation, cache/time and gyro error bounds supplied; no invented zero uncertainty'})
 (out/'event-COM-geometry.json').write_text(json.dumps({'schema':'p12c-event-geometry-1','origin_COM_distance_m':r,'rows':rows,'capture_resume_does_not_reset_L_D':True,'W_sources_never_conflated':True},indent=2)+'\n');return table
if __name__=='__main__':process(Path(sys.argv[1]),Path(sys.argv[2]))
