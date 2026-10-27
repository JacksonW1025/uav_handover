// Source decision-only projection of ImuDownSampler (payload integration does
// not affect its return predicate). Compiled float operations, not host-double.
#include <cmath>
#include <algorithm>
#include <cstdint>
struct State{float avg,acc,target,minimum;int32_t count,required;uint64_t processed;};
static void reset(State &s,int target_us){float t=std::clamp(target_us,1000,100000)*1.e-6f;s.acc=0.f;s.count=0;s.required=std::max(static_cast<int>(roundf(t/s.avg)),1);s.target=s.required*s.avg;s.minimum=std::max(s.avg*(s.required-1.f),s.avg*.5f);}
extern "C" {
void p14h_init(State *s,int target_us){*s={};s->avg=.005f;reset(*s,target_us);}
int p14h_push(State *s,float dt,int target_us){s->avg=.9f*s->avg+.1f*dt;s->acc+=dt;s->count++;s->processed++;bool yield=(s->count>=s->required && s->acc>s->minimum)||s->acc>s->target;if(yield)reset(*s,target_us);return yield;}
}
