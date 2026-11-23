#!/usr/bin/env python3
"""Apply narrow, idempotent SITL research edits to the preserved RAPTOR checkout."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
PX=ROOT/'uav_lab/.local/checkouts/px4-raptor'
def edit(name,old,new):
 p=PX/name;s=p.read_text()
 if new in s:return
 if old not in s:raise RuntimeError('expected source anchor missing: '+name)
 p.write_text(s.replace(old,new,1))

def main():
 dest=PX/'src/lib/handover_research';dest.mkdir(exist_ok=True)
 for p in (ROOT/'research/state').glob('*.hpp'):shutil.copy2(p,dest/p.name)
 for p in (ROOT/'research/state').glob('*.msg'):shutil.copy2(p,PX/'msg'/p.name)
 edit('msg/CMakeLists.txt','\tRouteObservability.msg','\tResearchStateRequest.msg\n\tResearchStateResponse.msg\n\tResearchTiming.msg\n\tResearchActuator.msg\n\tRouteObservability.msg')
 if 'MC_RAPTOR_RSH:' not in (PX/'src/modules/mc_raptor/module.yaml').read_text():edit('src/modules/mc_raptor/module.yaml','parameters:\n','parameters:\n    - group: Handover Research\n      definitions:\n        MC_RAPTOR_RSH:\n            description:\n                short: Enable SITL controller state research interface\n            type: boolean\n            default: false\n')
 # Local state operations are excluded from hardware builds.
 for name,member in [('mc_rate_control/MulticopterRateControl.hpp','handover_research::StateBridge _research_state{2, 3, 0.3f};'),('mc_pos_control/MulticopterPositionControl.hpp','handover_research::StateBridge _research_state{3, 3, 4.f};'),('mc_raptor/mc_raptor.hpp','handover_research::StateBridge _research_state{1, 26, 100.f};\n\tvoid research_get(float *values);\n\tvoid research_set(const float *values, bool reset_state);')]:
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
    timing.inference_duration_us=(wall_end.tv_sec-wall_start.tv_sec)*1000000+(wall_end.tv_nsec-wall_start.tv_nsec)/1000;
    timing.active=next_active;
    timing.executor_ok=executor_status.OK;
    timing.control_step=executor_status.source==decltype(executor_status.source)::CONTROL;
    timing.mode_id=ext_component_mode_id;
    timing.output_finite=true;
    if(timing.control_step)for(TI i=0;i<4;i++) {timing.action[i]=action.action[i];timing.output_finite &= PX4_ISFINITE(action.action[i]);}
    static uORB::Publication<research_timing_s> timing_pub{ORB_ID(research_timing)};
    timing_pub.publish(timing);
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
 print('Applied state API and wall-clock inference instrumentation; policy files unchanged.')
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
if 'MC_RAPTOR_RINI:' not in (PX/'src/modules/mc_raptor/module.yaml').read_text():edit('src/modules/mc_raptor/module.yaml','    - group: Handover Research\n','''    - group: Handover Research
      definitions:
        MC_RAPTOR_RINI:
            description:
                short: SITL research preserve memory on mode entry
            type: boolean
            default: false
    - group: Handover Research
''')
edit('src/modules/mc_raptor/mc_raptor.hpp','ext_component_mode_id;','ext_component_mode_id = 255;')
edit('src/modules/mc_raptor/mc_raptor.cpp','bool next_active = timestamp_last_vehicle_status_set && _vehicle_status.nav_state == ext_component_mode_id;','bool next_active = flightmode_state == FlightModeState::CONFIGURED && timestamp_last_vehicle_status_set && _vehicle_status.nav_state == ext_component_mode_id;')
edit('src/modules/mc_raptor/mc_raptor.cpp','''\t\tthis->reset();
\t\tPX4_INFO("Resetting Inference Executor (Recurrent State)");''','''#ifdef __PX4_POSIX
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
\t\tPX4_INFO("Resetting Inference Executor (Recurrent State)");''')
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
