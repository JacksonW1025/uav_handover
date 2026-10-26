#pragma once
#include <cmath>
#include <cstdint>

// P7 rate-limited recovery (MC_RAPTOR_RREC, SITL research only). When RAPTOR's external trajectory_setpoint becomes
// fresh again after an in-flight setpoint-timeout capture, the target the network observes does not jump back to the
// setpoint. A virtual target starts at the vehicle's current horizontal position and velocity and, every control cycle,
//   acc = w^2 (sp_pos - vt_pos) + 2 w (sp_vel - vt_vel),  w = 1.5 rad/s,
// scaled down to |acc| = rate (horizontal norm) when larger; then vt_vel += acc dt, vt_pos += vt_vel dt (dt from the
// cycle's gyro sample time). It ends (the network sees the setpoint directly again) once the horizontal position and
// velocity differences to the setpoint are both below 0.02 (m, m/s). Same definition as R(a_r) of the project's l2f
// experiments. The vertical axis and the yaw always use the setpoint.
namespace handover_research {
struct RecoveryStep {
    double dt{0},acc[2]{},acc_unlimited{0},position_difference{0},velocity_difference{0};
    bool limited{false},converged{false};
};
struct RecoveryTarget {
    static constexpr double OMEGA=1.5,EXIT_POSITION_M=0.02,EXIT_VELOCITY_M_S=0.02,MAX_DT_S=0.05;
    bool active{false};
    uint64_t start_us{0},last_us{0};
    double rate{0},p[2]{},v[2]{};
    // Starts at time t_us from the vehicle state (horizontal components). Returns false (inactive) for a rate that is
    // not positive and finite or a nonfinite state.
    bool start(uint64_t t_us,const float position[3],const float velocity[3],float rate_m_s2) {
        active=false;
        if(!std::isfinite(rate_m_s2) || rate_m_s2<=0.f)return false;
        for(int i=0;i<2;i++)if(!std::isfinite(position[i]) || !std::isfinite(velocity[i]))return false;
        for(int i=0;i<2;i++) {p[i]=double(position[i]);v[i]=double(velocity[i]);}
        rate=double(rate_m_s2);start_us=t_us;last_us=t_us;active=true;return true;
    }
    // One control cycle at t_us against the setpoint in force (horizontal position and velocity). dt = time since the
    // previous step (0 in the start cycle and for a repeated or older sample, at most MAX_DT_S). Ends the recovery
    // (active=false, converged) when both differences are below the exit thresholds after the update.
    RecoveryStep step(uint64_t t_us,const float sp_position[2],const float sp_velocity[2]) {
        RecoveryStep s{};
        if(!active)return s;
        if(t_us>last_us) {s.dt=std::fmin(double(t_us-last_us)*1e-6,MAX_DT_S);last_us=t_us;}
        double a[2];
        for(int i=0;i<2;i++)a[i]=OMEGA*OMEGA*(double(sp_position[i])-p[i])+2.*OMEGA*(double(sp_velocity[i])-v[i]);
        s.acc_unlimited=std::hypot(a[0],a[1]);
        if(s.acc_unlimited>rate) {const double k=rate/s.acc_unlimited;a[0]*=k;a[1]*=k;s.limited=true;}
        for(int i=0;i<2;i++) {v[i]+=a[i]*s.dt;p[i]+=v[i]*s.dt;s.acc[i]=a[i];}
        s.position_difference=std::hypot(double(sp_position[0])-p[0],double(sp_position[1])-p[1]);
        s.velocity_difference=std::hypot(double(sp_velocity[0])-v[0],double(sp_velocity[1])-v[1]);
        s.converged=s.position_difference<EXIT_POSITION_M && s.velocity_difference<EXIT_VELOCITY_M_S;
        if(s.converged)active=false;
        return s;
    }
};
}
