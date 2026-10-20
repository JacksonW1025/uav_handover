#include "../research/state/RecoveryTarget.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <limits>
using namespace handover_research;
static bool near(double a,double b,double tol) {return std::fabs(a-b)<=tol;}
int main() {
 const uint64_t t0=61234000ULL;
 RecoveryTarget r;
 const float vp[3]={1.0f,2.0f,-3.0f},vv[3]={0.5f,0.0f,0.2f};
 // Rate 0 (the default) or invalid input never starts.
 assert(!r.start(t0,vp,vv,0.f) && !r.active);
 assert(!r.start(t0,vp,vv,-1.f) && !r.start(t0,vp,vv,std::numeric_limits<float>::quiet_NaN()));
 const float bad[3]={std::numeric_limits<float>::infinity(),0.f,0.f};
 assert(!r.start(t0,bad,vv,2.f) && !r.active);
 // An inactive target is a no-op.
 {float sp[2]={0,0},sv[2]={0,0};RecoveryStep s=r.step(t0,sp,sv);assert(!s.converged && s.dt==0. && !r.active);}
 // Start = vehicle state; the start cycle (same sample) does not move the target.
 assert(r.start(t0,vp,vv,2.f) && r.active);
 float sp[2]={5.f,2.f},sv[2]={2.f,0.f};
 RecoveryStep s=r.step(t0,sp,sv);
 assert(s.dt==0. && near(r.p[0],1.,1e-7) && near(r.v[0],.5,1e-7) && r.active);
 // Far behind: the acceleration is limited to the rate (horizontal norm), direction kept.
 const double ax=1.5*1.5*4.+3.*1.5,ay=0.;
 assert(near(s.acc_unlimited,std::hypot(ax,ay),1e-9) && s.limited && near(std::hypot(s.acc[0],s.acc[1]),2.,1e-12) && near(s.acc[1],0.,1e-12));
 // Semi-implicit Euler with dt from the sample time; repeated or older samples give dt 0; dt capped at 50 ms.
 s=r.step(t0+4000,sp,sv);
 assert(near(s.dt,.004,1e-12) && near(r.v[0],.5+2.*.004,1e-12) && near(r.p[0],1.+(.5+.008)*.004,1e-12));
 const double p_keep=r.p[0];
 s=r.step(t0+4000,sp,sv);assert(s.dt==0. && near(r.p[0],p_keep,1e-15));
 s=r.step(t0,sp,sv);assert(s.dt==0. && near(r.p[0],p_keep,1e-15));
 s=r.step(t0+1004000,sp,sv);assert(near(s.dt,.05,1e-15));
 // Below the limit the law is unscaled.
 {RecoveryTarget q;const float qp[3]={0,0,0},qv[3]={0,0,0};assert(q.start(t0,qp,qv,10.f));
  const float sp2[2]={.1f,-.2f},sv2[2]={.05f,0.f};RecoveryStep k=q.step(t0+4000,sp2,sv2);
  assert(!k.limited && near(k.acc[0],2.25*double(.1f)+3.*double(.05f),1e-9) && near(k.acc[1],2.25*double(-.2f),1e-9));}
 // Closed loop against a setpoint moving at 2 m/s, 3 m behind and at rest: converges (both differences < 0.02),
 // never exceeds the rate, and ends with active=false exactly once.
 {
  RecoveryTarget q;const float qp[3]={0,0,-3},qv[3]={0,0,0};assert(q.start(t0,qp,qv,2.f));
  double tmax=0;bool ended=false;double maxacc=0,overshoot=-1e9;
  for(uint64_t dt=0;dt<30000000;dt+=4000) {
   const double t=dt*1e-6;const float spp[2]={float(3.+2.*t),0.f},spv[2]={2.f,0.f};
   RecoveryStep k=q.step(t0+dt,spp,spv);maxacc=std::fmax(maxacc,std::hypot(k.acc[0],k.acc[1]));
   if(q.active)overshoot=std::fmax(overshoot,q.p[0]-double(spp[0]));
   if(k.converged) {ended=true;tmax=t;assert(k.position_difference<.02 && k.velocity_difference<.02);break;}
  }
  assert(ended && !q.active && maxacc<=2.+1e-9);
  std::printf("closed loop: 3 m behind at 2 m/s, rate 2: converged after %.3f s, max overshoot %.3f m\n",tmax,overshoot);
 }
 // Vertical and yaw are not part of the virtual target (only horizontal state is stored).
 static_assert(sizeof(RecoveryTarget::p)==2*sizeof(double),"horizontal only");
 std::printf("recovery_target_test passed\n");
 return 0;
}
