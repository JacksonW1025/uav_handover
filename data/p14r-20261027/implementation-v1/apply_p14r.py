"""P14R passive estimator/output/gyro state interface, POSIX only.
Source maintained here; no direct manual Lab edits. Unique whole-block markers
are idempotent and independent of pre-existing injection anchors.
"""
from pathlib import Path
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
 calcfields='delta_angle.copyTo(pr.data+64);delta_velocity.copyTo(pr.data+67);pr.data[70]=delta_angle_dt;pr.data[71]=delta_velocity_dt;'
 edit(c,'\t// Use full rate IMU data at the current time horizon','// P14R_CALC_PRE'+hook(1,'time_us',calcfields,False)+'\t// Use full rate IMU data at the current time horizon','P14R_CALC_PRE')
 edit(c,'\t_delta_angle_sum_dt += delta_angle_dt;','\t_delta_angle_sum_dt += delta_angle_dt;\n// P14R_CALC_POST'+hook(2,'time_us',calcfields,False),'P14R_CALC_POST')
 fusionfields='quat_state.copyTo(pr.data+64);vel_state.copyTo(pr.data+68);gyro_bias.copyTo(pr.data+74);accel_bias.copyTo(pr.data+77);pr.geo[3]=gpos_state.latitude_rad();pr.geo[4]=gpos_state.longitude_rad();pr.geo[5]=static_cast<double>(gpos_state.altitude());'
 edit(c,'\t// calculate an average filter update time','// P14R_FUSION_PRE'+hook(3,'time_delayed_us',fusionfields,True)+'\t// calculate an average filter update time','P14R_FUSION_PRE')
 edit(c,'\t_global_ref = gpos_state;','\t_global_ref = gpos_state;\n// P14R_FUSION_POST'+hook(4,'time_delayed_us',fusionfields,True),'P14R_FUSION_POST')
 filt='src/lib/mathlib/math/filter/LowPassFilter2p.hpp'
 edit(filt,'\tLowPassFilter2p() = default;','''    // P14R_PASSIVE_FILTER_ACCESSORS: no mutation.
#ifdef __PX4_POSIX
    const T &research_delay1() const {return _delay_element_1;}
    const T &research_delay2() const {return _delay_element_2;}
#endif
\tLowPassFilter2p() = default;''','P14R_PASSIVE_FILTER_ACCESSORS')
 gyro='src/modules/sensors/vehicle_angular_velocity/VehicleAngularVelocity.cpp'
 edit(gyro,'#include "VehicleAngularVelocity.hpp"','#include "VehicleAngularVelocity.hpp"\n#ifdef __PX4_POSIX\n#include <lib/handover_research/P14RBuffer.hpp>\n#endif','P14RBuffer.hpp')
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
 print('P14R passive observer snapshot hooks applied; controller/estimator assignments unchanged.')

if __name__=='__main__':apply()
