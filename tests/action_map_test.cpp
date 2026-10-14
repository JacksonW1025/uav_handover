#include "../research/state/ActionMap.hpp"
#include <cassert>
#include <cmath>
#include <limits>
using namespace handover_research;
static bool near(float a,float b){return std::fabs(a-b)<1e-6f;}
int main() {
 // Forward map exactly as mc_raptor publishes: control = (action+1)/2 with the Crazyflie->PX4 remap.
 float action[4]={-0.5f,0.1f,0.2f,0.3f},motor[4]{};
 action_to_motor(action,motor);
 assert(near(motor[0],0.25f) && near(motor[1],0.6f) && near(motor[2],0.65f) && near(motor[3],0.55f));
 float back[4]{};ActionConversion r=motor_to_action(motor,back);
 assert(r.valid && r.clipped==0);
 for(unsigned k=0;k<4;k++)assert(near(back[k],action[k]));
 // Out-of-range commands are clipped to [-1,1] and counted per component.
 float wide[4]={1.2f,-0.1f,0.5f,1.0f},clipped[4]{};
 r=motor_to_action(wide,clipped);
 assert(r.valid && r.clipped==2 && clipped[0]==1.f && near(clipped[1],1.f) && clipped[2]==-1.f && near(clipped[3],0.f));
 // A nonfinite motor leaves the output untouched.
 float bad[4]={0.5f,std::numeric_limits<float>::quiet_NaN(),0.5f,0.5f},keep[4]={9,9,9,9};
 r=motor_to_action(bad,keep);
 assert(!r.valid && r.clipped==0 && keep[0]==9 && keep[3]==9);
 bad[1]=std::numeric_limits<float>::infinity();r=motor_to_action(bad,keep);assert(!r.valid && keep[2]==9);
 // Each motor index is used exactly once.
 unsigned seen=0;for(unsigned k=0;k<4;k++)seen|=1u<<MOTOR_OF_ACTION[k];
 assert(seen==0xF);
}
