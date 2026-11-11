"""Read-only native Mission admission barrier; never forces or requests a mode.

The normal command/ACK/nav path must run AFTER this returns. Native listener is
used because this runner has no health_report/mission_result DDS subscriptions.
Commander normally refreshes its cached canRun result at 10 Hz; a successful
MISSION_ACK alone does not prove that refresh has happened.
"""
import re
import time

TOPICS = ('mission', 'mission_result', 'health_report', 'failsafe_flags')
FIELDS = {
    'mission': ('timestamp', 'mission_id', 'count'),
    'mission_result': ('timestamp', 'mission_id', 'seq_total', 'seq_current', 'valid', 'failure'),
    'health_report': ('timestamp', 'can_run_mode_flags'),
    'failsafe_flags': ('timestamp', 'auto_mission_missing', 'mission_failure'),
}


def parse_native(topic, output):
    """Parse only explicit scalar fields from the requested native topic."""
    if not re.search(r'^\s*TOPIC:\s*' + re.escape(topic) + r'\s*$', output, re.M):
        raise ValueError('native topic header missing: ' + topic)
    result = {}
    for key in FIELDS[topic]:
        matches = re.findall(r'^\s*' + re.escape(key) + r':\s*(True|False|[0-9]+)(?=\s|$)', output, re.M)
        if len(matches) != 1:
            raise ValueError('missing or ambiguous native field: ' + topic + '.' + key)
        token = matches[0]
        result[key] = int(token == 'True') if token in ('True', 'False') else int(token)
    return result


def readiness(rows, mission_mode, expected_count=5):
    """Require actual committed Mission plus an updated cached admission result."""
    mission, result, health, flags = (rows[name] for name in TOPICS)
    reasons = []
    if not 0 <= mission_mode < 32:
        raise ValueError('Mission nav state must fit native mode bit mask')
    if mission['timestamp'] <= 0 or mission['mission_id'] <= 0 or mission['count'] != expected_count:
        reasons.append('committed Mission missing or wrong count')
    if (result['timestamp'] < mission['timestamp'] or result['mission_id'] != mission['mission_id']
            or result['seq_total'] != expected_count or result['valid'] != 1 or result['failure'] != 0):
        reasons.append('valid matching mission_result missing')
    if health['timestamp'] < max(mission['timestamp'], result['timestamp']):
        reasons.append('health cache predates valid Mission')
    if not health['can_run_mode_flags'] & (1 << mission_mode):
        reasons.append('Mission can_run bit not set')
    if flags['timestamp'] < max(mission['timestamp'], result['timestamp']):
        reasons.append('failsafe cache predates valid Mission')
    if flags['auto_mission_missing'] != 0 or flags['mission_failure'] != 0:
        reasons.append('Mission failsafe requirements not ready')
    return reasons


def wait_mission_ready(experiment, timeout_s=5., expected_count=5):
    """Wait without bypass, retrying no command or upload; return logged evidence.

    Each listener call is bounded to 250 ms and the remaining overall deadline.
    The existing safety pump runs before and after EVERY listener invocation.
    Listener/process/safety failures propagate. Missing native topic fields wait
    only to the deadline. This reads state, not an atomic reservation: normal
    mode command/ACK/nav verification remains mandatory immediately afterward.
    """
    if timeout_s <= 0 or expected_count <= 0:
        raise ValueError('positive timeout/count required')
    experiment.cn_mission_readiness = None
    mode = int(experiment.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_MISSION)
    deadline = time.monotonic() + timeout_s
    attempts = 0
    reasons = ['native evidence not yet collected']
    rows = {}
    experiment.event('cn_mission_readiness_started', timeout_s=timeout_s, expected_count=expected_count)
    while time.monotonic() < deadline:
        rows = {}
        attempts += 1
        try:
            for topic in TOPICS:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('native Mission readiness deadline')
                experiment.pump(min(.01, remaining))
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('native Mission readiness deadline')
                output = experiment.command('listener', topic, '-n', '1', timeout=min(.25, remaining))
                experiment.pump(min(.01, max(0., deadline - time.monotonic())))
                rows[topic] = parse_native(topic, output)
            reasons = readiness(rows, mode, expected_count)
        except ValueError as exc:
            reasons = [str(exc)]
        if not reasons and time.monotonic() < deadline:
            evidence = dict(attempts=attempts, native=rows, mission_mode=mode,
                            semantics='native cached admission observed; normal mode command ACK/nav checks still required')
            experiment.cn_mission_readiness = evidence
            experiment.event('cn_mission_readiness_confirmed', **evidence)
            return evidence
        remaining = deadline - time.monotonic()
        if remaining > 0:
            experiment.pump(min(.05, remaining))
    experiment.event('cn_mission_readiness_timeout', attempts=attempts, reasons=reasons, native=rows)
    raise TimeoutError('native Mission admission readiness: ' + '; '.join(reasons))


def mission_sequence(experiment):
    """Observe native sequence for the exact Mission admitted by the barrier.

    This only replaces Mission-progress transport. Caller retains the original
    seq==1/speed/distance conditions and 200ms dwell. Duplicate timestamps are
    normal for this event topic; regressions and a different Mission fail closed.
    No mode request, upload, or policy/control modification occurs here.
    """
    proof = getattr(experiment, 'cn_mission_readiness', None)
    if not proof:
        raise RuntimeError('native Mission sequence requires completed readiness barrier')
    admitted = proof['native']['mission_result']
    experiment.pump(.01)
    output = experiment.command('listener', 'mission_result', '-n', '1', timeout=.25)
    experiment.pump(.01)
    row = parse_native('mission_result', output)
    previous = getattr(experiment, 'cn_native_mission_sequence', None)
    lower_bound = admitted['timestamp']
    if previous and previous['mission_id'] == admitted['mission_id']:
        lower_bound = max(lower_bound, previous['timestamp'])
    if (row['mission_id'] != admitted['mission_id'] or row['mission_id'] <= 0
            or row['timestamp'] < lower_bound or row['seq_total'] != admitted['seq_total']
            or row['valid'] != 1 or row['failure'] != 0
            or not 0 <= row['seq_current'] < row['seq_total']):
        raise RuntimeError('native Mission sequence is stale, invalid, failed, or belongs to a different Mission')
    experiment.cn_native_mission_sequence = row
    if previous != row:
        experiment.event('cn_native_mission_sequence', **row,
                         semantics='native mission_result; original trigger predicates and dwell remain unchanged')
    return row
