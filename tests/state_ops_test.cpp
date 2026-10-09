#include "../research/state/StateOps.hpp"
#include <cassert>
#include <limits>
using namespace handover_research;
int main() {
 StateOps s;float v[3]={.1f,.2f,.3f},limits[3]={1,1,1},zero[3]={},input[3]={.4f,.5f,.6f};
 assert(s.process(RESTORE,false,v,3,limits,zero,input,3)==NO_SNAPSHOT);
 assert(s.process(SNAPSHOT,true,v,3,limits,zero,input,3)==SUCCESS);
 assert(s.process(RESET,true,v,3,limits,zero,input,3)==SUCCESS && v[2]==0);
 assert(s.process(RESTORE,true,v,3,limits,zero,input,3)==ACTIVE_WRITE && v[2]==0);
 assert(s.process(RESTORE,false,v,3,limits,zero,input,3)==SUCCESS && v[2]==.3f);
 assert(s.process(INJECT,false,v,3,limits,zero,input,2)==DIMENSION && v[2]==.3f);
 input[0]=std::numeric_limits<float>::quiet_NaN();
 assert(s.process(INJECT,false,v,3,limits,zero,input,3)==NONFINITE && v[0]==.1f);
 input[0]=2;assert(s.process(INJECT,false,v,3,limits,zero,input,3)==BOUNDS && v[0]==.1f);
 input[0]=.4f;assert(s.process(INJECT,false,v,3,limits,zero,input,3)==SUCCESS && v[0]==.4f);
 assert(s.process(HOLD,true,v,3,limits,zero,input,3)==SUCCESS && s.holding);
 assert(s.process(RESET,true,v,3,limits,zero,input,3)==SUCCESS && s.held[0]==0);
 assert(s.process(RELEASE,true,v,3,limits,zero,input,3)==SUCCESS && !s.holding);
 assert(s.process(99,false,v,3,limits,zero,input,3)==UNKNOWN);
 assert(s.process(READ,false,v,33,limits,zero,input,3)==DIMENSION);
}
