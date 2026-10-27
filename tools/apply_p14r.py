"""P14R passive estimator/output/gyro state interface, POSIX only.
Source maintained here; no direct manual Lab edits. Unique whole-block markers
are idempotent and independent of pre-existing injection anchors.
"""
from pathlib import Path
import re
R=Path(__file__).resolve().parents[1];P=R/'uav_lab/.local/checkouts/px4-raptor'
def edit(name,old,new,marker):
 p=P/name;s=p.read_text()
 if marker in s:return
 if old not in s:raise RuntimeError('P14R anchor missing '+name)
 p.write_text(s.replace(old,new,1))

def hook(kind,time,fields,buffers):
 return '\n#ifdef __PX4_POSIX\n\t{ p14r::Core pr{};pr.kind='+str(kind)+';pr.sample_us='+time+';'+fields+'research_snapshot(pr,'+('true' if buffers else 'false')+'); }\n#endif\n'

def apply():
 h='src/modules/ekf2/EKF/output_predictor/output_predictor.h';c='src/modules/ekf2/EKF/output_predictor/output_predictor.cpp'
 edit(h,'#include <matrix/math.hpp>','#include <matrix/math.hpp>\n#ifdef __PX4_POSIX\n#include <lib/handover_research/P14RBuffer.hpp>\n#include <drivers/drv_hrt.h>\n#endif','P14RBuffer.hpp')
 edit(h,'private:\n','''#ifdef __PX4_POSIX
    // P14R_PASSIVE_SNAPSHOT: never used in estimator decisions.
    void research_snapshot(p14r::Core value,bool buffers);
#endif
private:
''','P14R_PASSIVE_SNAPSHOT')
 edit(h,'    void research_snapshot(p14r::Core value,bool buffers);','''    void research_snapshot(p14r::Core value,bool buffers);
    // P14R_SCOPE_DECL: capture all rare output resets/alignments.
    struct ResearchScope {
        OutputPredictor &owner;p14r::Core row{};
        ResearchScope(OutputPredictor &object,uint64_t kind,uint64_t sample):owner(object){row.kind=kind;row.sample_us=sample;owner.research_snapshot(row,true);}
        ~ResearchScope(){row.kind++;owner.research_snapshot(row,true);}
    };''','P14R_SCOPE_DECL')
 method='''
#ifdef __PX4_POSIX
// P14R_SNAPSHOT_IMPLEMENTATION
void OutputPredictor::research_snapshot(p14r::Core r,bool buffers)
{
    if(!std::getenv("HANDOVER_P14R_TRACE_DIR"))return;
    static p14r::Buffer<p14r::Core> trace("observer-core.bin","P14RCORE",131072);
    static p14r::Buffer<p14r::Fusion> fusion("observer-fusion.bin","P14RFUS1",16384);
    if(!trace.enabled())return;
    r.wall_ns=p14r::wall_ns();r.native_us=hrt_absolute_time();
    _output_new.quat_nominal.copyTo(r.data);_output_new.vel.copyTo(r.data+4);_output_new.pos.copyTo(r.data+7);
    r.data[10]=_output_vert_new.vert_vel;r.data[11]=_output_vert_new.vert_vel_integ;r.data[12]=_output_vert_new.dt;
    _gyro_bias.copyTo(r.data+13);_accel_bias.copyTo(r.data+16);_delta_angle_corr.copyTo(r.data+19);
    _vel_err_integ.copyTo(r.data+22);_pos_err_integ.copyTo(r.data+25);_vel_imu_rel_body_ned.copyTo(r.data+28);
    _delta_vel_sum.copyTo(r.data+31);r.data[34]=_delta_vel_dt;r.data[35]=_dt_update_states_avg;r.data[36]=_dt_correct_states_avg;
    r.data[37]=_vel_tau;r.data[38]=_pos_tau;r.data[39]=_gravity;_imu_pos_body.copyTo(r.data+40);_output_tracking_error.copyTo(r.data+43);
    r.data[46]=_unaided_yaw;_delta_angle_sum.copyTo(r.data+47);r.data[51]=_delta_angle_sum_dt;
    for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)r.data[52+3*a+b]=_R_to_earth_now(a,b);
    r.geo[0]=_global_ref.latitude_rad();r.geo[1]=_global_ref.longitude_rad();r.geo[2]=static_cast<double>(_global_ref.altitude());
    r.ids[0]=_time_last_update_states_us;r.ids[1]=_time_last_correct_states_us;r.ids[2]=_output_buffer.get_length();r.ids[3]=static_cast<uint64_t>(_output_buffer.entries());
    r.ids[4]=_output_buffer.get_newest_index();r.ids[5]=_output_buffer.get_oldest_index();r.ids[6]=_output_vert_buffer.get_length();r.ids[7]=static_cast<uint64_t>(_output_vert_buffer.entries());
    r.ids[8]=_output_vert_buffer.get_newest_index();r.ids[9]=_output_vert_buffer.get_oldest_index();r.ids[10]=_output_new.time_us;r.ids[11]=_output_vert_new.time_us;
    trace.Push(r);
    if(buffers){
        p14r::Fusion f{};f.core=r;f.core.ids[12]=r.ids[2]>64 || r.ids[6]>64;
        for(uint8_t a=0;a<_output_buffer.get_length() && a<64;a++){const auto &v=_output_buffer[a];f.time[a]=v.time_us;v.quat_nominal.copyTo(f.state[a]);v.vel.copyTo(f.state[a]+4);v.pos.copyTo(f.state[a]+7);}
        for(uint8_t a=0;a<_output_vert_buffer.get_length() && a<64;a++){const auto &v=_output_vert_buffer[a];f.vertical_time[a]=v.time_us;f.vertical[a][0]=v.vert_vel;f.vertical[a][1]=v.vert_vel_integ;f.vertical[a][2]=v.dt;}
        fusion.Push(f);
    }
}
#endif

'''
 edit(c,'void OutputPredictor::print_status()',method+'void OutputPredictor::print_status()','P14R_SNAPSHOT_IMPLEMENTATION')
 edit(c,'r.wall_ns=p14r::wall_ns();r.native_us=hrt_absolute_time();','r.wall_ns=p14r::wall_ns();r.native_us=hrt_absolute_time();\n    r.ids[13]=static_cast<uint64_t>(reinterpret_cast<uintptr_t>(this)); // P14R_OWNER_ID','P14R_OWNER_ID')
 # v2 process-lifetime storage: PX4 POSIX can leave work-queue producers alive
 # during C++ static destruction. Keep bounded mappings until kernel teardown.
 path=P/c;s=path.read_text()
 old='static p14r::Buffer<p14r::Core> trace("observer-core.bin","P14RCORE",131072);'
 new='static auto *trace_storage=new p14r::Buffer<p14r::Core>("observer-core.bin","P14RCORE",131072);auto &trace=*trace_storage; // P14R_PROCESS_LIFETIME'
 if old in s:s=s.replace(old,new,1)
 old='static p14r::Buffer<p14r::Fusion> fusion("observer-fusion.bin","P14RFUS1",16384);'
 new='static auto *fusion_storage=new p14r::Buffer<p14r::Fusion>("observer-fusion.bin","P14RFUS1",65536);auto &fusion=*fusion_storage;'
 if old in s:s=s.replace(old,new,1)
 path.write_text(s)
 path=P/c;s=path.read_text();s=re.sub(r'\("observer-core.bin","P14RCORE",\d+\)', '("observer-core.bin","P14RCORE",p14r::CORE_CAPACITY)',s);s=re.sub(r'\("observer-fusion.bin","P14RFUS1",\d+\)', '("observer-fusion.bin","P14RFUS1",p14r::FUSION_CAPACITY)',s);path.write_text(s)
 calcfields='delta_angle.copyTo(pr.data+64);delta_velocity.copyTo(pr.data+67);pr.data[70]=delta_angle_dt;pr.data[71]=delta_velocity_dt;'
 edit(c,'\t// Use full rate IMU data at the current time horizon','// P14R_CALC_PRE'+hook(1,'time_us',calcfields,False)+'\t// Use full rate IMU data at the current time horizon','P14R_CALC_PRE')
 edit(c,'\t_delta_angle_sum_dt += delta_angle_dt;','\t_delta_angle_sum_dt += delta_angle_dt;\n// P14R_CALC_POST'+hook(2,'time_us',calcfields,False),'P14R_CALC_POST')
 fusionfields='quat_state.copyTo(pr.data+64);vel_state.copyTo(pr.data+68);gyro_bias.copyTo(pr.data+74);accel_bias.copyTo(pr.data+77);pr.geo[3]=gpos_state.latitude_rad();pr.geo[4]=gpos_state.longitude_rad();pr.geo[5]=static_cast<double>(gpos_state.altitude());'
 edit(c,'\t// calculate an average filter update time','// P14R_FUSION_PRE'+hook(3,'time_delayed_us',fusionfields,True)+'\t// calculate an average filter update time','P14R_FUSION_PRE')
 # v1 build-only failure: generic global_ref anchor selected alignOutputFilter.
 # Preserve that failed source separately, migrate its hook out, then use a
 # complete function-boundary anchor. No flight used v1.
 bad='// P14R_FUSION_POST'+hook(4,'time_delayed_us',fusionfields,True)
 path=P/c;s=path.read_text()
 if bad in s and s.index(bad)<s.index('void OutputPredictor::correctOutputStates'):
  path.write_text(s.replace(bad,'',1))
 anchor='\t_global_ref = gpos_state;\n}\n\nvoid OutputPredictor::applyCorrectionToVerticalOutputBuffer'
 edit(c,anchor,'\t_global_ref = gpos_state;\n// P14R_FUSION_POST'+hook(4,'time_delayed_us',fusionfields,True)+'}\n\nvoid OutputPredictor::applyCorrectionToVerticalOutputBuffer','P14R_FUSION_POST')
 for number,name in enumerate(['alignOutputFilter','reset','resetQuaternion','resetHorizontalVelocityTo','resetVerticalVelocityTo','resetLatLonTo','resetAltitudeTo']):
  marker='P14R_SCOPE_'+name;path=P/c;s=path.read_text()
  if marker not in s:
   match=re.search(r'void OutputPredictor::'+name+r'\([^{}]*\)\s*\{',s)
   if not match:raise RuntimeError('P14R reset/align signature '+name)
   at=match.end();s=s[:at]+'\n#ifdef __PX4_POSIX\n    // '+marker+'\n    ResearchScope p14r_scope(*this,'+str(10+2*number)+',_time_last_update_states_us);\n#endif\n'+s[at:];path.write_text(s)
 filt='src/lib/mathlib/math/filter/LowPassFilter2p.hpp'
 edit(filt,'\tLowPassFilter2p() = default;','''    // P14R_PASSIVE_FILTER_ACCESSORS: no mutation.
#ifdef __PX4_POSIX
    const T &research_delay1() const {return _delay_element_1;}
    const T &research_delay2() const {return _delay_element_2;}
#endif
\tLowPassFilter2p() = default;''','P14R_PASSIVE_FILTER_ACCESSORS')
 gyro='src/modules/sensors/vehicle_angular_velocity/VehicleAngularVelocity.cpp'
 # Keep old P0 include insertion contiguous. A v1 include-only duplication is
 # preserved in the source-closure FAIL, then removed here before any flight.
 path=P/gyro;s=path.read_text();block='#ifdef __PX4_POSIX\n#include <lib/handover_research/P14RBuffer.hpp>\n#endif\n';oldblock='#ifdef __PX4_POSIX\n#include <uORB/topics/research_angular_velocity.h>\n#endif\n'
 if s.count(oldblock)>1:
  s=s.replace(block,'',1)
  while s.count(oldblock)>1:
   at=s.rfind(oldblock);s=s[:at]+s[at+len(oldblock):]
  path.write_text(s)
 edit(gyro,'#include <px4_platform_common/log.h>','#include <px4_platform_common/log.h>\n'+block,'P14RBuffer.hpp')
 edit(gyro,'\t\t_angular_velocity = _calibration.Correct(angular_velocity_uncalibrated) - _bias;','''\t\t_angular_velocity = _calibration.Correct(angular_velocity_uncalibrated) - _bias;
#ifdef __PX4_POSIX
        // P14R_GYRO_DELAY_STATE
        if(std::getenv("HANDOVER_P14R_TRACE_DIR")){
            static p14r::Buffer<p14r::Core> trace("observer-gyro.bin","P14RGYRO",65536);
            p14r::Core r{};r.kind=30;r.sample_us=timestamp_sample;r.native_us=hrt_absolute_time();r.wall_ns=p14r::wall_ns();
            for(int a=0;a<3;a++){r.data[a]=_lp_filter_velocity[a].research_delay1();r.data[a+3]=_lp_filter_velocity[a].research_delay2();}
            _bias.copyTo(r.data+6);_angular_velocity.copyTo(r.data+9);angular_velocity_uncalibrated.copyTo(r.data+12);
            r.data[15]=_filter_sample_rate_hz;r.ids[0]=_selected_sensor_device_id;trace.Push(r);
        }
#endif''','P14R_GYRO_DELAY_STATE')
 edit(gyro,'r.data[15]=_filter_sample_rate_hz;r.ids[0]=_selected_sensor_device_id;trace.Push(r);','r.data[15]=_filter_sample_rate_hz;r.ids[0]=_selected_sensor_device_id;r.ids[1]=static_cast<uint64_t>(reinterpret_cast<uintptr_t>(this));/* P14R_GYRO_OWNER */trace.Push(r);','P14R_GYRO_OWNER')
 path=P/gyro;s=path.read_text();old='static p14r::Buffer<p14r::Core> trace("observer-gyro.bin","P14RGYRO",65536);';new='static auto *trace_storage=new p14r::Buffer<p14r::Core>("observer-gyro.bin","P14RGYRO",65536);auto &trace=*trace_storage; // P14R_PROCESS_LIFETIME'
 if old in s:path.write_text(s.replace(old,new,1))
 path=P/gyro;s=path.read_text();s=re.sub(r'\("observer-gyro.bin","P14RGYRO",\d+\)', '("observer-gyro.bin","P14RGYRO",p14r::GYRO_CAPACITY)',s);path.write_text(s)
 print('P14R passive observer snapshot hooks applied; controller/estimator assignments unchanged.')

if __name__=='__main__':apply()
