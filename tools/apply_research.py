#!/usr/bin/env python3
"""Apply narrow, idempotent SITL research edits to the preserved RAPTOR checkout."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
PX=ROOT/'uav_lab/.local/checkouts/px4-raptor'
def edit(name,old,new):
 p=PX/name;s=p.read_text()
 # P12 adds one explicit mode selection inside this formerly contiguous function.
 # Its unique marker prevents reinsertion of the complete P4/P5 function.
 if old=='int Raptor::task_spawn(int argc, char *argv[])\n{' and 'void Raptor::research_target_capture' in new and 'P12_CAPTURE_OVERLAY' in s:
  assert s.count('void Raptor::research_target_capture(')==1
  return
 if new in s:return
 if old not in s:raise RuntimeError('expected source anchor missing: '+name)
 p.write_text(s.replace(old,new,1))

def migrate(name,old,new):
 # Upgrade text inserted by an earlier version of an edit; the edit itself keeps its own anchor.
 p=PX/name;s=p.read_text()
 if new not in s and old in s:p.write_text(s.replace(old,new,1))

def main():
 dest=PX/'src/lib/handover_research';dest.mkdir(exist_ok=True)
 for p in (ROOT/'research/state').glob('*.hpp'):shutil.copy2(p,dest/p.name)
 for p in (ROOT/'research/state').glob('*.msg'):shutil.copy2(p,PX/'msg'/p.name)
 edit('msg/CMakeLists.txt','\tRouteObservability.msg','\tResearchStateRequest.msg\n\tResearchStateResponse.msg\n\tResearchTiming.msg\n\tResearchAngularVelocity.msg\n\tResearchOutput.msg\n\tResearchActuator.msg\n\tRouteObservability.msg')
 if 'MC_RAPTOR_RSH:' not in (PX/'src/modules/mc_raptor/module.yaml').read_text():edit('src/modules/mc_raptor/module.yaml','parameters:\n','parameters:\n    - group: Handover Research\n      definitions:\n        MC_RAPTOR_RSH:\n            description:\n                short: Enable SITL controller state research interface\n            type: boolean\n            default: false\n')
 # Local state operations are excluded from hardware builds.
 for name,member in [('mc_rate_control/MulticopterRateControl.hpp','handover_research::StateBridge _research_state{2, 3, 0.3f};'),('mc_pos_control/MulticopterPositionControl.hpp','handover_research::StateBridge _research_state{3, 3, 4.f};'),('mc_raptor/mc_raptor.hpp','handover_research::StateBridge _research_state{1, 26, 100.f};\n\tvoid research_get(float *values);\n\tvoid research_set(const float *values, bool reset_state);\n    handover_research::SampleClock _sample_clock{};\n    unsigned _sample_generation{0};\n    uint64_t _sample_missed{0}, _native_total{0}, _gru_total{0}, _last_gru_sample{0};')]:
  file='src/modules/'+name
  edit(file,'#pragma once','#pragma once\n#ifdef __PX4_POSIX\n#include <lib/handover_research/StateBridge.hpp>\n#endif')
  edit(file,'private:\n','private:\n#ifdef __PX4_POSIX\n\t'+member+'\n#endif\n')
 # Minimal explicit getters/setters: no change to ordinary control update equations.
 edit('src/lib/rate_control/rate_control.hpp','\tvoid resetIntegral() { _rate_int.zero(); }','\tvoid resetIntegral() { _rate_int.zero(); }\n#ifdef __PX4_POSIX\n\tmatrix::Vector3f researchGet() const { return _rate_int; }\n\tmatrix::Vector3f researchLimit() const { return _lim_int; }\n\tvoid researchSet(const matrix::Vector3f &v) { _rate_int = v; }\n#endif')
 edit('src/modules/mc_pos_control/PositionControl/PositionControl.hpp','\tvoid resetIntegral() { _vel_int.setZero(); }','\tvoid resetIntegral() { _vel_int.setZero(); }\n#ifdef __PX4_POSIX\n\tmatrix::Vector3f researchGet() const { return _vel_int; }\n\tvoid researchSet(const matrix::Vector3f &v) { _vel_int = v; }\n#endif')
 rate='src/modules/mc_rate_control/MulticopterRateControl.cpp'
 edit(rate,'\t\t_vehicle_status_sub.update(&_vehicle_status);','''\t\t_vehicle_status_sub.update(&_vehicle_status);
#ifdef __PX4_POSIX
        _rate_control.researchLimit().copyTo(_research_state._bounds);
        _research_state.update(_vehicle_control_mode.flag_armed && _vehicle_control_mode.flag_control_rates_enabled,
            [this](float *v) { _rate_control.researchGet().copyTo(v); },
            [this](const float *v, bool) { _rate_control.researchSet(Vector3f(v)); });
#endif''')
 edit(rate,'\tperf_end(_loop_perf);','''#ifdef __PX4_POSIX
    if (_research_state.engine.holding) _rate_control.researchSet(Vector3f(_research_state.engine.held));
#endif
\tperf_end(_loop_perf);''')
 pos='src/modules/mc_pos_control/MulticopterPositionControl.cpp'
 edit(pos,'\t\t_vehicle_land_detected_sub.update(&_vehicle_land_detected);','''\t\t_vehicle_land_detected_sub.update(&_vehicle_land_detected);
#ifdef __PX4_POSIX
        _research_state.update(_vehicle_control_mode.flag_armed && _vehicle_control_mode.flag_multicopter_position_control_enabled,
            [this](float *v) { _control.researchGet().copyTo(v); },
            [this](const float *v, bool) { _control.researchSet(Vector3f(v)); });
#endif''')
 edit(pos,'\tperf_end(_cycle_perf);','''#ifdef __PX4_POSIX
    if (_research_state.engine.holding) _control.researchSet(Vector3f(_research_state.engine.held));
#endif
\tperf_end(_cycle_perf);''')
 rap='src/modules/mc_raptor/mc_raptor.cpp'
 edit(rap,'#include <sys/stat.h>','''#include <sys/stat.h>
#ifdef __PX4_POSIX
#include <lib/handover_research/StateCli.hpp>
#include <uORB/topics/research_timing.h>
#include <time.h>
void Raptor::research_get(float *v) {
    auto &hidden = executor.executor.policy_state.content_state.next_content_state.state.state;
    static_assert(decltype(hidden)::SPEC::SIZE == 16, "Frozen checkpoint GRU dimension changed");
    for (TI i=0;i<16;i++) v[i]=rlt::get(device,hidden,0,i);
    for (TI i=0;i<4;i++) v[16+i]=previous_action[i];
    for (TI i=0;i<3;i++) {v[20+i]=_trajectory_setpoint.position[i];v[23+i]=_trajectory_setpoint.velocity[i];}
}
void Raptor::research_set(const float *v, bool reset_state) {
    if(reset_state) this->reset();
    auto &hidden = executor.executor.policy_state.content_state.next_content_state.state.state;
    auto &temp = executor.executor.policy_state_temp.content_state.next_content_state.state.state;
    for (TI i=0;i<16;i++) {rlt::set(device,hidden,v[i],0,i);rlt::set(device,temp,v[i],0,i);}
    for (TI i=0;i<4;i++) previous_action[i]=v[16+i];
    for (TI i=0;i<3;i++) {_trajectory_setpoint.position[i]=v[20+i];_trajectory_setpoint.velocity[i]=v[23+i];}
}
#endif'''.replace('decltype(hidden)::SPEC::SIZE','std::remove_reference_t<decltype(hidden)>::SPEC::SIZE'))
 edit(rap,'\tobserve(observation);','''#ifdef __PX4_POSIX
    for (TI i=0;i<16;i++) _research_state._bounds[i]=1.f;
    for (TI i=16;i<20;i++) _research_state._bounds[i]=1.f;
    for (TI i=23;i<26;i++) _research_state._bounds[i]=10.f;
    _research_state.update(next_active,
        [this](float *v) { research_get(v); },
        [this](const float *v, bool reset_state) { research_set(v,reset_state); });
    struct timespec wall_start{}, wall_end{};
    clock_gettime(CLOCK_MONOTONIC,&wall_start);
#endif
\tobserve(observation);''')
 edit(rap,'\tauto executor_status = rl_tools::control(device, executor, nanoseconds, policy, observation, action, rng);','''\tauto executor_status = rl_tools::control(device, executor, nanoseconds, policy, observation, action, rng);
#ifdef __PX4_POSIX
    clock_gettime(CLOCK_MONOTONIC,&wall_end);
    research_timing_s timing{};
    timing.timestamp=current_time;
    timing.schema_version=2;
    timing.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    timing.local_position_sample=_vehicle_local_position.timestamp_sample;
    timing.attitude_sample=_vehicle_attitude.timestamp_sample;
    timing.control_start_wall_ns=static_cast<uint64_t>(wall_start.tv_sec)*1000000000ULL+wall_start.tv_nsec;
    timing.control_end_wall_ns=static_cast<uint64_t>(wall_end.tv_sec)*1000000000ULL+wall_end.tv_nsec;
    timing.accepted_total=_sample_clock.accepted;
    timing.duplicate_total=_sample_clock.duplicate;
    timing.regressed_total=_sample_clock.regressed;
    timing.source_generation=_sample_generation;
    timing.source_missed_total=_sample_missed;
    timing.input_dt_us=_sample_clock.dt;
    timing.executor_dt_us=executor_dt_us;
    timing.native_dt_us=native_dt_us;
    timing.executor_called=true;
    timing.native_step=executor_status.source==decltype(executor_status.source)::CONTROL && executor_status.step_type==decltype(executor_status.step_type)::NATIVE;
    timing.gru_committed=timing.native_step && !_research_state.engine.holding;
    if(timing.native_step)++_native_total;
    if(timing.gru_committed){++_gru_total;_last_gru_sample=timing.timestamp_sample;}
    timing.native_total=_native_total;timing.gru_commit_total=_gru_total;timing.last_gru_sample=_last_gru_sample;
    timing.timing_jitter_ok=executor_status.timing_jitter.OK;
    timing.timing_bias_ok=executor_status.timing_bias.OK;
    timing.jitter_ratio=executor_status.timing_jitter.MAGNITUDE;
    timing.bias_ratio=executor_status.timing_bias.MAGNITUDE;
    timing.timestamp_invalid=executor_status.TIMESTAMP_INVALID;
    timing.timestamp_order_invalid=executor_status.LAST_CONTROL_TIMESTAMP_GREATER_THAN_LAST_OBSERVATION_TIMESTAMP;
    timing.inference_duration_us=(wall_end.tv_sec-wall_start.tv_sec)*1000000+(wall_end.tv_nsec-wall_start.tv_nsec)/1000;
    timing.active=next_active;
    timing.executor_ok=executor_status.OK;
    timing.control_step=executor_status.source==decltype(executor_status.source)::CONTROL;
    timing.mode_id=ext_component_mode_id;
    timing.output_finite=true;
    if(timing.control_step)for(TI i=0;i<4;i++) {timing.action[i]=action.action[i];timing.output_finite &= PX4_ISFINITE(action.action[i]);}
    handover_research::TimingRecord timing_record(timing);
    if(_research_state.engine.holding)research_set(_research_state.engine.held,false);
    if(timing.control_step && (!timing.output_finite || executor_status.TIMESTAMP_INVALID || executor_status.LAST_CONTROL_TIMESTAMP_GREATER_THAN_LAST_OBSERVATION_TIMESTAMP)) {
        PX4_ERR("Research guard: invalid inference; actuator publication withheld");
        can_arm=false;updateArmingCheckReply();return;
    }
#endif''')
 edit(rap,'\t\t\tthis->previous_action[action_i] = value;','''#ifdef __PX4_POSIX
            if(!_research_state.engine.holding) {
                this->previous_action[action_i] = value;
            }
#else
            this->previous_action[action_i] = value;
#endif''')
 edit(rap,'\tif (argc >= 2 && strcmp(argv[0], "intref") == 0) {','''#ifdef __PX4_POSIX
    if(argc>=1 && strcmp(argv[0],"state")==0)return handover_research::state_command(argc,argv);
#endif
\tif (argc >= 2 && strcmp(argv[0], "intref") == 0) {''')
if __name__=='__main__':main()
# Exact actuator ownership evidence supplements the preserved, throttled route events.
for module in ['mc_raptor/mc_raptor.cpp','control_allocator/ControlAllocator.cpp']:
 file='src/modules/'+module
 p=PX/file
 if 'research_actuator.h' not in p.read_text():
  p.write_text('#ifdef __PX4_POSIX\n#include <uORB/topics/research_actuator.h>\n#endif\n'+p.read_text())
 owner=1 if module.startswith('mc_raptor') else 2
 anchor='\t\t_actuator_motors_pub.publish(actuator_motors);' if owner==1 else '\t_actuator_motors_pub.publish(actuator_motors);'
 if f'ownership.owner={owner};' not in p.read_text():edit(file,anchor,anchor+f'''
#ifdef __PX4_POSIX
    research_actuator_s ownership{{}};
    ownership.timestamp=hrt_absolute_time();ownership.actuator_timestamp=actuator_motors.timestamp;ownership.owner={owner};
    for(unsigned i=0;i<4;i++)ownership.control[i]=actuator_motors.control[i];
    static uORB::Publication<research_actuator_s> ownership_pub{{ORB_ID(research_actuator)}};
    ownership_pub.publish(ownership);
#endif''')
RINI_P1='''        MC_RAPTOR_RINI:
            description:
                short: SITL research preserve memory on mode entry
            type: boolean
            default: false
'''
RINI_P2='''        MC_RAPTOR_RINI:
            description:
                short: SITL research mode-entry memory treatment
                long: 0 original reset, 1 preserve shadow memory, 2 GRU reset with classic previous action, 3 teacher-forced GRU, 4 teacher-forced GRU with classic previous action, 5 staged memory
            type: int32
            min: 0
            max: 5
            default: 0
'''
RINI_P3=RINI_P2.replace(', 5 staged memory\n',', 5 staged memory, 6 memory held unchanged since the most recent exit\n').replace('            max: 5\n','            max: 6\n')
# P2 widened the P1 boolean to modes; 0/1 keep their meaning. P3 adds mode 6. Migrate checkouts prepared earlier.
migrate('src/modules/mc_raptor/module.yaml',RINI_P1,RINI_P2)
migrate('src/modules/mc_raptor/module.yaml',RINI_P2,RINI_P3)
if 'MC_RAPTOR_RINI:' not in (PX/'src/modules/mc_raptor/module.yaml').read_text():edit('src/modules/mc_raptor/module.yaml','    - group: Handover Research\n','''    - group: Handover Research
      definitions:
'''+RINI_P3+'''    - group: Handover Research
''')
edit('src/modules/mc_raptor/mc_raptor.hpp','ext_component_mode_id;','ext_component_mode_id = 255;')
edit('src/modules/mc_raptor/mc_raptor.cpp','bool next_active = timestamp_last_vehicle_status_set && _vehicle_status.nav_state == ext_component_mode_id;','bool next_active = flightmode_state == FlightModeState::CONFIGURED && timestamp_last_vehicle_status_set && _vehicle_status.nav_state == ext_component_mode_id;')
ENTRY_P1='''#ifdef __PX4_POSIX
        int32_t preserve=0, enabled=0;
        param_get(param_find("MC_RAPTOR_RINI"),&preserve);
        param_get(param_find("MC_RAPTOR_RSH"),&enabled);
        float memory[32]{};
        if(preserve && enabled)research_get(memory);
#endif
        this->reset();
#ifdef __PX4_POSIX
        if(preserve && enabled)research_set(memory,false);
        PX4_INFO("Research mode-entry memory: %s",preserve && enabled?"preserved; timing rebased":"reset");
#endif
\t\tPX4_INFO("Resetting Inference Executor (Recurrent State)");'''
# Modes 0 and 1 keep the P1 statements; modes 2..5 (P2) write only GRU and previous action after the reset.
ENTRY_P2='''#ifdef __PX4_POSIX
        int32_t preserve=0, enabled=0;
        param_get(param_find("MC_RAPTOR_RINI"),&preserve);
        param_get(param_find("MC_RAPTOR_RSH"),&enabled);
        float memory[32]{};
        if(preserve==1 && enabled)research_get(memory);
        const int32_t entry_mode=enabled?preserve:0;
        float entry_before[32]{};research_get(entry_before);
        float entry_classic[4]{};
        const bool entry_classic_valid=handover_research::needs_classic_action(entry_mode) && research_classic_action(entry_classic);
#endif
        this->reset();
#ifdef __PX4_POSIX
        if(preserve==1 && enabled)research_set(memory,false);
        PX4_INFO("Research mode-entry memory: %s",preserve==1 && enabled?"preserved; timing rebased":"reset");
        research_entry(entry_mode,entry_before,entry_classic,entry_classic_valid);
#endif
\t\tPX4_INFO("Resetting Inference Executor (Recurrent State)");'''
migrate('src/modules/mc_raptor/mc_raptor.cpp',ENTRY_P1,ENTRY_P2)
edit('src/modules/mc_raptor/mc_raptor.cpp','''\t\tthis->reset();
\t\tPX4_INFO("Resetting Inference Executor (Recurrent State)");''',ENTRY_P2)
# Export the existing matching RAPTOR diagnostics; experimental state payloads stay local uORB/ULog.
dds=PX/'src/modules/uxrce_dds_client/dds_topics.yaml'
if '/fmu/out/raptor_status' not in dds.read_text():
 edit('src/modules/uxrce_dds_client/dds_topics.yaml','publications:\n','''publications:
  - topic: /fmu/out/raptor_status
    type: px4_msgs::msg::RaptorStatus
  - topic: /fmu/out/raptor_input
    type: px4_msgs::msg::RaptorInput
''')

# Prevent a cached allocation-enabled flag from briefly publishing over RAPTOR.
for module in ['mc_raptor/mc_raptor.cpp','control_allocator/ControlAllocator.cpp']:
 edit('src/modules/'+module,'#include <uORB/topics/research_actuator.h>',
      '#include <uORB/topics/research_actuator.h>\n#include <lib/handover_research/ActuatorGate.hpp>')
edit('src/modules/control_allocator/ControlAllocator.cpp',
     'ControlAllocator::publish_actuator_controls()\n{',
     '''ControlAllocator::publish_actuator_controls()
{
#ifdef __PX4_POSIX
    handover_research::ActuatorGate publication_gate(false);
    if (!publication_gate.allowed()) return;
#endif''')
edit('src/modules/mc_raptor/mc_raptor.cpp','\tif (status.active) {\n\t\t_actuator_motors_pub.publish(actuator_motors);',
     '''\tif (status.active) {
#ifdef __PX4_POSIX
        handover_research::ActuatorGate publication_gate(true);
        if (publication_gate.allowed()) {
#endif
\t\t_actuator_motors_pub.publish(actuator_motors);''')
edit('src/modules/mc_raptor/mc_raptor.cpp','    ownership_pub.publish(ownership);\n#endif',
     '    ownership_pub.publish(ownership);\n        } // publication_gate.allowed()\n#endif')

# P0: use observation sample time, not asynchronously synchronized simulator now.
edit('src/modules/mc_raptor/mc_raptor.hpp',
     '\tvoid research_set(const float *values, bool reset_state);',
     '''\tvoid research_set(const float *values, bool reset_state);
    handover_research::SampleClock _sample_clock{};
    unsigned _sample_generation{0};
    uint64_t _sample_missed{0}, _native_total{0}, _gru_total{0}, _last_gru_sample{0};''')
edit('src/modules/mc_raptor/mc_raptor.cpp',
     '#ifdef __PX4_POSIX\n    for (TI i=0;i<16;i++) _research_state._bounds[i]=1.f;',
     '''#ifdef __PX4_POSIX
    const auto generation=_vehicle_angular_velocity_sub.get_last_generation();
    if(_sample_generation && generation-_sample_generation>1)_sample_missed+=generation-_sample_generation-1;
    _sample_generation=generation;
    const unsigned input_result=_sample_clock.accept(_vehicle_angular_velocity.timestamp_sample);
    if(input_result) {
        research_timing_s skipped{};
        skipped.timestamp=current_time;skipped.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
        skipped.schema_version=2;skipped.active=next_active;skipped.mode_id=ext_component_mode_id;
        skipped.accepted_total=_sample_clock.accepted;skipped.duplicate_total=_sample_clock.duplicate;
        skipped.regressed_total=_sample_clock.regressed;skipped.source_missed_total=_sample_missed;
        skipped.source_generation=generation;skipped.input_result=input_result;
        skipped.native_total=_native_total;skipped.gru_commit_total=_gru_total;skipped.last_gru_sample=_last_gru_sample;
        skipped.executor_ok=true;skipped.output_finite=true;
        handover_research::TimingRecord skipped_record(skipped);
        perf_end(_loop_perf);return;
    }
#endif
#ifdef __PX4_POSIX
    for (TI i=0;i<16;i++) _research_state._bounds[i]=1.f;''')
edit('src/modules/mc_raptor/mc_raptor.cpp',
     '\thrt_abstime nanoseconds = current_time * 1000;',
     '''#ifdef __PX4_POSIX
    const uint32_t executor_dt_us=executor.executor.last_control_timestamp_set ?
        (_vehicle_angular_velocity.timestamp_sample*1000-executor.executor.last_control_timestamp)/1000 : 0;
    const uint32_t native_dt_us=executor.executor.last_control_timestamp_original_set ?
        (_vehicle_angular_velocity.timestamp_sample*1000-executor.executor.last_control_timestamp_original)/1000 : 0;
    hrt_abstime nanoseconds = _vehicle_angular_velocity.timestamp_sample * 1000;
#else
\thrt_abstime nanoseconds = current_time * 1000;
#endif''')

# Gazebo transport callbacks and /clock are asynchronous. Timestamp observations
# from their message header, preserving acquisition time rather than callback time.
edit('src/modules/simulation/gz_bridge/GZBridge.cpp',
     'void GZBridge::imuCallback(const gz::msgs::IMU &msg)\n{\n\tconst uint64_t timestamp = hrt_absolute_time();',
     'void GZBridge::imuCallback(const gz::msgs::IMU &msg)\n{\n\tconst uint64_t timestamp = static_cast<uint64_t>(msg.header().stamp().sec()) * 1000000ULL + msg.header().stamp().nsec() / 1000;')


edit('src/modules/mc_raptor/mc_raptor.cpp',
     '\t\t_actuator_motors_pub.publish(actuator_motors);',
     '\t\t_actuator_motors_pub.publish(actuator_motors);\n#ifdef __PX4_POSIX\n        timing.actuator_published=true;\n        timing.actuator_publish_sim_us=hrt_absolute_time();\n        struct timespec publish_wall{};clock_gettime(CLOCK_MONOTONIC,&publish_wall);\n        timing.actuator_publish_wall_ns=static_cast<uint64_t>(publish_wall.tv_sec)*1000000000ULL+publish_wall.tv_nsec;\n#endif')

# SITL recurrent inference must consume each real gyro observation. The ordinary
# latest-only vehicle_angular_velocity publication and classical controllers keep
# their original scheduling. FIFO hardware paths are deliberately unchanged.
edit('msg/CMakeLists.txt','\tResearchTiming.msg','\tResearchTiming.msg\n\tResearchAngularVelocity.msg')
edit('src/modules/sensors/vehicle_angular_velocity/VehicleAngularVelocity.cpp',
     '#include "VehicleAngularVelocity.hpp"',
     '#include "VehicleAngularVelocity.hpp"\n#ifdef __PX4_POSIX\n#include <uORB/topics/research_angular_velocity.h>\n#endif')
edit('src/modules/sensors/vehicle_angular_velocity/VehicleAngularVelocity.cpp',
     '\t\t\t\t// Publish\n\t\t\t\tif (!_sensor_sub.updated()) {',
     '''#ifdef __PX4_POSIX
                // Preserve each filtered acquisition, including batched source samples.
                static uORB::Publication<research_angular_velocity_s> research_pub{ORB_ID(research_angular_velocity)};
                static uint64_t last_research_sample=0;
                if(sensor_data.timestamp_sample >= last_research_sample + _publish_interval_min_us) {
                    research_angular_velocity_s sample{};
                    sample.timestamp=hrt_absolute_time();sample.timestamp_sample=sensor_data.timestamp_sample;
                    (_calibration.Correct(angular_velocity_uncalibrated)-_bias).copyTo(sample.xyz);
                    (_calibration.rotation()*angular_acceleration_uncalibrated).copyTo(sample.xyz_derivative);
                    research_pub.publish(sample);last_research_sample=sample.timestamp_sample;
                }
#endif
\t\t\t\t// Publish
\t\t\t\tif (!_sensor_sub.updated()) {''')
edit('src/modules/mc_raptor/mc_raptor.hpp',
     '#include <uORB/topics/vehicle_angular_velocity.h>',
     '#include <uORB/topics/vehicle_angular_velocity.h>\n#ifdef __PX4_POSIX\n#include <uORB/topics/research_angular_velocity.h>\n#endif')
edit('src/modules/mc_raptor/mc_raptor.hpp',
     '\tuORB::SubscriptionCallbackWorkItem _vehicle_angular_velocity_sub{this, ORB_ID(vehicle_angular_velocity)};',
     '''#ifdef __PX4_POSIX
    uORB::SubscriptionCallbackWorkItem _vehicle_angular_velocity_sub{this, ORB_ID(research_angular_velocity)};
#else
\tuORB::SubscriptionCallbackWorkItem _vehicle_angular_velocity_sub{this, ORB_ID(vehicle_angular_velocity)};
#endif''')
edit('src/modules/mc_raptor/mc_raptor.hpp',
     '\tvehicle_angular_velocity_s _vehicle_angular_velocity{};',
     '''#ifdef __PX4_POSIX
    research_angular_velocity_s _vehicle_angular_velocity{};
#else
\tvehicle_angular_velocity_s _vehicle_angular_velocity{};
#endif''')
edit('src/modules/mc_raptor/mc_raptor.cpp',
     'status.subscription_update_angular_velocity = _vehicle_angular_velocity_sub.update(&_vehicle_angular_velocity);',
     '''status.subscription_update_angular_velocity = _vehicle_angular_velocity_sub.update(&_vehicle_angular_velocity);
#ifdef __PX4_POSIX
    // Schedule another work item until the queue is drained, including early returns.
    if(_vehicle_angular_velocity_sub.updated())ScheduleNow();
#endif''')

# POSIX daemon must publish its stdout TLS key before any logging thread can
# observe Server::is_running(). ASAN exposed the old uninitialized-key window.
def apply_daemon_stdout_key():
 edit('platforms/posix/src/px4/common/px4_daemon/server.cpp', '\t  _instance_id(instance_id)\n{\n\t_instance = this;\n}', '\t  _instance_id(instance_id)\n{\n    const int ret=pthread_key_create(&_key,_pthread_key_destructor);\n    if(ret!=0){PX4_ERR("failed to create daemon stdout pthread key");return;}\n\t_instance = this;\n}')
 edit('platforms/posix/src/px4/common/px4_daemon/server.cpp', 'void\nServer::_server_main()\n{\n\tint ret = pthread_key_create(&_key, _pthread_key_destructor);\n\n\tif (ret != 0) {\n\t\tPX4_ERR("failed to create pthread key");\n\t\treturn;\n\t}\n', 'void\nServer::_server_main()\n{\n    int ret=0;\n')
 edit('platforms/posix/src/px4/common/px4_daemon/server.cpp', 'Server::start()\n{\n\tstd::string sock_path', 'Server::start()\n{\n    if(_instance!=this)return -1;\n\tstd::string sock_path')

apply_daemon_stdout_key()
_saved_px=PX
PX=ROOT/'uav_lab/.local/checkouts/px4-classic'
apply_daemon_stdout_key()
PX=_saved_px

# P2: RAPTOR mode-entry memory treatments (MC_RAPTOR_RINI 2..5), teacher forcing of the inactive shadow
# inference, recurrent-memory evidence (research_memory) and the N->C velocity-integrator coordination
# (MC_RAPTOR_NCO). Anchors are upstream lines outside earlier inserted blocks.
edit('msg/CMakeLists.txt','\tRouteObservability.msg\n\tRtlStatus.msg','\tRouteObservability.msg\n\tResearchMemory.msg\n\tRtlStatus.msg')
if 'MC_RAPTOR_NCO:' not in (PX/'src/modules/mc_raptor/module.yaml').read_text():edit('src/modules/mc_raptor/module.yaml','    - group: Multicopter Raptor\n','''    - group: Handover Research
      definitions:
        MC_RAPTOR_NCO:
            description:
                short: SITL research N-to-C velocity integrator coordination
                long: 0 original classic takeover, 1 set the classic velocity integrator on the first position-control cycle after RAPTOR so that its thrust equals RAPTOR's last applied collective thrust along the current body z axis
            type: int32
            min: 0
            max: 1
            default: 0
    - group: Multicopter Raptor
''')
rap_h='src/modules/mc_raptor/mc_raptor.hpp'
edit(rap_h,'#include <uORB/topics/actuator_motors.h>','''#include <uORB/topics/actuator_motors.h>
#ifdef __PX4_POSIX
#include <uORB/topics/research_actuator.h>
#include <uORB/topics/research_memory.h>
#include <lib/handover_research/ActionMap.hpp>
#include <lib/handover_research/MemoryInit.hpp>
#endif''')
edit(rap_h,'\tfloat previous_action[EXECUTOR_SPEC::OUTPUT_DIM];','''\tfloat previous_action[EXECUTOR_SPEC::OUTPUT_DIM];
#ifdef __PX4_POSIX
    // P2 mode-entry treatments and recurrent-memory evidence (SITL research only).
    void research_set_memory(const float *values);
    bool research_classic_action(float *action);
    void research_teacher_force(bool active);
    void research_entry(int32_t mode, const float *before, const float *classic, bool classic_valid);
    void research_log_step(bool active, const float *previous_action_used, bool native_step);
    uORB::Subscription _research_actuator_sub{ORB_ID(research_actuator)};
    uORB::Publication<research_memory_s> _research_memory_pub{ORB_ID(research_memory)};
    research_actuator_s _research_classic{};
    bool _research_classic_set{false}, _research_teacher_forced{false};
    int32_t _research_mode{0};
    float _research_classic_action[4]{};
    uint32_t _research_clipped_total{0}, _research_classic_unavailable_total{0};
#endif''')
rap='src/modules/mc_raptor/mc_raptor.cpp'
# P3: the mode-entry call also receives the memory held since the most recent exit (MC_RAPTOR_RINI=6).
# P3: inference rows also log the exact policy input (executor.input) for the offline GRU replay.
migrate(rap,'    m.teacher_forced=_research_teacher_forced;\n    float memory[32]{};research_get(memory);','    m.teacher_forced=_research_teacher_forced;\n    for (TI i=0;i<22;i++) m.policy_input[i]=rlt::get(device,executor.input,0,i);\n    float memory[32]{};research_get(memory);')
migrate(rap,'_research_state.engine.staged_dim,RESET_PREVIOUS_ACTION_VALUE,written);','_research_state.engine.staged_dim,_research_exit.memory,_research_exit.valid,RESET_PREVIOUS_ACTION_VALUE,written);')
edit(rap,'ModuleBase::Descriptor Raptor::desc{task_spawn, custom_command, print_usage};','''#ifdef __PX4_POSIX
// Only the GRU hidden state and previous action; never RAPTOR's position/velocity target.
void Raptor::research_set_memory(const float *v) {
    auto &hidden = executor.executor.policy_state.content_state.next_content_state.state.state;
    auto &temp = executor.executor.policy_state_temp.content_state.next_content_state.state.state;
    for (TI i=0;i<handover_research::GRU_DIM;i++) {rlt::set(device,hidden,v[i],0,i);rlt::set(device,temp,v[i],0,i);}
    for (TI i=0;i<handover_research::ACTION_DIM;i++) previous_action[i]=v[handover_research::GRU_DIM+i];
}
// Latest motor command actually published by the classic allocator, in RAPTOR action space.
bool Raptor::research_classic_action(float *action) {
    research_actuator_s sample{};
    while (_research_actuator_sub.update(&sample)) if (sample.owner==2) {_research_classic=sample;_research_classic_set=true;}
    constexpr hrt_abstime MAX_AGE_US=50000;
    bool valid=_research_classic_set && hrt_absolute_time()-_research_classic.timestamp<=MAX_AGE_US;
    if (valid) {
        const handover_research::ActionConversion r=handover_research::motor_to_action(_research_classic.control,_research_classic_action);
        _research_clipped_total+=r.clipped;valid=r.valid;
    }
    if (!valid) {++_research_classic_unavailable_total;return false;}
    for (TI i=0;i<4;i++) action[i]=_research_classic_action[i];
    return true;
}
void Raptor::research_teacher_force(bool active) {
    static const param_t rini=param_find("MC_RAPTOR_RINI"), rsh=param_find("MC_RAPTOR_RSH");
    int32_t mode=0, enabled=0;param_get(rini,&mode);param_get(rsh,&enabled);
    _research_mode=enabled?mode:0;_research_teacher_forced=false;
    if (active || !handover_research::teacher_forcing(_research_mode)) return;
    float action[4];
    if (research_classic_action(action)) {
        for (TI i=0;i<4;i++) previous_action[i]=action[i];
        _research_teacher_forced=true;
    }
}
void Raptor::research_entry(int32_t mode, const float *before, const float *classic, bool classic_valid) {
    research_memory_s m{};
    m.timestamp=hrt_absolute_time();m.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    m.kind=research_memory_s::KIND_ENTRY;m.entry_mode=mode;m.active=true;
    for (TI i=0;i<16;i++) m.gru_before_entry[i]=before[i];
    for (TI i=0;i<4;i++) {m.previous_action_before_entry[i]=before[16+i];m.classic_action[i]=classic_valid?classic[i]:NAN;}
    if (mode>=handover_research::ENTRY_CLASSIC_ACTION) {
        float written[handover_research::MEMORY_DIM]{};
        m.entry_result=handover_research::entry_memory(mode,before,classic,classic_valid,_research_state.engine.staged,
            _research_state.engine.staged_dim,_research_exit.memory,_research_exit.valid,RESET_PREVIOUS_ACTION_VALUE,written);
        if (m.entry_result==handover_research::ENTRY_APPLIED) {
            research_set_memory(written);
            PX4_INFO("Research mode-entry treatment %d applied",(int)mode);
        } else {
            PX4_ERR("Research mode-entry treatment %d NOT applied: result %d",(int)mode,(int)m.entry_result);
        }
    }
    float after[32]{};research_get(after);
    for (TI i=0;i<16;i++) m.gru[i]=after[i];
    for (TI i=0;i<4;i++) m.previous_action[i]=after[16+i];
    m.classic_actuator_timestamp=_research_classic_set?_research_classic.actuator_timestamp:0;
    m.clipped_total=_research_clipped_total;m.classic_unavailable_total=_research_classic_unavailable_total;
    _research_memory_pub.publish(m);
}
void Raptor::research_log_step(bool active, const float *previous_action_used, bool native_step) {
    research_memory_s m{};
    m.timestamp=hrt_absolute_time();m.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    m.kind=research_memory_s::KIND_STEP;m.entry_mode=_research_mode;m.active=active;m.native_step=native_step;
    m.teacher_forced=_research_teacher_forced;
    for (TI i=0;i<22;i++) m.policy_input[i]=rlt::get(device,executor.input,0,i);
    float memory[32]{};research_get(memory);
    for (TI i=0;i<16;i++) m.gru[i]=memory[i];
    for (TI i=0;i<4;i++) {m.previous_action[i]=previous_action_used[i];m.classic_action[i]=_research_teacher_forced?_research_classic_action[i]:NAN;}
    m.classic_actuator_timestamp=_research_teacher_forced?_research_classic.actuator_timestamp:0;
    m.clipped_total=_research_clipped_total;m.classic_unavailable_total=_research_classic_unavailable_total;
    _research_memory_pub.publish(m);
}
#endif

ModuleBase::Descriptor Raptor::desc{task_spawn, custom_command, print_usage};''')
edit(rap,'''\t\tif (previous_active && !next_active) {
\t\t\tPX4_INFO("inactive");
\t\t}
\t}
''','''\t\tif (previous_active && !next_active) {
\t\t\tPX4_INFO("inactive");
\t\t}
\t}
#ifdef __PX4_POSIX
    research_teacher_force(next_active);
#endif
''')
edit(rap,'\tif (!executor_status.OK) {\n\t\tif (executor_status.TIMESTAMP_INVALID) {','''#ifdef __PX4_POSIX
    // Logged after the timed observe+control span; the GRU is the committed state after this inference.
    if (executor_status.source==decltype(executor_status.source)::CONTROL)
        research_log_step(next_active,observation.previous_action,executor_status.step_type==decltype(executor_status.step_type)::NATIVE);
#endif
\tif (!executor_status.OK) {
\t\tif (executor_status.TIMESTAMP_INVALID) {''')
# C2 (N->C): classic velocity integrator coordinated with RAPTOR's last applied output.
pc_h='src/modules/mc_pos_control/PositionControl/PositionControl.hpp'
edit(pc_h,'\tvoid resetIntegralXY() { _vel_int.xy() = matrix::Vector2f(); }','''\tvoid resetIntegralXY() { _vel_int.xy() = matrix::Vector2f(); }
#ifdef __PX4_POSIX
	/** P2 C2: set the velocity integrator so that this cycle's thrust is `thrust` along body z axis `body_z` (NED). */
	matrix::Vector3f researchCoordinate(float thrust, const matrix::Vector3f &body_z);
#endif''')
pc='src/modules/mc_pos_control/PositionControl/PositionControl.cpp'
edit(pc,'bool PositionControl::_inputValid()\n{','''#ifdef __PX4_POSIX
matrix::Vector3f PositionControl::researchCoordinate(float thrust, const matrix::Vector3f &body_z)
{
	// Inverse of _accelerationControl() for the produced collective thrust and body attitude.
	const float acc_z = (_hover_thrust - thrust * body_z(2)) * CONSTANTS_ONE_G / _hover_thrust;
	const float vertical = _decouple_horizontal_and_vertical_acceleration ? CONSTANTS_ONE_G : CONSTANTS_ONE_G - acc_z;
	const Vector3f acc_target(-vertical * body_z(0) / body_z(2), -vertical * body_z(1) / body_z(2), acc_z);
	const Vector3f previous = _vel_int;
	_vel_int += acc_target - _acc_sp;
	_vel_int(2) = math::constrain(_vel_int(2), -CONSTANTS_ONE_G, CONSTANTS_ONE_G);
	_acc_sp += _vel_int - previous;
	_accelerationControl();
	return _vel_int;
}
#endif

bool PositionControl::_inputValid()
{''')
mpc_h='src/modules/mc_pos_control/MulticopterPositionControl.hpp'
edit(mpc_h,'#include <uORB/topics/vehicle_land_detected.h>','''#include <uORB/topics/vehicle_land_detected.h>
#ifdef __PX4_POSIX
#include <uORB/topics/research_actuator.h>
#include <uORB/topics/vehicle_attitude.h>
#endif''')
edit(mpc_h,'\tuORB::Subscription _vehicle_land_detected_sub{ORB_ID(vehicle_land_detected)};','''\tuORB::Subscription _vehicle_land_detected_sub{ORB_ID(vehicle_land_detected)};
#ifdef __PX4_POSIX
	void researchTrackNeural();
	void researchCoordinateTakeover();
	uORB::Subscription _research_actuator_sub{ORB_ID(research_actuator)};
	uORB::Subscription _research_attitude_sub{ORB_ID(vehicle_attitude)};
	research_actuator_s _research_neural{};
	bool _research_neural_set{false}, _research_controlled{false};
#endif''')
mpc='src/modules/mc_pos_control/MulticopterPositionControl.cpp'
migrate(mpc,'''	PX4_INFO("Research velocity integrator coordinated: thrust %.5f age %llu us vel_int %.5f %.5f %.5f -> %.5f %.5f %.5f",
		 (double)thrust, (unsigned long long)age, (double)before(0), (double)before(1), (double)before(2),
		 (double)after(0), (double)after(1), (double)after(2));''','''	// ULog keeps about 127 characters per message: before and after are printed separately.
	PX4_INFO("Research velocity integrator coordinated: thrust %.5f age %llu us", (double)thrust, (unsigned long long)age);
	PX4_INFO("Research vel_int before %.5f %.5f %.5f", (double)before(0), (double)before(1), (double)before(2));
	PX4_INFO("Research vel_int after %.5f %.5f %.5f", (double)after(0), (double)after(1), (double)after(2));''')
edit(mpc,'\t\t\t// Publish internal position control setpoints','''#ifdef __PX4_POSIX
            researchCoordinateTakeover();
#endif
\t\t\t// Publish internal position control setpoints''')
edit(mpc,'''\t\t\t_control.resetIntegral();
\t\t}

\t\t// Publish takeoff status''','''\t\t\t_control.resetIntegral();
#ifdef __PX4_POSIX
            _research_controlled=false;
            researchTrackNeural();
#endif
\t\t}

\t\t// Publish takeoff status''')
edit(mpc,'trajectory_setpoint_s MulticopterPositionControl::generateFailsafeSetpoint(const hrt_abstime &now,','''#ifdef __PX4_POSIX
static bool research_coordination_enabled()
{
	static const param_t nco = param_find("MC_RAPTOR_NCO"), rsh = param_find("MC_RAPTOR_RSH");
	int32_t mode = 0, enabled = 0;
	param_get(nco, &mode); param_get(rsh, &enabled);
	return mode == 1 && enabled;
}
void MulticopterPositionControl::researchTrackNeural()
{
	if (!research_coordination_enabled()) return;
	research_actuator_s sample{};
	while (_research_actuator_sub.update(&sample)) if (sample.owner == 1) {_research_neural = sample; _research_neural_set = true;}
}
void MulticopterPositionControl::researchCoordinateTakeover()
{
	// First classic position-control cycle after RAPTOR owned the motors (position control disabled).
	const bool first = !_research_controlled;
	_research_controlled = true;
	if (!first || !research_coordination_enabled()) return;
	researchTrackNeural();
	vehicle_attitude_s attitude{};
	const hrt_abstime age = hrt_absolute_time() - _research_neural.timestamp;
	float thrust = 0.f;
	for (int i = 0; i < 4; i++) thrust += _research_neural.control[i] / 4.f;
	if (!_research_neural_set || age > 50_ms || !PX4_ISFINITE(thrust) || !_research_attitude_sub.copy(&attitude)) {
		PX4_WARN("Research velocity integrator coordination unavailable");
		return;
	}
	const Vector3f body_z = matrix::Dcmf(matrix::Quatf(attitude.q)).col(2);
	const Vector3f before = _control.researchGet();
	const Vector3f after = _control.researchCoordinate(thrust, body_z);
	// ULog keeps about 127 characters per message: before and after are printed separately.
	PX4_INFO("Research velocity integrator coordinated: thrust %.5f age %llu us", (double)thrust, (unsigned long long)age);
	PX4_INFO("Research vel_int before %.5f %.5f %.5f", (double)before(0), (double)before(1), (double)before(2));
	PX4_INFO("Research vel_int after %.5f %.5f %.5f", (double)after(0), (double)after(1), (double)after(2));
}
#endif

trajectory_setpoint_s MulticopterPositionControl::generateFailsafeSetpoint(const hrt_abstime &now,''')

# P3 (N3): RAPTOR stores its memory (committed GRU, previous action) on its own thread on the first inactive cycle
# after it was active, before that cycle's teacher forcing or inference; MC_RAPTOR_RINI=6 writes it back at re-entry.
edit(rap_h,'\tvoid reset();\n','''\tvoid reset();
#ifdef __PX4_POSIX
    // P3 N3: memory held unchanged since RAPTOR's most recent exit (SITL research only).
    void research_exit_lifecycle(bool active);
    handover_research::ExitMemory _research_exit{};
#endif
''')
edit(rap,'\tif (!previous_active && next_active) {\n','''#ifdef __PX4_POSIX
    research_exit_lifecycle(next_active);
#endif
\tif (!previous_active && next_active) {
''')
edit(rap,'void Raptor::updateArmingCheckReply()\n{','''#ifdef __PX4_POSIX
void Raptor::research_exit_lifecycle(bool active) {
    static const param_t rsh=param_find("MC_RAPTOR_RSH");
    int32_t enabled=0;param_get(rsh,&enabled);
    if (!enabled || !_research_exit.due(active)) return;
    float live[32]{};research_get(live);
    _research_exit.store(live);
    research_memory_s m{};
    m.timestamp=hrt_absolute_time();m.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    m.kind=research_memory_s::KIND_EXIT;m.entry_mode=_research_mode;m.active=false;
    for (TI i=0;i<16;i++) m.gru[i]=_research_exit.memory[i];
    for (TI i=0;i<4;i++) {m.previous_action[i]=_research_exit.memory[16+i];m.classic_action[i]=NAN;}
    m.clipped_total=_research_clipped_total;m.classic_unavailable_total=_research_classic_unavailable_total;
    _research_memory_pub.publish(m);
    PX4_INFO("Research exit memory stored");
}
#endif

void Raptor::updateArmingCheckReply()
{''')

# P4-01c: RAPTOR takeover target (MC_RAPTOR_RTGT, MC_RAPTOR_RTDEC) on RAPTOR's own thread. Mode 0 keeps the original
# zero-velocity capture unchanged; mode 1 replaces the zero velocity by the current horizontal velocity in the
# activation cycle and then decelerates the target at a fixed rate (research/state/TargetProfile.hpp). Every capture
# and every T1 target is published on research_target. Anchors are upstream lines outside earlier inserted blocks.
edit('msg/CMakeLists.txt','\tRtlTimeEstimate.msg','\tResearchTarget.msg\n\tRtlTimeEstimate.msg')
RTGT_P4C='                long: 0 original activation capture (current position and yaw, zero velocity); 1 speed-matched target (same capture with the current horizontal velocity, then a fixed deceleration MC_RAPTOR_RTDEC along that direction to zero, position integrated from the target velocity). Only active with MC_RAPTOR_RSH.\n            type: int32\n            min: 0\n            max: 1\n'
RTGT_P5='                long: 0 original activation capture (current position and yaw, zero velocity); 1 speed-matched target (same capture with the current horizontal velocity, then a fixed deceleration MC_RAPTOR_RTDEC along that direction to zero, position integrated from the target velocity); 2 the same speed-matched target at activation and at every in-flight setpoint-timeout capture while active. Only active with MC_RAPTOR_RSH.\n            type: int32\n            min: 0\n            max: 2\n'
TGT_FN_P4C='// P4-01c: called in the cycle in which RAPTOR captured its target (the original capture has just written the current\n// position and yaw with zero velocity). Mode 1 replaces the zero velocity by the current horizontal velocity in the\n// activation cycle only; research_target_step() then evaluates the profile every cycle while RAPTOR holds that target.\nvoid Raptor::research_target_capture(bool activation) {'
TGT_FN_P5='// P4-01c: called in the cycle in which RAPTOR captured its target (the original capture has just written the current\n// position and yaw with zero velocity). Mode 1 replaces the zero velocity by the current horizontal velocity in the\n// activation cycle only; research_target_step() then evaluates the profile every cycle while RAPTOR holds that target.\n// P5: mode 2 does the same at activation and at every in-flight setpoint-timeout capture while active.\nvoid Raptor::research_target_capture(bool activation, bool active) {'
# P5: MC_RAPTOR_RTGT=2 (speed-matched target also at in-flight setpoint-timeout captures). The P4-01c edits below carry
# the P5 text; these migrations upgrade checkouts prepared with the P4-01c text first, so each edit then finds its text.
migrate('src/modules/mc_raptor/module.yaml',RTGT_P4C,RTGT_P5)
migrate(rap_h,'    void research_target_capture(bool activation);\n','    void research_target_capture(bool activation, bool active);\n')
migrate(rap,'\t\t\tresearch_target_capture(!previous_active && next_active);\n','\t\t\tresearch_target_capture(!previous_active && next_active, next_active);\n')
migrate(rap,TGT_FN_P4C,TGT_FN_P5)
migrate(rap,'    if (activation && mode==handover_research::TARGET_SPEED_MATCHED) {\n','    if (handover_research::speed_matched_capture(mode,activation,active)) {\n')
if 'MC_RAPTOR_RTGT:' not in (PX/'src/modules/mc_raptor/module.yaml').read_text():edit('src/modules/mc_raptor/module.yaml','    - group: Multicopter Raptor\n','''    - group: Handover Research
      definitions:
        MC_RAPTOR_RTGT:
            description:
                short: SITL research RAPTOR takeover target
                long: 0 original activation capture (current position and yaw, zero velocity); 1 speed-matched target (same capture with the current horizontal velocity, then a fixed deceleration MC_RAPTOR_RTDEC along that direction to zero, position integrated from the target velocity); 2 the same speed-matched target at activation and at every in-flight setpoint-timeout capture while active. Only active with MC_RAPTOR_RSH.
            type: int32
            min: 0
            max: 2
            default: 0
        MC_RAPTOR_RTDEC:
            description:
                short: SITL research deceleration of the speed-matched takeover target
            type: float
            unit: m/s^2
            min: 0.1
            max: 10.0
            decimal: 2
            default: 2.0
    - group: Multicopter Raptor
''')
edit(rap_h,'#include <uORB/topics/trajectory_setpoint.h>','''#ifdef __PX4_POSIX
#include <uORB/topics/research_target.h>
#include <lib/handover_research/TargetProfile.hpp>
#endif
#include <uORB/topics/trajectory_setpoint.h>''')
edit(rap_h,'\tbool use_internal_reference = false;','''#ifdef __PX4_POSIX
    // P4-01c takeover target (SITL research only).
    void research_target_capture(bool activation, bool active);
    void research_target_step(bool active, bool stale);
    void research_target_publish(uint8_t kind, uint8_t end_reason);
    uORB::Publication<research_target_s> _research_target_pub{ORB_ID(research_target)};
    handover_research::TargetProfile _research_target{};
    int32_t _research_target_mode{0};
    float _research_target_decel{0.f}, _research_target_vehicle_position[3]{}, _research_target_vehicle_velocity[3]{};
    bool _research_target_activation{false};
    uint8_t _research_target_phase{0};
    hrt_abstime _research_target_capture_time{0}, _research_target_capture_sample{0}, _research_target_local_sample{0};
#endif
\tbool use_internal_reference = false;''')
edit(rap,'\t\t\t_trajectory_setpoint.yawspeed = 0;\n','''\t\t\t_trajectory_setpoint.yawspeed = 0;
#ifdef __PX4_POSIX
\t\t\tresearch_target_capture(!previous_active && next_active, next_active);
#endif
''')
# P7: the rate-limited recovery transition runs right after the takeover-target step (migration for checkouts prepared
# with the P4-01c/P5 block first).
migrate(rap,'\tresearch_target_step(next_active, status.trajectory_setpoint_stale);\n#endif\n','\tresearch_target_step(next_active, status.trajectory_setpoint_stale);\n\tresearch_recovery_transition(next_active, status.trajectory_setpoint_stale, !previous_active && next_active);\n#endif\n')
edit(rap,'\trl_tools::inference::applications::l2f::Observation<EXECUTOR_SPEC> observation;\n','''#ifdef __PX4_POSIX
\tresearch_target_step(next_active, status.trajectory_setpoint_stale);
\tresearch_recovery_transition(next_active, status.trajectory_setpoint_stale, !previous_active && next_active);
#endif
\trl_tools::inference::applications::l2f::Observation<EXECUTOR_SPEC> observation;
''')
edit(rap,'int Raptor::task_spawn(int argc, char *argv[])\n{','''#ifdef __PX4_POSIX
// P4-01c: called in the cycle in which RAPTOR captured its target (the original capture has just written the current
// position and yaw with zero velocity). Mode 1 replaces the zero velocity by the current horizontal velocity in the
// activation cycle only; research_target_step() then evaluates the profile every cycle while RAPTOR holds that target.
// P5: mode 2 does the same at activation and at every in-flight setpoint-timeout capture while active.
void Raptor::research_target_capture(bool activation, bool active) {
    static const param_t rsh=param_find("MC_RAPTOR_RSH"),rtgt=param_find("MC_RAPTOR_RTGT"),rtdec=param_find("MC_RAPTOR_RTDEC");
    int32_t enabled=0,mode=0;float decel=0.f;param_get(rsh,&enabled);
    if (!enabled) return;
    param_get(rtgt,&mode);param_get(rtdec,&decel);
    if (_research_target.active) {_research_target.active=false;research_target_publish(research_target_s::KIND_END,research_target_s::END_RECAPTURE);}
    _research_target_mode=mode;_research_target_decel=decel;_research_target_activation=activation;
    _research_target_capture_time=hrt_absolute_time();_research_target_capture_sample=_vehicle_angular_velocity.timestamp_sample;
    _research_target_local_sample=_vehicle_local_position.timestamp_sample;
    for (TI i=0;i<3;i++) {_research_target_vehicle_position[i]=position[i];_research_target_vehicle_velocity[i]=linear_velocity[i];}
    _research_target_phase=handover_research::TARGET_PHASE_HOLD;
    if (handover_research::speed_matched_capture(mode,activation,active)) {
        float p[3]={_trajectory_setpoint.position[0],_trajectory_setpoint.position[1],_trajectory_setpoint.position[2]},v[3];
        if (_research_target.start(_research_target_capture_sample,p,linear_velocity,decel)) {
            _research_target_phase=_research_target.evaluate(_research_target_capture_sample,p,v);
            for (TI i=0;i<3;i++) {_trajectory_setpoint.position[i]=p[i];_trajectory_setpoint.velocity[i]=v[i];}
            PX4_INFO("Research takeover target T1: speed %.3f m/s, decel %.2f m/s^2",(double)_research_target.speed0,(double)decel);
        } else {
            PX4_ERR("Research takeover target T1 NOT started (decel %.3f)",(double)decel);
        }
    }
    research_target_publish(research_target_s::KIND_CAPTURE,0);
}
void Raptor::research_target_step(bool active, bool stale) {
    if (!_research_target.active) return;
    if (!active || !stale) {
        _research_target.active=false;
        research_target_publish(research_target_s::KIND_END,active?research_target_s::END_EXTERNAL_SETPOINT:research_target_s::END_INACTIVE);
        return;
    }
    float p[3],v[3];_research_target_phase=_research_target.evaluate(_vehicle_angular_velocity.timestamp_sample,p,v);
    for (TI i=0;i<3;i++) {_trajectory_setpoint.position[i]=p[i];_trajectory_setpoint.velocity[i]=v[i];}
    research_target_publish(research_target_s::KIND_PROFILE,0);
}
void Raptor::research_target_publish(uint8_t kind, uint8_t end_reason) {
    research_target_s m{};
    m.timestamp=hrt_absolute_time();m.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    m.kind=kind;m.mode=_research_target_mode;m.activation=_research_target_activation;
    m.phase=kind==research_target_s::KIND_END?0:_research_target_phase;m.end_reason=end_reason;m.decel=_research_target_decel;
    m.capture_timestamp=_research_target_capture_time;m.capture_sample=_research_target_capture_sample;m.local_position_sample=_research_target_local_sample;
    for (TI i=0;i<3;i++) {
        m.vehicle_position[i]=_research_target_vehicle_position[i];m.vehicle_velocity[i]=_research_target_vehicle_velocity[i];
        m.position[i]=_trajectory_setpoint.position[i];m.velocity[i]=_trajectory_setpoint.velocity[i];
    }
    m.yaw=_trajectory_setpoint.yaw;
    _research_target_pub.publish(m);
}
#endif

int Raptor::task_spawn(int argc, char *argv[])
{''')

# P4-01c: the takeover-target parameters are marked used at module start, so the log header records their values.
# P7 adds MC_RAPTOR_RREC and advertises research_recovery at module start (the logger subscribes to a topic only some
# time after its first advertisement, which lost the first recovery's rows in development); migrations for checkouts
# prepared with the earlier blocks first.
migrate(rap,'\tparam_find("MC_RAPTOR_RTDEC");\n#endif\n','\tparam_find("MC_RAPTOR_RTDEC");\n\tparam_find("MC_RAPTOR_RREC");\n\t_research_recovery_pub.advertise();\n#endif\n')
migrate(rap,'\tparam_find("MC_RAPTOR_RREC");\n#endif\n','\tparam_find("MC_RAPTOR_RREC");\n\t_research_recovery_pub.advertise();\n#endif\n')
edit(rap,'\t_actuator_motors_pub.advertise();\n\t_tune_control_pub.advertise();\n','''\t_actuator_motors_pub.advertise();
\t_tune_control_pub.advertise();
#ifdef __PX4_POSIX
\tparam_find("MC_RAPTOR_RTGT");
\tparam_find("MC_RAPTOR_RTDEC");
\tparam_find("MC_RAPTOR_RREC");
\t_research_recovery_pub.advertise();
#endif
''')

# P7: rate-limited recovery (MC_RAPTOR_RREC, m/s^2; default 0 = the original one-step jump back to the setpoint). With
# RREC > 0, when the external setpoint is fresh again after an in-flight setpoint-timeout capture while RAPTOR is active,
# a virtual target starts at the vehicle's horizontal position and velocity and approaches the setpoint
# (research/state/RecoveryTarget.hpp); the network observes it until both differences are below 0.02, then the setpoint
# again. A new timeout during the recovery ends it and the original capture rules apply. The observation is swapped in
# for the duration of observe() only, so every other reader still sees the external setpoint. Evidence on
# research_recovery. Anchors are upstream lines outside earlier inserted blocks.
edit('msg/CMakeLists.txt','\tRadioStatus.msg','\tRadioStatus.msg\n\tResearchRecovery.msg')
if 'MC_RAPTOR_RREC:' not in (PX/'src/modules/mc_raptor/module.yaml').read_text():edit('src/modules/mc_raptor/module.yaml','    - group: Multicopter Raptor\n','''    - group: Handover Research Recovery
      definitions:
        MC_RAPTOR_RREC:
            description:
                short: SITL research rate-limited recovery after a setpoint timeout
                long: 0 original behaviour (the target jumps back to the external setpoint when it is fresh again). Greater than 0, after an in-flight setpoint-timeout capture the network observes a virtual target that starts at the vehicle's horizontal position and velocity and approaches the setpoint with acc = w^2 dp + 2 w dv (w 1.5), limited to this horizontal acceleration, until both differences are below 0.02. Only active with MC_RAPTOR_RSH.
            type: float
            unit: m/s^2
            min: 0.0
            max: 10.0
            decimal: 2
            default: 0.0
    - group: Multicopter Raptor
''')
edit(rap_h,'#include <uORB/topics/register_ext_component_request.h>','''#ifdef __PX4_POSIX
#include <uORB/topics/research_recovery.h>
#include <lib/handover_research/RecoveryTarget.hpp>
#endif
#include <uORB/topics/register_ext_component_request.h>''')
edit(rap_h,'\tvoid observe(rl_tools::inference::applications::l2f::Observation<EXECUTOR_SPEC> &observation);\n','''\tvoid observe(rl_tools::inference::applications::l2f::Observation<EXECUTOR_SPEC> &observation);
#ifdef __PX4_POSIX
    // P7 rate-limited recovery (SITL research only).
    void research_recovery_transition(bool active, bool stale, bool activation);
    bool research_recovery_apply(float saved[4]);
    void research_recovery_restore(const float saved[4]);
    void research_recovery_publish(uint8_t kind, uint8_t end_reason);
    struct ResearchRecoveryView {
        Raptor &raptor;
        float saved[4]{};
        bool on;
        explicit ResearchRecoveryView(Raptor &r) : raptor(r), on(r.research_recovery_apply(saved)) {}
        ~ResearchRecoveryView() {if (on) raptor.research_recovery_restore(saved);}
    };
    uORB::Publication<research_recovery_s> _research_recovery_pub{ORB_ID(research_recovery)};
    handover_research::RecoveryTarget _research_recovery{};
    handover_research::RecoveryStep _research_recovery_last{};
    bool _research_recovery_previous_stale{false}, _research_recovery_armed{false};
    float _research_recovery_vehicle_position[3]{}, _research_recovery_vehicle_velocity[3]{};
#endif
''')
edit(rap,'\t// converting from FRD to FLU\n','''#ifdef __PX4_POSIX
\t// P7: while the rate-limited recovery is active the network observes the virtual target (horizontal position and
\t// velocity) instead of the external setpoint; the setpoint is restored when observe() returns.
\tconst ResearchRecoveryView research_recovery_view(*this);
#endif
\t// converting from FRD to FLU
''')
edit(rap,'int Raptor::print_status()\n{','''#ifdef __PX4_POSIX
// P7: called every cycle after the takeover-target step. Arms at an in-flight setpoint-timeout capture while active (not
// at the activation capture), starts the virtual target in the cycle the setpoint is fresh again (MC_RAPTOR_RREC > 0),
// ends it at a new timeout or when RAPTOR becomes inactive.
void Raptor::research_recovery_transition(bool active, bool stale, bool activation) {
    const bool was_stale=_research_recovery_previous_stale;
    _research_recovery_previous_stale=stale;
    if (!active) {
        _research_recovery_armed=false;
        if (_research_recovery.active) {_research_recovery.active=false;research_recovery_publish(research_recovery_s::KIND_END,research_recovery_s::END_INACTIVE);}
        return;
    }
    if (stale) {
        if (activation) _research_recovery_armed=false;
        else if (!was_stale) _research_recovery_armed=true;
        if (_research_recovery.active) {_research_recovery.active=false;research_recovery_publish(research_recovery_s::KIND_END,research_recovery_s::END_STALE);}
        return;
    }
    if (!was_stale || !_research_recovery_armed) return;
    _research_recovery_armed=false;
    static const param_t rsh=param_find("MC_RAPTOR_RSH"),rrec=param_find("MC_RAPTOR_RREC");
    int32_t enabled=0;float rate=0.f;param_get(rsh,&enabled);param_get(rrec,&rate);
    if (!enabled || !(rate>0.f)) return;
    const float p[3]={position[0],position[1],position[2]},v[3]={linear_velocity[0],linear_velocity[1],linear_velocity[2]};
    if (!_research_recovery.start(_vehicle_angular_velocity.timestamp_sample,p,v,rate)) {PX4_ERR("Research recovery NOT started (rate %.3f)",(double)rate);return;}
    for (TI i=0;i<3;i++) {_research_recovery_vehicle_position[i]=p[i];_research_recovery_vehicle_velocity[i]=v[i];}
    _research_recovery_last=handover_research::RecoveryStep{};
    research_recovery_publish(research_recovery_s::KIND_START,0);
    PX4_INFO("Research recovery: virtual target, rate %.2f m/s^2",(double)rate);
}
// Inside observe(): one step of the virtual target against the external setpoint in force; the network then observes it.
bool Raptor::research_recovery_apply(float saved[4]) {
    if (!_research_recovery.active) return false;
    const float sp_p[2]={_trajectory_setpoint.position[0],_trajectory_setpoint.position[1]};
    const float sp_v[2]={_trajectory_setpoint.velocity[0],_trajectory_setpoint.velocity[1]};
    _research_recovery_last=_research_recovery.step(_vehicle_angular_velocity.timestamp_sample,sp_p,sp_v);
    if (!_research_recovery.active) {research_recovery_publish(research_recovery_s::KIND_END,research_recovery_s::END_CONVERGED);return false;}
    research_recovery_publish(research_recovery_s::KIND_STEP,0);
    for (TI i=0;i<2;i++) {
        saved[i]=sp_p[i];saved[2+i]=sp_v[i];
        _trajectory_setpoint.position[i]=float(_research_recovery.p[i]);_trajectory_setpoint.velocity[i]=float(_research_recovery.v[i]);
    }
    return true;
}
void Raptor::research_recovery_restore(const float saved[4]) {
    for (TI i=0;i<2;i++) {_trajectory_setpoint.position[i]=saved[i];_trajectory_setpoint.velocity[i]=saved[2+i];}
}
void Raptor::research_recovery_publish(uint8_t kind, uint8_t end_reason) {
    research_recovery_s m{};
    m.timestamp=hrt_absolute_time();m.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    m.kind=kind;m.end_reason=end_reason;m.rate=float(_research_recovery.rate);m.omega=float(handover_research::RecoveryTarget::OMEGA);
    const handover_research::RecoveryStep &s=_research_recovery_last;
    m.dt=float(s.dt);m.limited=s.limited;m.acc[0]=float(s.acc[0]);m.acc[1]=float(s.acc[1]);m.acc_unlimited_norm=float(s.acc_unlimited);
    m.position_difference=float(s.position_difference);m.velocity_difference=float(s.velocity_difference);m.start_sample=_research_recovery.start_us;
    const bool step=kind==research_recovery_s::KIND_STEP;
    for (TI i=0;i<3;i++) {
        m.setpoint_position[i]=_trajectory_setpoint.position[i];m.setpoint_velocity[i]=_trajectory_setpoint.velocity[i];
        m.target_position[i]=i<2 && (step || kind==research_recovery_s::KIND_START)?float(_research_recovery.p[i]):_trajectory_setpoint.position[i];
        m.target_velocity[i]=i<2 && (step || kind==research_recovery_s::KIND_START)?float(_research_recovery.v[i]):_trajectory_setpoint.velocity[i];
        m.vehicle_position[i]=_research_recovery_vehicle_position[i];m.vehicle_velocity[i]=_research_recovery_vehicle_velocity[i];
    }
    _research_recovery_pub.publish(m);
}
#endif

int Raptor::print_status()
{''')

print('Applied SITL research instrumentation and POSIX daemon TLS initialization; policy files unchanged.')

from apply_preparation import apply as apply_preparation
apply_preparation()

# Independent, read-only P11 observation hooks (default off).
from apply_p11 import apply as apply_p11
apply_p11()
from apply_p12 import apply as apply_p12
apply_p12()
from apply_p12c import apply as apply_p12c
apply_p12c()
from apply_p12b import apply as apply_p12b
apply_p12b()
