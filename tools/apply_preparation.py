"""Preparation-only lifecycle fixes and output tracing; called by apply_research."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
def replace(path,old,new):
    text=path.read_text()
    if new in text:return
    if old not in text:raise RuntimeError('preparation anchor missing: '+str(path))
    path.write_text(text.replace(old,new,1))
def apply():
    for variant in ['classic','raptor']:
        root=ROOT/'uav_lab/.local/checkouts'/('px4-'+variant)
        if variant == 'raptor':
            scheduler=root/'platforms/posix/src/px4/common/lockstep_scheduler/src/lockstep_scheduler.cpp'
            scheduler.write_bytes((ROOT/'research/platform/lockstep_scheduler.cpp').read_bytes())
        bridge=root/'src/modules/simulation/gz_bridge'
        for name in ['GZMixingInterfaceESC','GZMixingInterfaceWheel','GZMixingInterfaceServo','GZGimbal']:
            replace(bridge/(name+'.hpp'),'pthread_mutex_t _node_mutex;',
                    'pthread_mutex_t _node_mutex = PTHREAD_MUTEX_INITIALIZER;')
            p=bridge/(name+'.cpp');s=p.read_text()
            s=s.replace('\tpthread_mutex_init(&_node_mutex, nullptr);\n', '')
            p.write_text(s)
        replace(bridge/'GZBridge.hpp','#include <gz/math.hh>','#include <atomic>\n#include <gz/math.hh>')
        replace(bridge/'GZBridge.hpp','private:\n','private:\n    std::atomic<uint64_t> _research_imu_callbacks{0}, _research_baro_callbacks{0}, _research_mag_callbacks{0};\n')
        for signature, counter in [('void GZBridge::airPressureCallback(const gz::msgs::FluidPressure &msg)', 'baro'), ('void GZBridge::magnetometerCallback(const gz::msgs::Magnetometer &msg)', 'mag')]:
            replace(bridge/'GZBridge.cpp',signature+'\n{',signature+'\n{\n    _research_'+counter+'_callbacks.fetch_add(1, std::memory_order_relaxed);')
        stamp='static_cast<uint64_t>(msg.header().stamp().sec()) * 1000000ULL + msg.header().stamp().nsec() / 1000' if variant=='raptor' else 'hrt_absolute_time()'
        imu_anchor='void GZBridge::imuCallback(const gz::msgs::IMU &msg)\n{\n\tconst uint64_t timestamp = '+stamp+';'
        replace(bridge/'GZBridge.cpp',imu_anchor,imu_anchor+'\n    _research_imu_callbacks.fetch_add(1, std::memory_order_relaxed);')
        replace(bridge/'GZBridge.cpp','int GZBridge::print_status()\n{',
            'int GZBridge::print_status()\n{\n    PX4_INFO("Research callbacks: imu=%llu baro=%llu mag=%llu", (unsigned long long)_research_imu_callbacks.load(), (unsigned long long)_research_baro_callbacks.load(), (unsigned long long)_research_mag_callbacks.load());')
        dds=root/'src/modules/uxrce_dds_client/dds_topics.yaml'
        replace(dds,'publications:\n','''publications:
  # Preparation readiness: actual raw and selected barometer data.
  - topic: /fmu/out/sensor_baro
    type: px4_msgs::msg::SensorBaro
  - topic: /fmu/out/vehicle_air_data
    type: px4_msgs::msg::VehicleAirData
''')
    root=ROOT/'uav_lab/.local/checkouts/px4-raptor'
    replace(root/'msg/CMakeLists.txt','\tResearchActuator.msg','\tResearchOutput.msg\n\tResearchActuator.msg')
    replace(root/'src/lib/mixer_module/mixer_module.hpp',
        '\tconst actuator_armed_s &armed() const { return _armed; }',
        '''// SITL research: sample actually selected by the configured output provider.
#ifdef __PX4_POSIX
    hrt_abstime researchSelectedSampleTimestamp() const {
        hrt_abstime sample=0;
        if (_function_allocated[0]) _function_allocated[0]->getLatestSampleTimestamp(sample);
        return sample;
    }
#endif
\tconst actuator_armed_s &armed() const { return _armed; }''')
    esc=root/'src/modules/simulation/gz_bridge/GZMixingInterfaceESC.cpp'
    replace(esc,'#include "GZMixingInterfaceESC.hpp"',
        '#include "GZMixingInterfaceESC.hpp"\n#include <uORB/topics/research_output.h>\n#include <time.h>')
    # Marker check: output_chain() later inserts lines inside this block.
    if 'This confirms bridge selection and transport publication' not in esc.read_text():replace(esc,'\t\t\treturn _actuators_pub.Publish(rotor_velocity_message);',
        '''            const bool published=_actuators_pub.Publish(rotor_velocity_message);
            // This confirms bridge selection and transport publication, NOT motor physics consumption.
            static uint64_t attempts=0, successes=0, repeated=0, regressed=0, negative=0, previous=0;
            static uint64_t bins[8]{};
            const uint64_t sample=_mixing_output.researchSelectedSampleTimestamp();
            const uint64_t now=hrt_absolute_time();
            const int64_t age=static_cast<int64_t>(now)-static_cast<int64_t>(sample);
            ++attempts;if(published)++successes;
            if(sample && previous==sample)++repeated;
            if(sample && previous && sample<previous)++regressed;
            if(sample) {
                previous=sample;
                if(age<0)++negative;
                else {
                    const int64_t limits[7]={0,4000,8000,12000,20000,40000,100000};
                    unsigned i=0;while(i<7 && age>limits[i])++i;++bins[i];
                }
            }
            struct timespec wall{};clock_gettime(CLOCK_MONOTONIC,&wall);
            research_output_s trace{};
            trace.timestamp=now;trace.timestamp_sample=sample;
            trace.wall_monotonic_ns=static_cast<uint64_t>(wall.tv_sec)*1000000000ULL+wall.tv_nsec;
            trace.attempts_total=attempts;trace.published_total=successes;
            trace.repeated_sample_total=repeated;trace.regressed_sample_total=regressed;trace.negative_age_total=negative;
            for(unsigned i=0;i<8;i++)trace.age_bins[i]=bins[i];
            trace.transport_published=published;trace.armed=_mixing_output.armed().armed;
            for(unsigned i=0;i<4 && i<active_output_count;i++)trace.motor_speed[i]=outputs[i];
            static uORB::Publication<research_output_s> trace_pub{ORB_ID(research_output)};
            trace_pub.publish(trace);
            return published;''')
    output_chain(root)

def output_chain(root):
    """Output-chain measurement: sample ID to Gazebo, overwrite counts, per-physics-step trace."""
    functions=root/'src/lib/mixer_module/functions'
    replace(functions/'FunctionProviderBase.hpp','\tvirtual bool getLatestSampleTimestamp(hrt_abstime &t) const { return false; }',
        '\tvirtual bool getLatestSampleTimestamp(hrt_abstime &t) const { return false; }\n#ifdef __PX4_POSIX\n    virtual bool researchGeneration(unsigned &g) const { return false; }\n#endif')
    replace(functions/'FunctionMotors.hpp','\tbool getLatestSampleTimestamp(hrt_abstime &t) const override { t = _data.timestamp_sample; return t != 0; }',
        '\tbool getLatestSampleTimestamp(hrt_abstime &t) const override { t = _data.timestamp_sample; return t != 0; }\n#ifdef __PX4_POSIX\n    // uORB generation of the last copied actuator_motors; gaps are overwritten publications.\n    bool researchGeneration(unsigned &g) const override { g = _topic.get_last_generation(); return true; }\n#endif')
    # Anchor after the earlier block so that block stays contiguous for its own idempotence check.
    replace(root/'src/lib/mixer_module/mixer_module.hpp','\tbool isActuatorTestRunning() const { return _actuator_test.inTestMode(); }',
        '#ifdef __PX4_POSIX\n    bool researchSelectedGeneration(unsigned &g) const {\n        return _function_allocated[0] && _function_allocated[0]->researchGeneration(g);\n    }\n#endif\n\tbool isActuatorTestRunning() const { return _actuator_test.inTestMode(); }')
    esc=root/'src/modules/simulation/gz_bridge/GZMixingInterfaceESC.cpp'
    replace(esc,'            const bool published=_actuators_pub.Publish(rotor_velocity_message);',
        '''            // Sample ID travels to Gazebo in the header; the motor model ignores headers.
            const uint64_t research_sample=_mixing_output.researchSelectedSampleTimestamp();
            rotor_velocity_message.mutable_header()->mutable_stamp()->set_sec(research_sample/1000000ULL);
            rotor_velocity_message.mutable_header()->mutable_stamp()->set_nsec((research_sample%1000000ULL)*1000ULL);
            const bool published=_actuators_pub.Publish(rotor_velocity_message);''')
    replace(esc,'trace.transport_published=published;trace.armed=_mixing_output.armed().armed;',
        '''trace.transport_published=published;trace.armed=_mixing_output.armed().armed;
            static uint64_t skipped=0;static unsigned previous_generation=0;static bool generation_seen=false;
            unsigned generation=0;
            if(_mixing_output.researchSelectedGeneration(generation)) {
                if(generation_seen && generation!=previous_generation)skipped+=generation-previous_generation-1;
                previous_generation=generation;generation_seen=true;
            }
            trace.skipped_publication_total=skipped;''')
    plugins=root/'src/modules/simulation/gz_plugins'
    (plugins/'research_motor_model').mkdir(exist_ok=True)
    for name in ['ResearchMulticopterMotorModel.cc','ResearchMulticopterMotorModel.hh','P13PhysicsTrace.hh','CMakeLists.txt']:
        target=plugins/'research_motor_model'/name;source=ROOT/'research/gz'/name
        if not target.exists() or target.read_bytes()!=source.read_bytes():shutil.copy2(source,target)
    cmake=plugins/'CMakeLists.txt'
    replace(cmake,'    add_subdirectory(airspeed)\n','    add_subdirectory(airspeed)\n    add_subdirectory(research_motor_model)\n')
    text=cmake.read_text()
    if 'AirSpeedPlugin ResearchMulticopterMotorModel)' not in text:
        if text.count('AirSpeedPlugin)')!=2:raise RuntimeError('preparation anchor missing: '+str(cmake))
        cmake.write_text(text.replace('AirSpeedPlugin)','AirSpeedPlugin ResearchMulticopterMotorModel)'))
    # Research model copy outside the gz submodule so candidate identity hashes it.
    model=(root/'Tools/simulation/gz/models/x500/model.sdf').read_text()
    old='<plugin filename="gz-sim-multicopter-motor-model-system"\n      name="gz::sim::systems::MulticopterMotorModel">'
    if model.count(old)!=4:raise RuntimeError('preparation anchor missing: x500 motor plugins')
    model=model.replace(old,'<plugin filename="ResearchMulticopterMotorModel"\n      name="gz::sim::systems::ResearchMulticopterMotorModel">')
    target=root/'Tools/simulation/research_models/x500/model.sdf';target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists() or target.read_text()!=model:target.write_text(model)
if __name__=='__main__':apply()
