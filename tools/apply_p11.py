#!/usr/bin/env python3
"""Read-only P11 hooks, only at original-source anchors outside prior inserted blocks.

Called after apply_research. MC_RAPTOR_P11 defaults off; RSH must also be on.
No policy, reset, target, executor, actuator, or guard equations are changed.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PX = ROOT / 'uav_lab/.local/checkouts/px4-raptor'


def edit(name, old, new):
    path = PX / name
    s = path.read_text()
    if new in s:
        assert s.count(new) == 1, name
        return
    if s.count(old) != 1:
        raise RuntimeError('P11 unique anchor missing: ' + name + ': ' + old[:70])
    path.write_text(s.replace(old, new, 1))


def apply():
    edit('msg/CMakeLists.txt', '\tVehicleAcceleration.msg\n', '\tResearchP11.msg\n\tVehicleAcceleration.msg\n')
    edit('src/modules/mc_raptor/module.yaml', 'parameters:\n', '''parameters:
    - group: Handover Research Observation
      definitions:
        MC_RAPTOR_P11:
            description:
                short: SITL read-only P11 full inference observation
            type: boolean
            default: false
''')
    h = 'src/modules/mc_raptor/mc_raptor.hpp'
    edit(h, '#include <uORB/topics/raptor_input.h>', '#include <uORB/topics/raptor_input.h>\n#ifdef __PX4_POSIX\n#include <uORB/topics/research_p11.h>\n#endif')
    edit(h, '\tbool previous_active = false;', '''#ifdef __PX4_POSIX
    bool _p11_enabled{false};
    uint64_t _p11_sequence{0};
    uint64_t _p11_pre_ns{0};
    research_p11_s _p11{};
    uORB::Publication<research_p11_s> _p11_pub{ORB_ID(research_p11)};
#endif
\tbool previous_active = false;''')
    c = 'src/modules/mc_raptor/mc_raptor.cpp'
    edit(c, '\t_actuator_motors_pub.advertise();', '#ifdef __PX4_POSIX\n    _p11_pub.advertise();\n#endif\n\t_actuator_motors_pub.advertise();')
    edit(c, '\tstatus.substep = 0;', '''\tstatus.substep = 0;
#ifdef __PX4_POSIX
    struct timespec p11_cycle_begin{};clock_gettime(CLOCK_MONOTONIC,&p11_cycle_begin);
    const uint64_t p11_cycle_start=static_cast<uint64_t>(p11_cycle_begin.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_cycle_begin.tv_nsec);
    static const param_t p11_param=param_find("MC_RAPTOR_P11"), p11_rsh=param_find("MC_RAPTOR_RSH");
    int32_t p11_enable=0,p11_research=0;
    param_get(p11_param,&p11_enable);param_get(p11_rsh,&p11_research);
    _p11_enabled=p11_enable && p11_research;
    if (_p11_enabled) {
        _p11=research_p11_s{};_p11.timestamp=current_time;_p11.sequence=++_p11_sequence;
        struct timespec p11_wall{};clock_gettime(CLOCK_MONOTONIC,&p11_wall);
        _p11.run_wall_ns=static_cast<uint64_t>(p11_wall.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_wall.tv_nsec);
    }
#endif''')
    # Before the original input early exits. This does not call subscription.update again.
    edit(c, '\tconstexpr bool PUBLISH_NON_COMPLETE_STATUS = true;', '''#ifdef __PX4_POSIX
    if (_p11_enabled) {
        _p11.subscription_updated=status.subscription_update_trajectory_setpoint;
        _p11.external_valid=_p11.subscription_updated && status.timestamp_last_trajectory_setpoint==current_time;
        _p11.external_timestamp=_p11.subscription_updated?temp_trajectory_setpoint.timestamp:0;
        _p11.last_valid_read_us=timestamp_last_trajectory_setpoint_set?timestamp_last_trajectory_setpoint:0;
        _p11.invalid_total=trajectory_setpoint_invalid_count;
        for (TI i=0;i<3;i++) {
            _p11.external_position[i]=_p11.external_valid?temp_trajectory_setpoint.position[i]:NAN;
            _p11.external_velocity[i]=_p11.external_valid?temp_trajectory_setpoint.velocity[i]:NAN;
        }
        _p11.external_yaw=_p11.external_valid?temp_trajectory_setpoint.yaw:NAN;
        struct timespec p11_read{};clock_gettime(CLOCK_MONOTONIC,&p11_read);
        _p11.read_wall_ns=static_cast<uint64_t>(p11_read.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_read.tv_nsec);
    }
#endif
\tconstexpr bool PUBLISH_NON_COMPLETE_STATUS = true;''')
    # Inside observe, after the P7 RAII view applied the actual virtual target.
    edit(c, '\tT Rt_inv[9];', '''#ifdef __PX4_POSIX
    if (_p11_enabled) {
        struct timespec p11_pre_begin{};clock_gettime(CLOCK_MONOTONIC,&p11_pre_begin);
        _p11.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
        _p11.local_position_sample=_vehicle_local_position.timestamp_sample;
        _p11.attitude_sample=_vehicle_attitude.timestamp_sample;
        _p11.stale=previous_trajectory_setpoint_stale;
        _p11.recovery_active=_research_recovery.active;
        _p11.target_yaw=_trajectory_setpoint.yaw;
        float p11_memory[32]{};research_get(p11_memory);
        for (TI i=0;i<16;i++) _p11.gru_before[i]=p11_memory[i];
        for (TI i=0;i<4;i++) {_p11.attitude[i]=_vehicle_attitude.q[i];_p11.previous_action_before[i]=previous_action[i];}
        for (TI i=0;i<3;i++) {
            _p11.position[i]=position[i];_p11.velocity[i]=linear_velocity[i];
            _p11.angular_velocity[i]=_vehicle_angular_velocity.xyz[i];
            _p11.network_target_position[i]=_trajectory_setpoint.position[i];
            _p11.network_target_velocity[i]=_trajectory_setpoint.velocity[i];
        }
        struct timespec p11_pre_end{};clock_gettime(CLOCK_MONOTONIC,&p11_pre_end);
        _p11_pre_ns=static_cast<uint64_t>(p11_pre_end.tv_sec-p11_pre_begin.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_pre_end.tv_nsec-p11_pre_begin.tv_nsec);
    }
#endif
\tT Rt_inv[9];''')
    edit(c, '\tprevious_active = next_active;', '''#ifdef __PX4_POSIX
    struct timespec p11_post_begin{};clock_gettime(CLOCK_MONOTONIC,&p11_post_begin);
    timing.p11_cycle_wall_start_ns=p11_cycle_start;
    if (_p11_enabled) {
        _p11.active=next_active;_p11.activation=!previous_active && next_active;
        _p11.native_step=timing.native_step;_p11.gru_committed=timing.gru_committed;
        float p11_after[32]{};research_get(p11_after);
        for (TI i=0;i<16;i++) _p11.gru_after[i]=p11_after[i];
        for (TI i=0;i<4;i++) {_p11.previous_action_after[i]=previous_action[i];_p11.executor_action[i]=action.action[i];}
        for (TI i=0;i<22;i++) _p11.policy_input[i]=rlt::get(device,executor.input,0,i);
        struct timespec p11_pub_begin{},p11_pub_end{};clock_gettime(CLOCK_MONOTONIC,&p11_pub_begin);
        _p11_pub.publish(_p11);
        clock_gettime(CLOCK_MONOTONIC,&p11_pub_end);
        timing.p11_setup_ns=_p11.run_wall_ns-p11_cycle_start;
        timing.p11_pre_ns=_p11_pre_ns;
        timing.p11_post_copy_ns=static_cast<uint64_t>(p11_pub_begin.tv_sec-p11_post_begin.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_pub_begin.tv_nsec-p11_post_begin.tv_nsec);
        timing.p11_publication_ns=static_cast<uint64_t>(p11_pub_end.tv_sec-p11_pub_begin.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_pub_end.tv_nsec-p11_pub_begin.tv_nsec);
    }
    struct timespec p11_cycle_end{};clock_gettime(CLOCK_MONOTONIC,&p11_cycle_end);
    timing.p11_cycle_wall_end_ns=static_cast<uint64_t>(p11_cycle_end.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_cycle_end.tv_nsec);
#endif
\tprevious_active = next_active;''')


if __name__ == '__main__':
    apply()
