#!/usr/bin/env python3
"""Independent P12 overlay; run after apply_research, before compilation.

Only the delivery gate and capture-mode override affect control semantics.
Observation fields never feed control. Every edit checks a unique anchor.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PX = ROOT / 'uav_lab/.local/checkouts/px4-raptor'


def edit(path, old, new):
    file = PX / path
    s = file.read_text()
    if new in s:
        assert s.count(new) == 1, path
        return
    if s.count(old) != 1:
        raise RuntimeError('P12 unique anchor missing: ' + path + ': ' + old[:80])
    file.write_text(s.replace(old, new, 1))


def apply():
    for name in ['ResearchP12.msg']:
        shutil.copy2(ROOT / 'research/state' / name, PX / 'msg' / name)
    shutil.copy2(ROOT / 'research/state/P12Controls.hpp', PX / 'src/lib/handover_research/P12Controls.hpp')
    edit('msg/CMakeLists.txt', '\tVehicleAirData.msg\n', '\tResearchP12.msg\n\tVehicleAirData.msg\n')
    # Append at the end, outside the contiguous P11 insertion.
    yaml = 'src/modules/mc_raptor/module.yaml'
    p = PX / yaml
    if 'MC_RAPTOR_P12:' not in p.read_text():
        with p.open('a') as f:
            f.write('''
    - group: Handover P12 Experiment
      definitions:
        MC_RAPTOR_P12:
            description:
                short: SITL P12 observation and experiment enable
            type: boolean
            default: false
        MC_RAPTOR_P12PH:
            description:
                short: P12 delivery gate 0 original 1 native 2 intermediate
            type: int32
            default: 0
            min: 0
            max: 2
        MC_RAPTOR_P12R:
            description:
                short: P12 repair only after activation and external read
            type: boolean
            default: false
''')
    h = 'src/modules/mc_raptor/mc_raptor.hpp'
    edit(h, '\tvoid Run() override;', '''#ifdef __PX4_POSIX
    bool _p12_enabled{false}, _p12_seen{false}, _p12_repair{false};
    research_p12_s _p12{};
    uORB::Publication<research_p12_s> _p12_pub{ORB_ID(research_p12)};
#endif
\tvoid Run() override;''')
    edit(h, '#include <uORB/topics/raptor_input.h>', '#ifdef __PX4_POSIX\n#include <uORB/topics/research_p12.h>\n#include <lib/handover_research/P12Controls.hpp>\n#endif\n#include <uORB/topics/raptor_input.h>')
    c = 'src/modules/mc_raptor/mc_raptor.cpp'
    # Development v1 put advertisement inside an older contiguous injection.
    # Migrate only that exact fragment; retain the complete earlier block.
    file=PX/c
    old_ad='#ifdef __PX4_POSIX\n    _p12_pub.advertise();\n#endif\n\t_tune_control_pub.advertise();'
    if old_ad in file.read_text():file.write_text(file.read_text().replace(old_ad,'\t_tune_control_pub.advertise();',1))
    edit(c, 'bool Raptor::init()\n{', 'bool Raptor::init()\n{\n#ifdef __PX4_POSIX\n    _p12_pub.advertise();\n#endif')
    edit(c, '\ttrajectory_setpoint_s temp_trajectory_setpoint;', '''#ifdef __PX4_POSIX
    static const param_t p12_on=param_find("MC_RAPTOR_P12"),p12_ph=param_find("MC_RAPTOR_P12PH"),p12_r=param_find("MC_RAPTOR_P12R");
    int32_t p12_enable=0,p12_phase=0,p12_repair=0;
    param_get(p12_on,&p12_enable);param_get(p12_ph,&p12_phase);param_get(p12_r,&p12_repair);
    _p12_enabled=p12_enable && _p11_enabled;
    _p12_repair=p12_repair!=0;
    if (!previous_active && next_active) _p12_seen=false;
    _p12=research_p12_s{};
    if (_p12_enabled) {
        _p12.timestamp=current_time;_p12.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
        _p12.active=next_active;_p12.requested_phase=p12_phase;_p12.repair_requested=_p12_repair;
        _p12.lp_updated=status.subscription_update_local_position;_p12.attitude_updated=status.subscription_update_attitude;
        _p12.last_gru_sample_before=_last_gru_sample;
        _p12.call_index_before=executor.executor.intermediate_step;
        _p12.history_count_before=executor.steps_since_original_control_step;
        for (TI i=0;i<4;i++) _p12.history_before[i]=executor.action_history[0][i];
        _p12.predicted_commit=!executor.executor.last_control_timestamp_original_set ||
            (executor.executor.force_sync_native!=0 && executor.executor.intermediate_step%executor.executor.force_sync_native==0);
        _p12.gate_pending=_trajectory_setpoint_sub.updated();
        _p12.gate_permit=handover_research::p12_delivery_allowed(p12_phase,next_active,
            executor.executor.last_control_timestamp_original_set,executor.executor.intermediate_step,executor.executor.force_sync_native);
        struct timespec p12_begin{};clock_gettime(CLOCK_MONOTONIC,&p12_begin);
        _p12.read_begin_wall_ns=static_cast<uint64_t>(p12_begin.tv_sec)*1000000000ULL+static_cast<uint64_t>(p12_begin.tv_nsec);
    }
#endif
\ttrajectory_setpoint_s temp_trajectory_setpoint;''')
    old = '\tstatus.subscription_update_trajectory_setpoint = use_external_reference && _trajectory_setpoint_sub.update(&temp_trajectory_setpoint);'
    edit(c, old, '''#ifdef __PX4_POSIX
    // P12 native-state delivery gate: do not consume on the other phase.
    // The uORB latest value remains pending; timestamps and the strict guard are untouched.
    status.subscription_update_trajectory_setpoint = use_external_reference &&
        (!_p12_enabled || _p12.gate_permit) && _trajectory_setpoint_sub.update(&temp_trajectory_setpoint);
    if (_p12_enabled) {
        struct timespec p12_end{};clock_gettime(CLOCK_MONOTONIC,&p12_end);
        _p12.read_end_wall_ns=static_cast<uint64_t>(p12_end.tv_sec)*1000000000ULL+static_cast<uint64_t>(p12_end.tv_nsec);
    }
#else
''' + old + '\n#endif')
    # This anchor follows all P11 inserted code; no earlier insertion is split.
    edit(c, '\tif (!this->timestamp_last_policy_frequency_check_set', '''#ifdef __PX4_POSIX
    if (_p12_enabled) {
        if (_p11.external_valid && next_active) _p12_seen=true;
        _p12.external_seen=_p12_seen;
        _p12.actual_commit=timing.gru_committed;
        _p12.call_index_after=executor.executor.intermediate_step;
        _p12.history_count_after=executor.steps_since_original_control_step;
        for (TI i=0;i<4;i++) _p12.history_after[i]=executor.action_history[0][i];
        _p12_pub.publish(_p12);
    }
    struct timespec p12_cycle_end{};clock_gettime(CLOCK_MONOTONIC,&p12_cycle_end);
    // P12 full-cycle envelope includes its own publication and parameter reads.
    timing.p11_cycle_wall_end_ns=static_cast<uint64_t>(p12_cycle_end.tv_sec)*1000000000ULL+static_cast<uint64_t>(p12_cycle_end.tv_nsec);
#endif
\tif (!this->timestamp_last_policy_frequency_check_set''')
    # The original injected target function receives an explicit independent overlay.
    edit(c, '    param_get(rtgt,&mode);param_get(rtdec,&decel);', '''    param_get(rtgt,&mode);param_get(rtdec,&decel);
    // P12_CAPTURE_OVERLAY: no reset, no hidden/history write, no live parameter change.
    if (_p12_enabled) mode=handover_research::p12_capture_mode(_p12_repair,activation,active,_p12_seen);''')


if __name__ == '__main__':
    apply()
