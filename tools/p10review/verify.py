#!/usr/bin/env python3
"""P10-A source-application erratum, exact counterexample and refusal audit.

Standard library only. Executes ONLY extracted pure runner profile functions,
never imports the runner, starts a process, or changes any historical evidence.
The counterexample is to an abstraction precondition, not to flight safety.
"""
import argparse
import ast
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
import struct
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
BASELINE = 'c3df8e600674ace3861b4b9181195896c6783dfc'
EP = F(1, 2**21) + F(1, 10**12)
EV = F(1, 2**23) + F(1, 10**12)
ARTIFACT = 'data/p10-20261024-a2-review'
SOURCE_HASHES = {
    'tools/run_experiment.py': '93078287c8fa9452ef928f98ea5620dbb3888386f0b6d2c7f030b75b2e9cfaf5',
    'tools/p9_predict.py': '090dbfc3e58495d7f865d8b242eea0c902343f9e0587227df5cf699abe684acf',
    'tools/p10r2/verify.py': '1acaa35be7ca9858358252269baca23392a542f83d77d97ee48a311dbced0596',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declaration():
    return {
        'schema': 'p10-a-final-gate-review-v1',
        'gate': 'NOT_PASSED',
        'canonical_report': 'docs/THOR_P10_A_FINAL_REPORT.md',
        'audit': ARTIFACT + '/audit/audit.json',
        'reviewed_baseline': BASELINE,
        'supersedes_overall_gate_in': [
            'data/p10-20261024-a2/complete-decision.json',
            'data/p10-20261024-a2/publication-receipt.json',
            'data/p10-20261024-a2/audit-source-reviewed/audit.json',
            'docs/THOR_P10_A2_REPORT.md',
        ],
        'legacy_files_preserved': True,
        'manual_proxy_theorem_retained_with_its_assumptions': True,
        'actual_complete_source_sequence_certified': False,
        'new_SITL_starts': 0, 'new_development_flights': 0,
        'new_formal_flights': 0, 'new_real_flights': 0,
        'B_C_D_started': False, 'B_C_D_authorized': False,
        'refusal': 'SOURCE_REFERENCE_OUTSIDE_A2_ENVELOPE_AND_INITIALIZATION_RELATION_UNPROVEN',
        'outside_certificate': 'UNKNOWN_NOT_NECESSARY_FAILURE',
    }


def require_declaration(value):
    if value != declaration():
        raise ValueError('GATE_OR_SCOPE_MUTATION_REJECTED')


def extract_runner_profiles():
    """Compile just three pure methods from the unchanged runner AST.

    This is a source-formula oracle, not a C++ binary or whole-runner oracle.
    No runner imports, constructor, ROS publisher, clocks or flight methods run.
    """
    source = (ROOT/'tools/run_experiment.py').read_text()
    cls = next(n for n in ast.parse(source).body
               if isinstance(n, ast.ClassDef) and n.name == 'Experiment')
    names = {'profile_cfg', 'reposition', 'p1_profile'}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if len(methods) != 3:
        raise ValueError('PURE_PROFILE_SOURCE_CHANGED')
    isolated = ast.ClassDef(name='Experiment', bases=[], keywords=[], body=methods, decorator_list=[])
    tree = ast.fix_missing_locations(ast.Module(body=[isolated], type_ignores=[]))
    env = {'__builtins__': {'getattr': getattr, 'float': float, 'abs': abs,
                            'min': min, 'max': max, '__build_class__': __build_class__},
           '__name__': 'isolated_profile_source'}
    exec(compile(tree, 'isolated_runner_profile_AST', 'exec'), env)
    lines = source.splitlines()
    evidence = {n.name: {'lines': [n.lineno, n.end_lineno],
                         'text': '\n'.join(lines[n.lineno-1:n.end_lineno])}
                for n in methods}
    return env['Experiment'], evidence


def first_held_counterexample():
    # Fixed A2 phase: at first grid point -5 s, last publisher call was -5.002 s.
    # Source gap time is tr + 3 hold + 1 ramp + 1 pre-gap cruise = tr + 5.
    tau, acceleration = F(1, 500), F(1, 2)
    delta_position = acceleration*tau*tau/2
    source_velocity = -acceleration*tau
    assert delta_position == F(1, 10**6) and source_velocity == -F(1, 1000)
    # Even allowing one full original EP/EV to perturb the source value,
    # the remaining discrepancy is larger than the original A2 envelope.
    assert delta_position-EP > EP and abs(source_velocity)-EV > EV

    cfg = json.loads((ROOT/'config/p9.json').read_text())['p5']['profile']
    assert F(str(cfg['reposition']['accel_m_s2'])) == acceleration
    assert F(str(cfg['reposition']['speed_m_s'])) == 1
    assert [cfg[k] for k in ['reference_hold_s', 'accel_s', 'pre_gap_s']] == [3, 1, 1]
    cls, source = extract_runner_profiles()
    profile = dict(cfg, start_offset_m=-5.895, cruise_s=5.6)
    obj = SimpleNamespace(pcfg=profile, cfg={'p1_speed_m_s': 1.8})
    tr = cls.reposition(obj, 0.)[3]
    pos, vel, _ = cls.p1_profile(obj, tr-float(tau))
    # Translate the source origin to put its hold endpoint at the A2 -2.7 m.
    # Translation does not change the discrepancy, velocity or branch.
    actual_delta = pos-profile['start_offset_m']
    assert abs(actual_delta-float(delta_position)) < 1e-12
    assert abs(vel-float(source_velocity)) < 1e-12
    assert cls.p1_profile(obj, tr)[1] == 0.
    translated = pos + (-2.7-profile['start_offset_m'])
    binary32 = lambda x: F.from_float(struct.unpack('!f', struct.pack('!f', x))[0])
    pos32, vel32 = binary32(translated), binary32(vel)
    assert abs(pos32+F(27, 10)) > EP and abs(vel32) > EV

    # Independently check the historical A2 reference branch, without importing
    # its matrix construction, checker, or any of its gate labels.
    tree = ast.parse((ROOT/'tools/p10r2/verify.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'reference')
    env = {'F': F, '__builtins__': {'min': min, 'max': max}}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'old_A2_reference_AST', 'exec'), env)
    assert env['reference'](-5002000) == (-F(27, 10), F(0))
    return {
        'kind': 'EXACT_SOURCE_REFERENCE_PRECONDITION_COUNTEREXAMPLE',
        'relative_first_grid_us': -5000000, 'relative_last_publish_us': -5002000,
        'hold_start_profile_time': 'tr', 'first_gap_profile_time': 'tr+5',
        'reposition_tail_time_s': str(tau), 'reposition_acceleration_m_s2': str(acceleration),
        'negative_axis_tail_formula': 's=-d+a*tau^2/2; velocity=-a*tau, d>0',
        'reference_translation': 'source hold endpoint translated to -27/10 m; arbitrary constant origin',
        'delta_position_m': str(delta_position), 'source_velocity_m_s': str(source_velocity),
        'A2_velocity_m_s': '0', 'A2_position_envelope_m': str(EP),
        'A2_velocity_envelope_m_s': str(EV),
        'position_excess_after_source_EP_and_A2_EP_m': str(delta_position-2*EP),
        'velocity_excess_after_source_EV_and_A2_EV_m_s': str(abs(source_velocity)-2*EV),
        'binary32_translated_position_m': str(pos32), 'binary32_velocity_m_s': str(vel32),
        'binary32_position_discrepancy_m': str(abs(pos32+F(27, 10))),
        'binary32_velocity_discrepancy_m_s': str(abs(vel32)),
        'pure_runner_float_crosscheck_tolerance': '1/1000000000000',
        'decision': 'REJECT_A2_APPLICATION_TO_THIS_SOURCE_REFERENCE',
        'body_initial_perturbations': 'counterexample independent of all body/queue uncertainty parameters',
        'scope': 'fixed declared phase plus source reposition formula; not a claim that every runner phase is impossible or a flight must fail',
    }, source


def refuse_changed_application(proposal):
    expected = {'include_reposition': True, 'publisher_phase_us': -2000,
                'first_grid_us': -5000000, 'EP': str(EP), 'EV': str(EV),
                'w_P_budget': '1/10000000', 'A2_prepopulated_slots': 22,
                'source_initialization_relation_proved': False}
    if proposal != expected:
        raise ValueError('UNREVIEWED_CLOCK_BUDGET_HISTORY_OR_WARMUP_CHANGE')
    first_held_counterexample()
    return 'REJECT_A2_APPLICATION_TO_THIS_SOURCE_REFERENCE'


def initialization_gap():
    source = (ROOT/'tools/p9_predict.py').read_text()
    for exact in ['STEP=.008', 'errors=[];mismatches=[];',
                  'errors.append(np.clip(e,-.5,.5))', 'j=max(0.,k-delay)',
                  'lo=int(j);hi=min(k,lo+1)']:
        assert exact in source
    a2 = (ROOT/'tools/p10r2/verify.py').read_text()
    assert 'H = F(1, 250)' in a2 and 'for j in range(1, 23):' in a2
    assert 'tau = F(11, 125)' in a2
    return {
        'P9_prediction': {'step_s': '1/125', 'initial_queue': 'empty',
            'first_update': 'append current e/d, then max(0,k-delay) repeats earliest available sample during startup',
            'delay_s': '11/125', 'full_delay_intervals': 11,
            'reposition_before_minus_5': 'omitted by original forecast too; omission is not a source guarantee'},
        'A2_proxy': {'step_s': '1/250', 'initial_queue': '22 explicitly prefilled e/d pairs before first step',
            'history': 'two-parameter kinematically consistent polynomial with constant external target',
            'physical_history_relations': 'p_dot=v and v_dot=q only; preceding controller/GRU/action dynamics not established',
            'new_model': True, 'exact_resampling_of_P9': False},
        'native': {'explicit_equivalent_error_FIFO_established': False,
            'interpretation': 'native uses current observations plus GRU/previous action and latest-value actuator path; the proxy FIFO is not a native state field',
            'source_to_proxy_queue_initialization_relation': 'UNPROVEN_NONEMPTY_SOURCE_IMAGE',
            'source_to_proxy_step_simulation': 'UNPROVEN',
            'actual_initial_controller': 'RAPTOR already active before start_stream/reposition; earlier classic label was unsupported'},
        'diagnosis': 'kinematic history is a legitimate abstract initial set but does not prove any actual runner state maps into it',
        'decision': 'REJECT_IDENTICAL_INITIALIZATION_OR_COMPLETE_SOURCE_SEQUENCE_CLAIM',
    }


def source_correspondence():
    portable = json.loads((ROOT/'data/p10-20261024-a2/source-map-final.json').read_text())
    excerpts = portable['excerpts']
    checks = [
        ('731-756', 'timestamp_last_trajectory_setpoint = current_time;',
         'valid read updates native age origin; publication stamp is not age origin'),
        ('918-958', 'current_time - timestamp_last_trajectory_setpoint',
         'strict native age guard and stale capture branch'),
        ('1311-1355', 'if (!enabled || !(rate>0.f)) return;',
         'RREC=0 excludes START under inactive initial recovery; does not cover an already active virtual target'),
        ('959-988', 'research_recovery_transition',
         'capture/profile/recovery transition occurs before sample-clock rejection'),
    ]
    rows = []
    for key, token, meaning in checks:
        assert token in excerpts[key]['text']
        rows.append({'source': portable['native_source']['path'], 'lines': key,
                     'checked_token': token, 'relation': meaning,
                     'status': 'INDIVIDUAL_RELATION_ONLY'})
    order = excerpts['959-988']['text']
    assert order.index('research_recovery_transition') < order.index('sample_clock.accept')
    runner = (ROOT/'tools/run_experiment.py').read_text()
    assert "if now-state['last']<period:return" in runner
    assert 'while time.monotonic()-self.stream_t0<total:self.pump(0.01)' in runner
    return {
        'portable_native_input_sha256': sha(ROOT/'data/p10-20261024-a2/source-map-final.json'),
        'checked_relations': rows,
        'runner_relation': 'profile formulas, gap skips, immediate gap-exit emit; pump is callback based and period is a minimum interval, not proof of exact 20ms calls',
        'source_guard_times_conditional': [204000, 520000, 11704000],
        'guard_time_scope': 'correct for the manually fixed read/publish schedule after its assumed initialization; does not repair the false first held reference',
        'RREC0_scope': 'initial inactive recovery plus constant RREC0 excludes START; prior mode and guard relations still need an initialization image',
        'unclosed': ['mapping of actual controller/GRU/action to proxy p,v,q and delayed error history',
                     'stream/reposition warmup reachable set into first A2 history',
                     'step relation covering actual reads, gyro samples and action cadence',
                     'strict model error and intersample q-output conformance'],
        'no_FIFO_claim': 'native source has no identified corresponding 22-slot clipped-e/d FIFO; no proof derives one from GRU or motor chain',
        'not_claimed': 'complete event graph simulation, binary equivalence, or formal absence of every possible queue in the native binary',
    }


def gates_and_coverage():
    return {
        'overall_gate': 'NOT_PASSED',
        'gates': [
            {'item': '47-D discrete proxy P and all-prefix tube inequalities', 'status': 'RETAINED_CONDITIONAL_PROXY_THEOREM',
             'evidence': 'original exact verifier; unchanged certificate; no source-equivalence inference'},
            {'item': 'nonzero abstract initial uncertainty and moving capture', 'status': 'PROVED_FOR_MANUAL_PROXY_CLASS',
             'evidence': 'two generators; first capture proxy velocity interval excludes zero; not a source-image proof'},
            {'item': 'strict >200ms, read-age, capture/resume and recovery guards', 'status': 'INDIVIDUAL_SOURCE_RELATIONS_CHECKED',
             'evidence': 'portable original excerpts and tracked injection; not a complete step simulation'},
            {'item': 'initial held target agrees with actual reposition tail', 'status': 'REFUTED_AT_FIRST_GRID_POINT',
             'evidence': 'delta r=1e-6 and velocity=-1e-3 exceed unchanged EP/EV'},
            {'item': 'all initial histories have nonempty source-allowed image', 'status': 'UNPROVEN',
             'evidence': '22-slot polynomial initialization differs from P9 startup and has no native FIFO mapping'},
            {'item': 'source-triggered complete sequence for all allowed initial members', 'status': 'NOT_ESTABLISHED',
             'evidence': 'source reference precondition false before gap; initialization and step relation unclosed'},
            {'item': 'complete source test/repair sufficient condition', 'status': 'NOT_DELIVERED',
             'evidence': 'manual proxy admission and instantaneous A reset budget do not supply it'},
            {'item': 'actual strict w/clock/machine envelope', 'status': 'CONDITIONAL_UNESTABLISHED',
             'evidence': 'human-chosen w<=1e-7; exact 4ms reads and fixed publisher phase are assumptions'},
            {'item': 'q interpolation and tilt', 'status': 'PROVED_ONLY_FOR_DECLARED_PROXY_OUTPUT',
             'evidence': 'exponential q interpolation with endpoint disturbance; no arbitrary intersample spikes'},
            {'item': 'height, complete task costs, actual SITL', 'status': 'OUTSIDE_PROOF',
             'evidence': 'not the sole reason for NOT_PASSED; source-model connection already fails'},
        ],
        'coverage': [
            {'location_us': -5000000, 'class': 'actual source first held reference',
             'cause': 'REFERENCE_PRECONDITION_FALSE', 'new_this_review': True,
             'decision': 'REJECT_CURRENT_CERTIFICATE_APPLICATION'},
            {'location_us': -5000000, 'class': 'initial queue/controller state',
             'cause': 'UNPROVEN_SOURCE_IMAGE_AND_NEW_MODEL_STARTUP', 'new_this_review': True,
             'decision': 'UNKNOWN_SOURCE_REACHABILITY'},
            {'location_us': -1800000, 'class': 'manual A2 set vs original A raw V<=49',
             'cause': 'OLD_DOMAIN_TOO_SMALL_IN_NEW_PROXY', 'new_this_review': False,
             'decision': 'OLD_CERTIFICATE_CANNOT_COVER; not instability'},
            {'location_us': None, 'class': 'saturated sector and RREC>0',
             'cause': 'NOT_COVERED_BY_A2_TUBE', 'new_this_review': False,
             'decision': 'UNKNOWN_NOT_NECESSARY_FAILURE'},
            {'location_us': [-5000000, 16000000], 'class': 'manual A2 declared input/history set',
             'cause': 'CONDITIONAL_ALL_PREFIX_PROOF_RETAINED', 'new_this_review': False,
             'decision': 'ABSTRACT_PROXY_ADMISSION_ONLY'},
        ],
        'actual_decision': 'REJECT_SOURCE_APPLICATION; do not rank as a substitute or authorize B/C/D',
        'future_checks': {
            'per_case_precheck_possible': ['RSH/RTGT/RTDEC/RREC', 'all specified initial history/queue coordinates if independently supplied',
                'fixed clocks and input budgets as declared assumptions', 'tube prefix/clip/output inequalities'],
            'per_case_postcheck_possible': ['observed publish/read/gyro timing, captures, resume, early returns and topic completeness if evidence exists',
                'measured trajectory membership can falsify assumptions; cannot prove unobserved continuous w bound'],
            'fundamentally_unclosed_here': ['source initialization image and step simulation relation',
                'complete stream/reposition warmup reachable set', 'actual hard model-error and intersample output interface'],
        },
    }


def run(output, gate_path):
    require_declaration(json.loads(gate_path.read_text()))
    inputs = list(SOURCE_HASHES) + ['config/p9.json', 'config/p10_a2_events.json',
        'data/p10-20261024-a2/source-map-final.json',
        'data/p10-20261024-a2/source-map-evidence.json',
        'data/p10-20261024-a2/construction-reviewed/certificate.json',
        'data/p10-20261024-a2/construction-reviewed/trace.csv.gz',
        'data/p10-20261024-a2/complete-decision.json', 'config/p10_a_gate.json']
    for name, expected in SOURCE_HASHES.items():
        if sha(ROOT/name) != expected:
            raise ValueError('SOURCE_CHANGED_REQUIRES_NEW_REVIEW: '+name)
    counter, pure_source = first_held_counterexample()
    out = {'counterexample.json': counter, 'pure-runner-formulas.json': pure_source,
           'initialization-gap.json': initialization_gap(),
           'source-correspondence.json': source_correspondence(),
           'coverage-and-gates.json': gates_and_coverage()}
    output.mkdir(parents=True, exist_ok=False)
    for name, value in out.items():
        (output/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
    audit = {
        'schema': 'p10-a-source-application-review-v1', 'gate': 'NOT_PASSED',
        'checked_baseline': BASELINE,
        'counterexample_kind': 'exact rational source-formula discrepancy; no numeric scan used as proof',
        'source_oracle_scope': 'isolated pure Python AST profiles only; no complete runner/native execution equivalence claim',
        'retained_proxy_result': 'unchanged A2 inequalities apply to its hand-specified discrete model and reference only',
        'superseded_overall_label': 'A2_DECLARED_PROXY_SUBCLASS_MEETS_REQUESTED_GATE_PENDING_PARENT_REVIEW',
        'input_sha256': {name: sha(ROOT/name) for name in inputs},
        'output_sha256': {name: sha(output/name) for name in out},
        'verifier_sha256': sha(Path(__file__)),
        'new_SITL_starts': 0, 'new_development_flights': 0, 'new_formal_flights': 0,
        'new_real_flights': 0, 'Lab_writes': 0, 'B_C_D_started': False,
    }
    (output/'audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False)+'\n')
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gate', type=Path, default=ROOT/'config/p10_a_gate.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output, args.gate)
    print(json.dumps({'gate': result['gate'], 'output': str(args.output), 'new_SITL_starts': 0}))
