"""Prospective P12c platform tests; no SITL starts."""
import sys,json,importlib.util
from pathlib import Path
import numpy as np
import pytest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from p12c_platform.campaign import claim
from p12c_platform.accept import metrics,dynamic_pass

def test_budget_is_new_but_never_zeroes_prior56_or_replaces_invalid():
 rows=[{'event':'START_INTENT','id':str(i),'budget_class':'preparation'} for i in range(12)]
 assert claim(rows,'f1','formal')==13
 with pytest.raises(RuntimeError,match='cap'):claim(rows,'p13','preparation')
 with pytest.raises(RuntimeError,match='already'):claim(rows,'0','formal')
 with pytest.raises(RuntimeError,match='critical'):claim(rows+[{'event':'STOP_CRITICAL'}],'f1','formal')
 with pytest.raises(RuntimeError,match='cap'):claim(rows+[{'event':'START_INTENT','id':f'f{i}','budget_class':'formal'} for i in range(24)],'extra','formal')

def test_actual_clean_source_has_one_canonical_and_no_duplicate_publication():
 from apply_p12b import LEGACY_CPP,CANONICAL_CPP,LEGACY_HPP,CANONICAL_HPP
 p=R/'uav_lab/.local/checkouts/px4-raptor/src/modules/mc_raptor';new=(p/'mc_raptor.cpp').read_text();old=(R/'data/p12c-20261026-preparation/baseline-observer-source/mc_raptor.cpp').read_text()
 assert new.count('handover_research::p12b_trace(_p12b)')==1 and new.count('_p12b_pub.publish')==0
 assert new.index('_p12b.timing_initialized_pre=')<new.index('status.subscription_update_trajectory_setpoint = use_external_reference')
 assert new.index('handover_research::p12b_trace(_p12b)')<new.index('const unsigned input_result=_sample_clock.accept')
 assert new.replace(CANONICAL_CPP,LEGACY_CPP)==old
 h=(p/'mc_raptor.hpp').read_text();assert '_p12b_pub' not in h
 assert h.replace(CANONICAL_HPP,LEGACY_HPP)==(R/'data/p12c-20261026-preparation/baseline-observer-source/mc_raptor.hpp').read_text()


def test_all_prespecified_configs_keep_heavy_off_and_formal_on():
 protocol=json.load(open(R/'data/p12c-20261026-preparation/protocol.json'));formal=json.load(open(R/'config/p12c-platform.json'))
 assert len(protocol['rows'])==12 and len(formal['rows'])==24
 assert {r['block'] for r in formal['rows']}=={7,8}
 assert {r['sim_seed'] for r in formal['rows']}=={1334287007,1334288008}
 for r in protocol['rows']+formal['rows']:
  c=json.load(open(R/r['config']));assert not c['p12b']['solver_observe'] and not c['p12c_platform']['heavy_solver']
  assert c['p12']['repair_sample_window']
 assert all(r['observe'] for r in formal['rows'])
 for cls in ['NORMAL','SAFE_EVENT','BOUNDARY']:
  rr=[r for r in protocol['rows'] if r['class']==cls]
  assert len(rr)==4 and sum(r['observe'] for r in rr)==2


def test_all_valid_common_prefix_cannot_hide_early_dynamic_error():
 t=np.arange(6,dtype=float);a={'t':t,**{k:np.zeros(6) for k in ['tilt','L_world','L_LP','W','track']}};b={k:v.copy() for k,v in a.items()};b['tilt'][1]=8
 m=metrics(a,b,0,5);sc={'tilt_deg':5,'world_loss_m':.2,'LP_loss_m':.2,'LP_down_velocity_m_s':.2,'tracking_error_m':.2}
 assert not dynamic_pass(m,sc) and m['rows']==6
 assert dynamic_pass(metrics(a,b,2,5),sc) # demonstrates why chosen late window is forbidden


def test_new_off_does_not_claim_unobserved_readiness():
 s=(R/'tools/p12c_platform/workflow.py').read_text()
 assert 'MEASURED_READINESS_UNOBSERVED' in s and 'no inferred initialization' in s
 assert 'last_GRU' not in s
 spec=json.load(open(R/'data/p12c-20261026-preparation/noninterference-spec.json'))
 assert 'cannot establish population equivalence' in spec['sufficiency']['statistics']
