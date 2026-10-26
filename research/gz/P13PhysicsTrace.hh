// P13 passive same-physics-step records. No callback disk writes after Configure.
#ifndef HANDOVER_P13_PHYSICS_TRACE_HH
#define HANDOVER_P13_PHYSICS_TRACE_HH
#include <array>
#include <memory>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <fcntl.h>
#include <unistd.h>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/Inertial.hh>
namespace p13 {
struct Header { char magic[8]; uint64_t version, bytes, capacity, count, dropped, errors, complete; };
static_assert(sizeof(Header)==64,"P13 header");
template<class T> class Buffer {
 public:
  Buffer(const std::string &path,const char *magic,size_t capacity):cap(capacity),data(new T[capacity]()) {
    std::memcpy(h.magic,magic,8);h.version=1;h.bytes=sizeof(T);h.capacity=cap;
    int fd=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL,0644);
    if(fd<0){h.errors++;return;}file=fdopen(fd,"wb");if(!file){::close(fd);h.errors++;return;}
    if(std::fwrite(&h,sizeof(h),1,file)!=1)h.errors++;
    std::fflush(file); // Initial incomplete header is evidence if process dies.
  }
  void Push(const T &r){if(h.count<cap)data[h.count++]=r;else h.dropped++;}
  ~Buffer(){if(file){h.complete=1;if(std::fseek(file,0,SEEK_SET)!=0)h.errors++;
    if(std::fwrite(&h,sizeof(h),1,file)!=1)h.errors++;
    if(std::fwrite(data.get(),sizeof(T),h.count,file)!=h.count)h.errors++;
    // Rewrite header after data so an IO error cannot be hidden by stale counts.
    if(std::fseek(file,0,SEEK_SET)==0)std::fwrite(&h,sizeof(h),1,file);
    std::fclose(file);}}
 private: size_t cap;std::unique_ptr<T[]> data;FILE *file{nullptr};Header h{};
};
struct Body {
 uint64_t step,sim_ns,dt_ns,wall_ns,phase,valid;
 double origin_p[3],origin_q[4],base_p[3],base_q[4],base_v[3],base_omega[3],com_p[3],com_v[3],mass;
 double link_com_p[5][3],link_com_v[5][3],link_mass[5];
};
struct Rotor {
 uint64_t step,sim_ns,dt_ns,wall_ns,sample_us,valid;
 double command,filter_before,filter_after,joint,thrust;
 double p[3],q[4],v[3],omega[3],axis[3],wind[3],drag[3],parent_torque[3];
};
static_assert(sizeof(Body)==544,"P13 body layout");
static_assert(sizeof(Rotor)==288,"P13 rotor layout");
inline void Vec(double *x,const gz::math::Vector3d &v){x[0]=v.X();x[1]=v.Y();x[2]=v.Z();}
inline void Quat(double *x,const gz::math::Quaterniond &q){x[0]=q.W();x[1]=q.X();x[2]=q.Y();x[3]=q.Z();}
class Trace {
 public:
 Trace(const gz::sim::Model &_model,int _motor,const std::string &dir):model(_model),motor(_motor) {
  rotor.reset(new Buffer<Rotor>(dir+"/physics-p13-rotor-"+std::to_string(motor)+".bin","P13ROTR1",65536));
  if(motor==0)body.reset(new Buffer<Body>(dir+"/physics-p13-body.bin","P13BODY1",131072));
 }
 void Enable(gz::sim::EntityComponentManager &ecm) {
  if(!body)return;
  for(int i=0;i<5;i++) {auto e=model.LinkByName(ecm,i==0?"base_link":"rotor_"+std::to_string(i-1));
   if(e!=gz::sim::kNullEntity){gz::sim::Link l(e);l.EnableVelocityChecks(ecm);}}
 }
 void Sample(const gz::sim::UpdateInfo &info,const gz::sim::EntityComponentManager &ecm,uint64_t phase,uint64_t wall) {
  if(!body || info.paused)return;
  Body r{};r.step=info.iterations;r.sim_ns=std::chrono::duration_cast<std::chrono::nanoseconds>(info.simTime).count();
  r.dt_ns=std::chrono::duration_cast<std::chrono::nanoseconds>(info.dt).count();r.wall_ns=wall;r.phase=phase;
  auto origin=gz::sim::worldPose(model.Entity(),ecm);Vec(r.origin_p,origin.Pos());Quat(r.origin_q,origin.Rot());
  gz::math::Vector3d cp(0,0,0),cv(0,0,0);
  for(int i=0;i<5;i++) {
   auto e=model.LinkByName(ecm,i==0?"base_link":"rotor_"+std::to_string(i-1));if(e==gz::sim::kNullEntity)continue;
   gz::sim::Link l(e);auto inertia=ecm.Component<gz::sim::components::Inertial>(e);
   auto p=l.WorldInertialPose(ecm);if(!inertia || !p)continue;
   auto v=l.WorldLinearVelocity(ecm,inertia->Data().Pose().Pos());if(!v)continue;
   double m=inertia->Data().MassMatrix().Mass();r.link_mass[i]=m;Vec(r.link_com_p[i],p->Pos());Vec(r.link_com_v[i],*v);
   r.mass+=m;cp+=m*p->Pos();cv+=m*(*v);r.valid|=uint64_t(1)<<i;
   if(i==0) {auto bp=l.WorldPose(ecm);auto bv=l.WorldLinearVelocity(ecm);auto w=l.WorldAngularVelocity(ecm);
    if(bp && bv && w){Vec(r.base_p,bp->Pos());Quat(r.base_q,bp->Rot());Vec(r.base_v,*bv);Vec(r.base_omega,*w);r.valid|=32;}}
  }
  if(r.mass>0){Vec(r.com_p,cp/r.mass);Vec(r.com_v,cv/r.mass);}body->Push(r);
 }
 void Motor(const Rotor &r){rotor->Push(r);}
 private:gz::sim::Model model;int motor;std::unique_ptr<Buffer<Body>> body;std::unique_ptr<Buffer<Rotor>> rotor;
};
}
#endif
