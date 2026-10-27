#pragma once
// P14H: passive post-EKF full covariance snapshot, bounded process-lifetime mmap.
// No data from this namespace is read by estimation, control, or safeguards.
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <chrono>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
namespace p14h {
struct Header {char magic[8];uint64_t version,bytes,capacity,count,dropped,errors,complete;};
struct Row {uint64_t sequence,wall_ns,native_us,delayed_us,latest_us,flags,nstate,ndof;float state[32],covariance[1024],imu[8];};
static_assert(sizeof(Header)==64,"header");static_assert(sizeof(Row)==4320,"row");
class Buffer {
public:
 explicit Buffer(const char *dir,uint64_t cap=131072){
  const std::string path=std::string(dir)+"/ekf-p14h.bin";fd=::open(path.c_str(),O_RDWR|O_CREAT|O_EXCL,0644);if(fd<0)return;
  bytes=sizeof(Header)+cap*sizeof(Row);if(::ftruncate(fd,static_cast<off_t>(bytes))!=0){::close(fd);fd=-1;return;}
  mem=::mmap(nullptr,bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);if(mem==MAP_FAILED){::close(fd);fd=-1;return;}
  h=static_cast<Header*>(mem);std::memset(h,0,sizeof(*h));std::memcpy(h->magic,"P14HEKF1",8);h->version=1;h->bytes=sizeof(Row);h->capacity=cap;rows=reinterpret_cast<Row*>(h+1);
 }
 bool enabled()const{return h!=nullptr;}
 void Push(Row &r){if(!h)return;const uint64_t k=h->count;if(k>=h->capacity){h->dropped++;return;}r.sequence=k;rows[k]=r;__atomic_store_n(&h->count,k+1,__ATOMIC_RELEASE);}
 // Production instance intentionally outlives workqueues until kernel teardown.
 // Header complete remains0; exited producer + committed prefix/coverage verified.
 ~Buffer(){if(h){::msync(mem,bytes,MS_SYNC);::munmap(mem,bytes);}if(fd>=0)::close(fd);}
 Buffer(const Buffer&)=delete;Buffer&operator=(const Buffer&)=delete;
private:int fd{-1};void *mem{MAP_FAILED};size_t bytes{};Header *h{};Row *rows{};
};
inline uint64_t wall_ns(){return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
template<class V,class P,class IMU>void snapshot(const V &state,const P &covariance,const IMU &imu,uint64_t native,uint64_t delayed,uint64_t flags){
 const char *dir=std::getenv("HANDOVER_P14H_TRACE_DIR");if(!dir)return;
 static auto *buffer=new Buffer(dir);if(!buffer->enabled())return;
 static auto *r=new Row{};r->wall_ns=wall_ns();r->native_us=native;r->delayed_us=delayed;r->latest_us=imu.time_us;r->flags=flags;r->nstate=state.size();r->ndof=covariance.diag().size();
 if(r->nstate>32 || r->ndof>32)return;
 for(unsigned a=0;a<r->nstate;a++)r->state[a]=state(a);
 for(unsigned a=0;a<r->ndof;a++)for(unsigned b=0;b<r->ndof;b++)r->covariance[32*a+b]=covariance(a,b);
 for(unsigned a=0;a<3;a++){r->imu[a]=imu.delta_ang(a);r->imu[a+3]=imu.delta_vel(a);}r->imu[6]=imu.delta_ang_dt;r->imu[7]=imu.delta_vel_dt;buffer->Push(*r);
}
}
