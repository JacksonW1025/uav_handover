"""Real-source continuation repair-window regressions, no SITL."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from p12c.native_oracle import Oracle
from test_p12 import native_row

def test_window_inhibits_delayed_startup_capture_after_real_external_read():
 o=Oracle(repair=True,window_ms=100500)
 try:
  o.tick(native_row(0,True));r=o.tick(native_row(204000))
  assert r[0]==1 and r[8]==0 # real strict guard capture, T0 velocity
 finally:o.close()

def test_window_only_changes_capture_reference_not_guard():
 o=Oracle(repair=True,window_ms=100500)
 try:
  o.tick(native_row(0,True));o.tick(native_row(300000,True))
  assert o.tick(native_row(500000))[0]==0 # exact200ms never force capture
  r=o.tick(native_row(504000));assert r[0]==1 and abs(r[8]-1.8)<1e-6
 finally:o.close()

def test_zero_inhibit_and_legacy_default_are_distinct():
 for ms,velocity in [(0,0),(-1,1.8)]:
  o=Oracle(repair=True,window_ms=ms)
  try:
   o.tick(native_row(0,True));r=o.tick(native_row(204000));assert abs(r[8]-velocity)<1e-6
  finally:o.close()


def test_continuation_budget_keeps_old_nine_and_counts_every_intent(tmp_path,monkeypatch):
 import json,pytest
 from p12c import campaign
 old=tmp_path/'data/p12-20261026-preparation';old.mkdir(parents=True)
 (old/'attempts.jsonl').write_text('\n'.join(json.dumps({'event':'START_INTENT','id':str(i)}) for i in range(9)))
 monkeypatch.setattr(campaign,'ROOT',tmp_path)
 prep=[{'event':'START_INTENT','budget_class':'development','id':'d'+str(i)} for i in range(12)]
 assert campaign.claim(prep,{'id':'f1'})==(1,13)
 full=prep+[{'event':'START_INTENT','budget_class':'formal','id':'f'+str(i)} for i in range(48)]
 with pytest.raises(RuntimeError,match='budget'):campaign.claim(full,{'id':'other'})
 with pytest.raises(RuntimeError,match='already'):campaign.claim(prep,{'id':'d0'})
 with pytest.raises(RuntimeError,match='critical'):campaign.claim(prep+[{'event':'STOP'}],{'id':'other'})
