
#define __PX4_POSIX 1
#include <cmath>
#include <cstdint>
#include <iostream>
#include <iomanip>
#include "research/state/TargetProfile.hpp"
#include "research/state/RecoveryTarget.hpp"
#include "research/state/SampleClock.hpp"
#define PX4_WARN(...) ((void)0)
#define PX4_INFO(...) ((void)0)
#define PX4_ERR(...) ((void)0)
#define PX4_ISFINITE(x) std::isfinite(x)
using TI=int;using param_t=int;
uint64_t now_us=0;
uint64_t hrt_absolute_time(){return now_us;}
param_t param_find(const char* s){return std::string(s)=="MC_RAPTOR_RSH"?1:std::string(s)=="MC_RAPTOR_RTGT"?2:std::string(s)=="MC_RAPTOR_RTDEC"?3:4;}
int32_t rtgt=0;float rrec=0;
void param_get(param_t p,int32_t* v){*v=p==1?1:rtgt;}
void param_get(param_t p,float* v){*v=p==3?2.f:rrec;}
struct research_target_s {enum {KIND_END=1,KIND_CAPTURE=2,KIND_PROFILE=3,END_RECAPTURE=4,END_EXTERNAL_SETPOINT=5,END_INACTIVE=6};};
struct research_recovery_s {enum {KIND_END=1,KIND_START=2,END_INACTIVE=3,END_STALE=4};};
struct trajectory_setpoint_s {float position[3]{},velocity[3]{},yaw{0},yawspeed{0};};
struct Raptor {
 trajectory_setpoint_s _trajectory_setpoint{};
 float position[3]{},linear_velocity[3]{};
 struct {float q[4]{1,0,0,0};} _vehicle_attitude;
 struct {uint64_t timestamp_sample=0;} _vehicle_angular_velocity,_vehicle_local_position;
 handover_research::TargetProfile _research_target{};
 int32_t _research_target_mode=0;float _research_target_decel=0;
 bool _research_target_activation=false;uint64_t _research_target_capture_time=0,_research_target_capture_sample=0,_research_target_local_sample=0;
 float _research_target_vehicle_position[3]{},_research_target_vehicle_velocity[3]{};uint8_t _research_target_phase=0;
 handover_research::RecoveryTarget _research_recovery{};handover_research::RecoveryStep _research_recovery_last{};
 bool _research_recovery_previous_stale=false,_research_recovery_armed=false;
 float _research_recovery_vehicle_position[3]{},_research_recovery_vehicle_velocity[3]{};
 int capture=0,rec_start=0;
 void research_target_publish(uint8_t k,uint8_t){if(k==research_target_s::KIND_CAPTURE)capture++;}
 void research_recovery_publish(uint8_t k,uint8_t){if(k==research_recovery_s::KIND_START)rec_start++;}
 void research_target_capture(bool,bool);void research_target_step(bool,bool);void research_recovery_transition(bool,bool,bool);
 uint64_t timestamp_last_trajectory_setpoint=0;bool timestamp_last_trajectory_setpoint_set=false;
 bool previous_trajectory_setpoint_stale=false,previous_active=false;
 handover_research::SampleClock sample_clock{};
 static constexpr uint64_t TRAJECTORY_SETPOINT_TIMEOUT=200000;
 static constexpr unsigned NUM_TRAJECTORY_SETPOINT_DTS=8,TRAJECTORY_SETPOINT_INVALID_COUNT_WARNING_INTERVAL=100;
 uint64_t trajectory_setpoint_dts[8]{};unsigned trajectory_setpoint_dt_index=0,trajectory_setpoint_invalid_count=0;bool trajectory_setpoint_dts_full=false;
 void tick(uint64_t current_time,uint64_t sample,bool updated,bool next_active,trajectory_setpoint_s temp_trajectory_setpoint){
  now_us=current_time;_vehicle_angular_velocity.timestamp_sample=sample;_vehicle_local_position.timestamp_sample=sample;
  bool use_internal_reference=false;
  struct {bool subscription_update_trajectory_setpoint,trajectory_setpoint_stale;uint64_t timestamp_last_trajectory_setpoint;} status{};
  status.subscription_update_trajectory_setpoint=updated;
  capture=0;rec_start=0;
if (status.subscription_update_trajectory_setpoint) {
		if (
			PX4_ISFINITE(temp_trajectory_setpoint.position[0]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.position[1]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.position[2]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.yaw) &&
			PX4_ISFINITE(temp_trajectory_setpoint.velocity[0]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.velocity[1]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.velocity[2]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.yawspeed)
		) {
			if (timestamp_last_trajectory_setpoint_set) {
				trajectory_setpoint_dts[trajectory_setpoint_dt_index] = current_time - timestamp_last_trajectory_setpoint;
				trajectory_setpoint_dt_index++;

				if (trajectory_setpoint_dt_index == NUM_TRAJECTORY_SETPOINT_DTS) {
					if (next_active && !trajectory_setpoint_dts_full) {
						PX4_INFO("trajectory_setpoint_dts_full");
					}

					trajectory_setpoint_dts_full = true;
					trajectory_setpoint_dt_index = 0;
				}
			}

			timestamp_last_trajectory_setpoint_set = true;
			status.timestamp_last_trajectory_setpoint = current_time;
			timestamp_last_trajectory_setpoint = current_time;
			_trajectory_setpoint = temp_trajectory_setpoint;

		} else {
			trajectory_setpoint_invalid_count++;

			if (next_active && trajectory_setpoint_invalid_count % TRAJECTORY_SETPOINT_INVALID_COUNT_WARNING_INTERVAL == 0) {
				PX4_WARN("trajectory_setpoint invalid, count: %d", (int)trajectory_setpoint_invalid_count);
			}
		}
	}
if (!timestamp_last_trajectory_setpoint_set || use_internal_reference
	    || (current_time - timestamp_last_trajectory_setpoint) > TRAJECTORY_SETPOINT_TIMEOUT) {
		status.trajectory_setpoint_stale = true;

		if (!previous_trajectory_setpoint_stale || (!previous_active && next_active)) {
			_trajectory_setpoint.position[0] = position[0];
			_trajectory_setpoint.position[1] = position[1];
			_trajectory_setpoint.position[2] = position[2];
			auto &q = _vehicle_attitude.q;
			_trajectory_setpoint.yaw = atan2f(2.0f * (q[1] * q[2] + q[0] * q[3]), 1.0f - 2.0f * (q[2] * q[2] + q[3] * q[3]));
			_trajectory_setpoint.velocity[0] = 0;
			_trajectory_setpoint.velocity[1] = 0;
			_trajectory_setpoint.velocity[2] = 0;
			_trajectory_setpoint.yawspeed = 0;
#ifdef __PX4_POSIX
			research_target_capture(!previous_active && next_active, next_active);
#endif

			if (!previous_trajectory_setpoint_stale) {
				PX4_WARN("trajectory_setpoint turned stale at: %f %f %f, yaw: %f %llu / %llu us", (double)position[0], (double)position[1],
					 (double)position[2],
					 (double)_trajectory_setpoint.yaw, (unsigned long long)(current_time - timestamp_last_trajectory_setpoint),
					 (unsigned long long)(TRAJECTORY_SETPOINT_TIMEOUT));

			} else {
				PX4_WARN("trajectory_setpoint reset due to activation at: %f %f %f, yaw: %f", (double)position[0], (double)position[1], (double)position[2],
					 (double)_trajectory_setpoint.yaw);
			}
		}

		previous_trajectory_setpoint_stale = true;

	} else {
		if (previous_trajectory_setpoint_stale) {
			PX4_WARN("trajectory_setpoint turned non-stale at: %f %f %f", (double)position[0], (double)position[1], (double)position[2]);
			previous_trajectory_setpoint_stale = false;
		}

		status.trajectory_setpoint_stale = false;
	}

  research_target_step(next_active,status.trajectory_setpoint_stale);
  research_recovery_transition(next_active,status.trajectory_setpoint_stale,!previous_active&&next_active);
  unsigned skipped=sample_clock.accept(sample);
  previous_active=next_active;
  std::cout<<std::setprecision(17)<<status.trajectory_setpoint_stale<<' '<<capture<<' '<<rec_start<<' '<<skipped<<' '
   <<timestamp_last_trajectory_setpoint<<' '<<_research_recovery_armed<<' '<<_research_target.active;
  for(int i=0;i<2;i++)std::cout<<' '<<_trajectory_setpoint.position[i]<<' '<<_trajectory_setpoint.velocity[i];
  std::cout<<std::endl;
 }
};

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

int main(){Raptor r;uint64_t us,sample;int update,active;
 while(std::cin>>us>>sample>>update>>active>>rtgt>>rrec){trajectory_setpoint_s sp;
  for(int i=0;i<2;i++)std::cin>>r.position[i]>>r.linear_velocity[i];
  r.position[2]=-3.f;
  for(int i=0;i<2;i++)std::cin>>sp.position[i]>>sp.velocity[i];sp.position[2]=-3.f;
  r.tick(us,sample,update,active,sp);
 }
}
