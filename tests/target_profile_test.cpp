#include "../research/state/TargetProfile.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <initializer_list>
#include <limits>
using namespace handover_research;
static bool near(double a,double b,double tol) {return std::fabs(a-b)<=tol;}
int main() {
 // Large simulation timestamps (about 1 min into a run) as in SITL.
 const uint64_t t0=57868000ULL;
 const float p[3]={4.996f,-0.027f,-3.061f},v[3]={1.8f,-0.6f,0.35f};
 float q[3],w[3];
 TargetProfile tp;
 assert(tp.evaluate(t0,q,w)==TARGET_PHASE_NONE);
 assert(tp.start(t0,p,v,2.f) && tp.active);
 const double s0=std::hypot(double(v[0]),double(v[1])),ux=v[0]/s0,uy=v[1]/s0;
 assert(near(tp.stop_time_s(),s0/2.,1e-12) && near(tp.stop_distance_m(),s0*s0/4.,1e-12));
 // Capture cycle: target = captured position, horizontal velocity = vehicle velocity, vertical velocity 0.
 assert(tp.evaluate(t0,q,w)==TARGET_PHASE_DECELERATING);
 for(int i=0;i<3;i++)assert(q[i]==p[i]);
 assert(near(w[0],1.8,1e-6) && near(w[1],-0.6,1e-6) && w[2]==0.f);
 // A time before the capture evaluates at the capture.
 assert(tp.evaluate(t0-4000,q,w)==TARGET_PHASE_DECELERATING && q[0]==p[0] && near(w[0],1.8,1e-6));
 // Fixed deceleration along the captured direction; altitude unchanged.
 for(uint64_t dt=4000;dt<1000000;dt+=4000) {
  const double t=dt*1e-6;tp.evaluate(t0+dt,q,w);
  const double speed=t<s0/2.?s0-2.*t:0.,d=t<s0/2.?s0*t-t*t:s0*s0/4.;
  assert(near(std::hypot(double(w[0]),double(w[1])),speed,1e-5));
  if(speed>0.)assert(near(w[0]*uy-w[1]*ux,0.,1e-6) && w[0]*ux+w[1]*uy>0.f);
  assert(near(q[0],p[0]+ux*d,1e-5) && near(q[1],p[1]+uy*d,1e-5) && q[2]==p[2] && w[2]==0.f);
 }
 // The position is the integral of the velocity: a 4 ms trapezoid sum over the profile reproduces it.
 {
  double x=p[0],y=p[1];float a[3],b[3],qa[3],qb[3];
  for(uint64_t dt=0;dt<2000000;dt+=4000) {tp.evaluate(t0+dt,qa,a);tp.evaluate(t0+dt+4000,qb,b);x+=.002*(a[0]+b[0]);y+=.002*(a[1]+b[1]);}
  tp.evaluate(t0+2000000,q,w);assert(near(x,q[0],1e-4) && near(y,q[1],1e-4));
 }
 // After the stop: zero velocity and the end point, forever.
 assert(tp.evaluate(t0+3600000000ULL,q,w)==TARGET_PHASE_STOPPED);
 assert(w[0]==0.f && w[1]==0.f && w[2]==0.f);
 assert(near(q[0],p[0]+ux*s0*s0/4.,1e-5) && near(q[1],p[1]+uy*s0*s0/4.,1e-5) && q[2]==p[2]);
 // Speed-dependent stop distance v^2/(2a) at the P4-01c levels and the default deceleration.
 for(float speed:{1.f,1.5f,2.f,3.f}) {
  const float vel[3]={0.f,speed,0.f};TargetProfile t;assert(t.start(0,p,vel,2.f));
  t.evaluate(10000000ULL,q,w);assert(near(q[1]-p[1],speed*speed/4.,1e-5) && q[0]==p[0]);
 }
 // Zero horizontal speed: the target is the original hold (T0 equivalent).
 {const float still[3]={0.f,0.f,-0.4f};TargetProfile t;assert(t.start(t0,p,still,2.f));
  assert(t.evaluate(t0,q,w)==TARGET_PHASE_STOPPED);for(int i=0;i<3;i++){assert(q[i]==p[i]);assert(w[i]==0.f);}}
 // Invalid deceleration or nonfinite inputs leave the profile inactive.
 const float nan=std::numeric_limits<float>::quiet_NaN(),inf=std::numeric_limits<float>::infinity();
 for(float d:{0.f,-1.f,nan,inf}) {TargetProfile t;assert(!t.start(t0,p,v,d) && !t.active && t.evaluate(t0,q,w)==TARGET_PHASE_NONE);}
 {const float bad[3]={nan,0.f,0.f};TargetProfile t;assert(!t.start(t0,p,bad,2.f) && !t.active);assert(!t.start(t0,bad,v,2.f) && !t.active);}
 // A restart replaces the previous profile completely.
 {TargetProfile t;assert(t.start(t0,p,v,2.f));const float vel[3]={-1.f,0.f,0.f};assert(t.start(t0+1000000,p,vel,4.f));
  t.evaluate(t0+1000000+100000,q,w);assert(near(w[0],-0.6,1e-6) && w[1]==0.f && near(q[0],p[0]-(0.1-0.02),1e-6));}
 std::puts("target_profile_test passed");
 return 0;
}
