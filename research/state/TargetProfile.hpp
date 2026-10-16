#pragma once
#include <cmath>
#include <cstdint>

// P4-01c RAPTOR takeover target (MC_RAPTOR_RTGT, SITL research only). Mode 0 is RAPTOR's original capture: in the
// activation cycle the target is the current position and yaw with zero velocity. Mode 1 (T1) captures the same
// position and yaw in the same cycle, but the target velocity is the current horizontal velocity (vertical 0);
// afterwards the target speed decreases along the captured direction at a fixed deceleration until it is zero, the
// target position is the exact integral of the target velocity, and the target then stays at the end point.
// The profile is a closed-form function of the time since the capture, so it does not depend on the cycle length.
namespace handover_research {
enum TargetMode : int32_t {TARGET_ZERO_VELOCITY=0,TARGET_SPEED_MATCHED=1,TARGET_MODE_MAX=1};
enum TargetPhase : uint8_t {TARGET_PHASE_NONE=0,TARGET_PHASE_HOLD=1,TARGET_PHASE_DECELERATING=2,TARGET_PHASE_STOPPED=3};
struct TargetProfile {
    bool active{false};
    uint64_t t0_us{0};
    double p0[3]{},dir[2]{},speed0{0},decel{0};
    // Starts at time t_us from the captured position and the vehicle velocity; the vertical velocity is ignored.
    // Returns false (profile inactive) for a nonfinite input or a deceleration that is not positive and finite.
    bool start(uint64_t t_us,const float position[3],const float velocity[3],float decel_m_s2) {
        active=false;
        if(!std::isfinite(decel_m_s2) || decel_m_s2<=0.f)return false;
        for(int i=0;i<3;i++)if(!std::isfinite(position[i]) || !std::isfinite(velocity[i]))return false;
        t0_us=t_us;decel=double(decel_m_s2);
        for(int i=0;i<3;i++)p0[i]=double(position[i]);
        speed0=std::hypot(double(velocity[0]),double(velocity[1]));
        dir[0]=speed0>0.?double(velocity[0])/speed0:0.;dir[1]=speed0>0.?double(velocity[1])/speed0:0.;
        active=true;return true;
    }
    double stop_time_s() const {return speed0/decel;}
    double stop_distance_m() const {return speed0*speed0/(2.*decel);}
    // Target position and velocity at t_us (times before the capture evaluate at the capture). Returns the phase.
    uint8_t evaluate(uint64_t t_us,float position[3],float velocity[3]) const {
        if(!active)return TARGET_PHASE_NONE;
        const double t=t_us>t0_us?double(t_us-t0_us)*1e-6:0.,ts=stop_time_s();
        const bool moving=t<ts;
        const double tau=moving?t:ts,speed=moving?speed0-decel*t:0.,distance=speed0*tau-.5*decel*tau*tau;
        for(int i=0;i<2;i++) {position[i]=float(p0[i]+dir[i]*distance);velocity[i]=float(dir[i]*speed);}
        position[2]=float(p0[2]);velocity[2]=0.f;
        return moving?TARGET_PHASE_DECELERATING:TARGET_PHASE_STOPPED;
    }
};
}
