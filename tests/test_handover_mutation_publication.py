"""Offline publication integrity checks. Never start a flight or rewrite evidence."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/handover-mutation-20261111-analysis-v1'
BATCH = ROOT / 'data/handover-mutation-20261111'


def load(path):
    return json.loads(path.read_text())


def test_original_delivery_manifest_matches_exact_bytes():
    for record in load(OUT / 'delivery-manifest.json')['files']:
        data = (OUT / record['path']).read_bytes()
        assert len(data) == record['bytes']
        assert hashlib.sha256(data).hexdigest() == record['sha256']


def test_published_sources_match_original_workspace_snapshot():
    source = load(ROOT / 'data/handover-mutation-20261111-publication-v1/source-manifest.json')
    for record in source['source_files']:
        data = (ROOT / record['path']).read_bytes()
        assert len(data) == record['bytes']
        assert hashlib.sha256(data).hexdigest() == record['sha256']


def test_all_starts_and_failures_remain_visible():
    rows = [json.loads(line) for line in (BATCH / 'attempts.jsonl').read_text().splitlines()]
    starts = [r['attempt_id'] for r in rows if r['event'] == 'START_INTENT']
    ends = [r for r in rows if r['event'] == 'PHYSICAL_END']
    summary = load(OUT / 'summary.json')
    assert len(starts) == len(set(starts)) == len(ends) == len(summary) == 23
    assert set(starts) == {r['attempt_id'] for r in ends} == {r['attempt_id'] for r in summary}
    assert Counter(r['execution_status'] for r in ends) == {'PASS': 10, 'FAIL': 12, 'INFRASTRUCTURE_INTERRUPTED': 1}
    assert sum(bool(r['boundaries']) for r in summary) == 22
    assert Counter(r['frozen_primary_status'] for r in summary) == {'FAILURE': 15, 'SUCCESS': 5, 'UNKNOWN': 3}
    assert Counter(r['observed_physical_frozen_status'] for r in summary if r['boundaries']) == {'FAILURE': 15, 'SUCCESS': 7}
    assert sum(r.get('completion', {}).get('normal_landing_disarm', False) for r in summary) == 10
    assert len(list(csv.DictReader((OUT / 'cases.csv').open()))) == 23
    assert summary[0]['interruption_recovery']['normal_recovery_landing_confirmed']
    assert not summary[0]['boundaries']


def test_both_candidate_versions_and_exact_runner_delta():
    versions = load(OUT / 'candidate-versions.json')
    records = versions['records']
    assert len(records) == 23
    assert Counter(r['canonical_json_sha256'] for r in records) == versions['groups']
    for r in records:
        assert hashlib.sha256(json.dumps(r['candidate'], sort_keys=True).encode()).hexdigest() == r['canonical_json_sha256']
    assert sum(r['before_after_equal'] is True for r in records) == 22
    groups = {}
    for r in records:
        groups.setdefault(r['canonical_json_sha256'], r['candidate'])
    before, after = groups.values()
    assert before['project_head'] == after['project_head'] == '003cd249a0b1baa3ad78a25c18473657af39aa70'
    assert before['lab'] == after['lab']
    assert [k for k in before['files'] if before['files'][k] != after['files'][k]] == ['tools/handover_mutation/runner.py']
    assert hashlib.sha256((ROOT / 'tools/handover_mutation/runner.py').read_bytes()).hexdigest() == after['files']['tools/handover_mutation/runner.py']


def test_raw_index_is_complete_but_bytes_are_not_published():
    records = load(OUT / 'raw-source-index.json')['files']
    assert len(records) == 183
    assert sum(r['bytes'] for r in records) == 1424096495
    assert len({r['local_path'] for r in records}) == len(records)
    assert sum(r['local_path'].endswith('/flight.ulg') for r in records) == 23
    for r in records:
        assert r['included_in_delivery'] is False
        assert len(r['sha256']) == 64
        relative = Path(r['local_path']).relative_to('/home/car/uav_handover')
        assert not (ROOT / relative).exists()


def test_scene_mismatch_not_promoted_to_success():
    summary = {r['attempt_id'][:3]: r for r in load(OUT / 'summary.json')}
    for name in ('015', '016', '017'):
        assert summary[name]['scenario_realization'] == 'NOT_REALIZED_ACTIVE_TIMEOUT'
    for name in ('016', '017'):
        assert summary[name]['frozen_primary_status'] == 'UNKNOWN'
    for name in ('011', '018', '019'):
        assert summary[name]['attempt']['execution_status'] == 'PASS'
        assert summary[name]['frozen_primary_status'] == 'FAILURE'
    for name in ('022', '023'):
        assert summary[name]['scenario_realization'] == 'VERIFIED_ACTIVE_TIMEOUT'
    assert summary['022']['observed_physical_frozen_status'] == 'FAILURE'
    assert summary['023']['observed_physical_frozen_status'] == 'SUCCESS'
