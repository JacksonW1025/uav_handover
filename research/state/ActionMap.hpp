#pragma once
#include <cmath>

namespace handover_research {
// RAPTOR action space <-> actuator_motors, fitted from P1 RAPTOR baseline logs (tools/p2_action_map.py):
// actuator_motors.control[MOTOR_OF_ACTION[k]] = MOTOR_SCALE * action[k] + MOTOR_OFFSET, residual < 1e-7.
// The inverse maps the classic controller's applied motor commands into RAPTOR's action space.
constexpr unsigned MOTOR_OF_ACTION[4]={0,3,1,2};
constexpr float MOTOR_SCALE=0.5f, MOTOR_OFFSET=0.5f;
constexpr float ACTION_MIN=-1.f, ACTION_MAX=1.f;
struct ActionConversion {bool valid{false}; unsigned clipped{0};};
// Writes action only when all four motor values are finite; out-of-range actions are clipped and counted.
inline ActionConversion motor_to_action(const float motor[4], float action[4]) {
    ActionConversion r{};
    for(unsigned k=0;k<4;k++)if(!std::isfinite(motor[MOTOR_OF_ACTION[k]]))return r;
    for(unsigned k=0;k<4;k++) {
        float a=(motor[MOTOR_OF_ACTION[k]]-MOTOR_OFFSET)/MOTOR_SCALE;
        if(a>ACTION_MAX){a=ACTION_MAX;++r.clipped;}
        else if(a<ACTION_MIN){a=ACTION_MIN;++r.clipped;}
        action[k]=a;
    }
    r.valid=true;return r;
}
inline void action_to_motor(const float action[4], float motor[4]) {
    for(unsigned k=0;k<4;k++)motor[MOTOR_OF_ACTION[k]]=MOTOR_SCALE*action[k]+MOTOR_OFFSET;
}
}
