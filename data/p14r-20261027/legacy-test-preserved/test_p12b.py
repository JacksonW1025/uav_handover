"""P12b real source contract, audit rejection and distinct budget regressions; no SITL."""
import sys,json,subprocess
from pathlib import Path
import numpy as np
import pytest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from p12b.contract import decision

def test_real_header_phase_contract_and_initialization(tmp_path):
 code='''#include "research/state/P12Controls.hpp"
#include <cassert>
int main(){using handover_research::p12_delivery_allowed;
for(int ph=0;ph<=2;ph++)for(bool active:{false,true})for(bool init:{false,true})for(unsigned f:{0u,2u})for(unsigned i=0;i<4;i++){
 bool applies=active&&ph!=0&&init&&f!=0;bool expected=!applies||(ph==1?i%f==0:i%f!=0);
 assert(p12_delivery_allowed(ph,active,init,i,f)==expected);
}
// Inactive shadow last-GRU may be nonzero: it is deliberately not an input.
assert(p12_delivery_allowed(2,true,false,0,2));assert(!p12_delivery_allowed(2,true,true,0,2));
assert(p12_delivery_allowed(2,true,true,0,0));
}'''.replace('#include <cassert>','#include <cassert>\n#include <initializer_list>')
 p=tmp_path/'test.cpp';p.write_text(code);subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I',str(R),str(p),'-o',str(tmp_path/'test')],check=True);subprocess.run([str(tmp_path/'test')],check=True)

def test_force_sync_flag_logged_but_not_invented_gate_condition():
 assert decision(2,True,False,True,0,2)['gate_permit']
 assert decision(2,True,True,False,0,0)['gate_permit']
 assert not decision(2,True,True,False,0,2)['gate_permit']
 assert decision(2,True,True,True,1,2)['gate_permit']

def fixture_topics(initialized=False):
 def arr(a):return np.asarray(a)
 n=2;d={k:arr(v) for k,v in {'active':[1,1],'timestamp_sample':[100000,104000],'timestamp':[100000,104000],'history_count_before':[0,0],'history_count_after':[0,1],'actual_commit':[1,0],'predicted_commit':[1,0],'call_index_before':[0,1],'call_index_after':[1,2],'requested_phase':[2,2],'gate_pending':[1,1],'gate_permit':[1,1],'read_begin_wall_ns':[10,20],'read_end_wall_ns':[15,25]}.items()}
 old={k:arr(v) for k,v in {'active':[1,1],'timestamp_sample':[100000,104000],'external_valid':[1,1],'subscription_updated':[1,1]}.items()}
 for k in ['history_before','history_after']:
  for i in range(4):d[f'{k}[{i}]']=np.zeros(n)
 for k,num in [('previous_action_before',4),('policy_input',22)]:
  for i in range(num):old[f'{k}[{i}]']=np.zeros(n)
 pre={k:arr(v) for k,v in {'active':[1,1],'timestamp_sample':[100000,104000],'pre_read_wall_ns':[12,22],'timing_initialized_pre':[initialized,True],'force_sync_initialized_pre':[1,1],'call_index_pre':[0,1],'force_sync_pre':[2,2],'requested_phase':[2,2],'gate_applicable':[False,True],'gate_permit':[1,1],'read_updated':[1,1],'read_valid':[1,1],'last_valid_read_pre':[0,100000],'last_valid_read_post':[100000,104000],'activation':[1,0]}.items()}
 return {'research_p12':d,'research_p11':old,'research_p12b':pre,'research_target':{'kind':np.array([],int)},'research_timing':{}}

def audit_fixture(monkeypatch,tmp_path,initialized=False):
 from types import SimpleNamespace as S
 import p12b.audit as a
 topics=fixture_topics(initialized);monkeypatch.setattr(a,'ULog',lambda *args,**kwargs:S(data_list=[S(name=k,data=v,multi_id=0) for k,v in topics.items()]))
 run=tmp_path/'run';run.mkdir();(run/'flight.ulg').write_bytes(b'synthetic explicit pre-read unit only');(run/'config.json').write_text('{}')
 return a.audit(run,tmp_path/'audit')

def test_history_array_not_overwritten_by_contract_dicts(monkeypatch,tmp_path):
 r=audit_fixture(monkeypatch,tmp_path)
 assert r['status']=='PASS' and r['gates']['history_input']
 assert r['pre_read_contract']['initialization_bypass_rows']==1

def test_first_row_is_not_blanket_exempt(monkeypatch,tmp_path):
 r=audit_fixture(monkeypatch,tmp_path,True)
 assert r['status']=='FAIL' and not r['gates']['read_phase']

def test_independent_budget_counts_all_intents_and_old48():
 from p12b.campaign import claim
 items=[{'event':'START_INTENT','id':f'd{i}','budget_class':'preparation'} for i in range(8)]
 assert claim(items,'f0','formal')==1
 with pytest.raises(RuntimeError,match='cap'):claim(items,'other','preparation')
 with pytest.raises(RuntimeError,match='already'):claim(items,'d0','formal')
 full=items+[{'event':'START_INTENT','id':f'f{i}','budget_class':'formal'} for i in range(45)]
 with pytest.raises(RuntimeError,match='cap'):claim(full,'last','formal')
 with pytest.raises(RuntimeError,match='critical'):claim(items+[{'event':'STOP_CRITICAL'}],'f','formal')

def test_source_pre_read_snapshot_precedes_consumption():
 s=(R/'uav_lab/.local/checkouts/px4-raptor/src/modules/mc_raptor/mc_raptor.cpp').read_text()
 assert s.count('_p12b.timing_initialized_pre=')==1
 assert s.index('_p12b.timing_initialized_pre=')<s.index('status.subscription_update_trajectory_setpoint = use_external_reference')
 assert s.index('_p12b_pub.publish(_p12b)')<s.index('const unsigned input_result=_sample_clock.accept')
 assert 'last_gru' not in s[s.index('static const param_t p12b_param'):s.index('bool use_external_reference')]

def test_design_preserves_pending_order_and_new_seeds():
 b=json.load(open(R/'config/p12b.json'));o=json.load(open(R/'config/p12-cont.json'));pending=json.load(open(R/'data/p12-cont-20261026-delivery-v2/startup-exclusion-ledger.json'));ids={r['id'] for r in pending if r['status']=='NOT_STARTED'}
 assert len(b['rows'])==45 and [r['source_id'] for r in b['rows'][:21]]==[r['id'] for r in o['rows'] if r['id'] in ids]
 assert all(r['source_id'] not in ['b1-ph2-NORMAL1','b3-ph2-NORMAL1'] for r in b['rows'][:21])
 assert {r['sim_seed'] for r in b['rows'][21:]}=={1334275356,1334276365}
 assert all(r['family']=='F4' for r in b['rows'][21:])


def test_direct_trace_writes_exact_native_fields_and_rejects_truncation(tmp_path):
 from p12b.read_trace import load,dtype
 stub=tmp_path/'uORB/topics';stub.mkdir(parents=True)
 fields=[]
 for line in (R/'research/state/ResearchP12b.msg').read_text().splitlines():
  if not line or line.startswith('#') or '=' in line:continue
  t,n=line.split();fields.append(({'uint64':'uint64_t','uint32':'uint32_t','int32':'int32_t','bool':'bool'}[t],n))
 (stub/'research_p12b.h').write_text('#pragma once\n#include <cstdint>\nstruct research_p12b_s{'+''.join(t+' '+n+'{};' for t,n in fields)+'};')
 code=tmp_path/'writer.cpp';code.write_text('#include "research/state/P12bTrace.hpp"\nint main(){research_p12b_s m{};m.timestamp_sample=123456;m.active=true;m.timing_initialized_pre=false;m.gate_permit=true;handover_research::p12b_trace(m);m.timestamp_sample=127456;m.timing_initialized_pre=true;handover_research::p12b_trace(m);}')
 exe=tmp_path/'writer';subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I',str(tmp_path),'-I',str(R),str(code),'-o',str(exe)],check=True)
 import os
 path=tmp_path/'read.bin';subprocess.run([str(exe)],env=dict(os.environ,HANDOVER_P12B_READ_TRACE=str(path)),check=True)
 d=load(path);assert d['timestamp_sample'].tolist()==[123456,127456] and d['sequence'].tolist()==[0,1] and d['timing_initialized_pre'].tolist()==[0,1]
 raw=path.read_bytes();bad=tmp_path/'partial.bin';bad.write_bytes(raw[:-1])
 with pytest.raises(RuntimeError,match='partial'):load(bad)
 a=np.frombuffer(raw,dtype()).copy();a['sequence'][1]=8;bad2=tmp_path/'gap.bin';bad2.write_bytes(a.tobytes())
 with pytest.raises(RuntimeError,match='sequence'):load(bad2)


def test_v2_never_changes_original_pending_cases_order_or_seeds():
 b=json.load(open(R/'config/p12b-v2.json'));old=json.load(open(R/'config/p12b.json'))
 assert [(r['source_id'],r['sim_seed'],r['phase'],r['branch']) for r in b['rows']]==[(r['source_id'],r['sim_seed'],r['phase'],r['branch']) for r in old['rows']]
 assert all(r['id'].startswith('v2-') for r in b['rows'])
 from p12b.campaign_v2 import claim
 previous=[{'event':'START_INTENT','id':'prep1','budget_class':'preparation'},{'event':'START_INTENT','id':'prep2','budget_class':'preparation'}]
 assert claim(previous,'prep3-v2','preparation')==3
 with pytest.raises(RuntimeError,match='cap'):claim(previous+[{'event':'START_INTENT','id':f'v{i}','budget_class':'preparation'} for i in range(6)],'extra','preparation')


def test_solver_extended_limits_do_not_silently_accept_infinity_mismatch():
 from p12b.solver import extended_limit_error
 assert extended_limit_error(float('inf'),float('inf'))==0
 assert extended_limit_error(-float('inf'),-float('inf'))==0
 assert extended_limit_error(float('inf'),3)==float('inf')
 assert extended_limit_error(-float('inf'),float('inf'))==float('inf')
 assert extended_limit_error(2,3)==1


def margin_module():
 import importlib.util
 spec=importlib.util.spec_from_file_location('p12b_margin',R/'data/p12b-20261026-analysis-source/margin_map.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_event_margin_keeps_hidden_prefix_failure_after_height_recovery():
 from fractions import Fraction as F
 m=margin_module()
 # Loss rises above1 mid-segment then returns below1: endpoint-only is unsound.
 L,V,D=m.advance(F('0.9'),F(1),F('0.9'),F(2),F(-1))
 assert L==F('0.9') and D==F('1.4')
 # A later height recovery cannot undo historical violation.
 assert m.advance(L,V,D,F(1),F(0))[2]==D


def test_event_map_composition_keeps_residual_velocity_and_declares_counterexample_scope():
 from fractions import Fraction as F
 m=margin_module()
 a=m.advance(F('.1'),F('.2'),F('.1'),F('.3'),F('.4'))
 b=m.advance(*a,F('.7'),F('.4'))
 whole=m.advance(F('.1'),F('.2'),F('.1'),F(1),F('.4'))
 assert b==whole
 e=m.example();assert e['single'][-1]['historical_max_loss_m']<1<e['AB'][-1]['historical_max_loss_m']
 assert 'not a proven reachable' in e['meaning']


def test_no_formal_release_from_valid_prefix_or_unproved_theory():
 stop=json.load(open(R/'data/p12b-20261026-preparation-v2/formal-stop.json'))
 assert stop['counts']['P12b_preparation']==8 and stop['counts']['P12b_formal']==0
 assert len(stop['pending'])==45 and stop['theory_not_stop_reason']
 assert len({r['id'] for r in stop['pending']})==45
 original=json.load(open(R/'data/p12b-20261026-preparation-v2/acceptance.json'))
 assert original['experimental_engineering_status']=='FAIL'
 review=json.load(open(R/'data/p12b-20261026-delivery/reviewed/common-prefix-review-v2.json'))
 assert review['release'].startswith('NOT_PASSED')
