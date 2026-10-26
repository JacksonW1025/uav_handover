#!/usr/bin/env python3
"""P12b passive pre-read state; independent additive overlay after P12c."""
from apply_p12 import PX,ROOT,edit
import shutil

def apply():
 shutil.copy2(ROOT/'research/state/ResearchP12b.msg',PX/'msg/ResearchP12b.msg')
 shutil.copy2(ROOT/'research/state/P12bTrace.hpp',PX/'src/lib/handover_research/P12bTrace.hpp')
 edit('msg/CMakeLists.txt','\tVehicleAirData.msg\n','\tVehicleAirData.msg\n\tResearchP12b.msg\n')
 h='src/modules/mc_raptor/mc_raptor.hpp';c='src/modules/mc_raptor/mc_raptor.cpp'
 edit(h,'\tvoid Run() override;','''\tvoid Run() override;
#ifdef __PX4_POSIX
    bool _p12b_enabled{false};
    research_p12b_s _p12b{};
    uORB::Publication<research_p12b_s> _p12b_pub{ORB_ID(research_p12b)};
#endif''')
 # Insert after the earlier complete include, preserving the old insertion byte substring.
 edit(h,'#include <uORB/topics/tune_control.h>','#include <uORB/topics/tune_control.h>\n#ifdef __PX4_POSIX\n#include <uORB/topics/research_p12b.h>\n#include <lib/handover_research/P12bTrace.hpp>\n#endif')
 p=PX/'src/modules/mc_raptor/module.yaml'
 if 'MC_RAPTOR_P12B:' not in p.read_text():
  with p.open('a') as f:f.write('''
    - group: Handover P12b Observation
      definitions:
        MC_RAPTOR_P12B:
            description:
                short: P12b passive pre-read contract observation
            type: boolean
            default: false
''')
 # Append after the complete P12 prefix, never splitting its inserted text.
 edit(c,'\ttrajectory_setpoint_s temp_trajectory_setpoint;','''\ttrajectory_setpoint_s temp_trajectory_setpoint;
#ifdef __PX4_POSIX
    static const param_t p12b_param=param_find("MC_RAPTOR_P12B");
    int32_t p12b_on=0;param_get(p12b_param,&p12b_on);
    _p12b_enabled=p12b_on && _p12_enabled;
    _p12b=research_p12b_s{};
    if (_p12b_enabled) {
        _p12b.timestamp=current_time;_p12b.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
        _p12b.active=next_active;_p12b.activation=!previous_active && next_active;
        _p12b.timing_initialized_pre=executor.executor.last_control_timestamp_original_set;
        _p12b.force_sync_initialized_pre=executor.executor.force_sync_native_initialized;
        _p12b.call_index_pre=executor.executor.intermediate_step;
        _p12b.force_sync_pre=executor.executor.force_sync_native;
        _p12b.control_time_pre=executor.executor.last_control_timestamp;
        _p12b.original_control_time_pre=executor.executor.last_control_timestamp_original;
        _p12b.last_valid_read_pre=timestamp_last_trajectory_setpoint_set?timestamp_last_trajectory_setpoint:0;
        _p12b.requested_phase=p12_phase;_p12b.gate_pending=_p12.gate_pending;
        _p12b.gate_applicable=next_active && p12_phase!=0 &&
            executor.executor.last_control_timestamp_original_set && executor.executor.force_sync_native!=0;
        _p12b.gate_permit=_p12.gate_permit;_p12b.external_seen_pre=_p12_seen;
        int32_t p12b_ms=-1;param_get(param_find("MC_RAPTOR_P12MS"),&p12b_ms);
        _p12b.repair_not_before_ms=p12b_ms;
        struct timespec p12b_wall{};clock_gettime(CLOCK_MONOTONIC,&p12b_wall);
        _p12b.pre_read_wall_ns=static_cast<uint64_t>(p12b_wall.tv_sec)*1000000000ULL+static_cast<uint64_t>(p12b_wall.tv_nsec);
    }
#endif''')
 # Preserve the EXACT tested source, including the legacy redundant ULog publish.
 # direct-v2 is the single canonical file write; ULog is explicitly noncanonical.
 # Do not silently rebuild an unvalidated cleaned binary after spending prep8.
 # Publish every read decision, including calls later rejected by SampleClock.
 # This anchor is outside the complete P11/P12 insertion substrings.
 edit(c,'\tconstexpr bool PUBLISH_NON_COMPLETE_STATUS = true;','\tconstexpr bool PUBLISH_NON_COMPLETE_STATUS = true;' + '''
#ifdef __PX4_POSIX
    if (_p12b_enabled) {
        _p12b.read_updated=status.subscription_update_trajectory_setpoint;
        _p12b.read_valid=_p12b.read_updated &&
            PX4_ISFINITE(temp_trajectory_setpoint.position[0]) && PX4_ISFINITE(temp_trajectory_setpoint.position[1]) &&
            PX4_ISFINITE(temp_trajectory_setpoint.position[2]) && PX4_ISFINITE(temp_trajectory_setpoint.velocity[0]) &&
            PX4_ISFINITE(temp_trajectory_setpoint.velocity[1]) && PX4_ISFINITE(temp_trajectory_setpoint.velocity[2]) &&
            PX4_ISFINITE(temp_trajectory_setpoint.yaw) && PX4_ISFINITE(temp_trajectory_setpoint.yawspeed);
        _p12b.last_valid_read_post=timestamp_last_trajectory_setpoint_set?timestamp_last_trajectory_setpoint:0;
        _p12b.external_timestamp=_p11.external_timestamp;
        _p12b.invalid_total=trajectory_setpoint_invalid_count;
        _p12b_pub.publish(_p12b);
        handover_research::p12b_trace(_p12b);
    }
#endif\n#ifdef __PX4_POSIX
    if (_p12b_enabled) {
        _p12b.read_updated=status.subscription_update_trajectory_setpoint;
        _p12b.read_valid=_p11.external_valid;
        _p12b.last_valid_read_post=timestamp_last_trajectory_setpoint_set?timestamp_last_trajectory_setpoint:0;
        _p12b.external_timestamp=_p11.external_timestamp;
        _p12b.invalid_total=trajectory_setpoint_invalid_count;
        _p12b_pub.publish(_p12b);
    }
#endif''')
if __name__=='__main__':apply()
