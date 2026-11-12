#pragma once
// Passive bounded mmap recorder: no per-sample filesystem calls after opening.
// One producer per file. Count commits after payload; abnormal exit retains
// prefix with complete=0. Never read by control/estimation code.
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <chrono>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
namespace p14r {
// Full configured run budget300s, conservative maxima: core1000/s,
// fusion500/s, gyro250/s. Sparse mappings touch committed rows only.
constexpr uint64_t CORE_CAPACITY=524288,FUSION_CAPACITY=262144,GYRO_CAPACITY=131072;
struct Header {char magic[8];uint64_t version,bytes,capacity,count,dropped,errors,complete;};
static_assert(sizeof(Header)==64,"header");
struct Core {uint64_t wall_ns,native_us,sample_us,kind,sequence;float data[128];uint64_t ids[16];double geo[8];};
struct Fusion {Core core;uint64_t time[64],vertical_time[64];float state[64][10],vertical[64][3];};
inline uint64_t wall_ns(){return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
template<class T> class Buffer {
 public:
 Buffer(const char *name,const char *magic,uint64_t capacity){
  const char *dir=std::getenv("HANDOVER_P14R_TRACE_DIR");if(!dir)return;
  std::string path=std::string(dir)+"/"+name;fd=::open(path.c_str(),O_RDWR|O_CREAT|O_EXCL,0644);if(fd<0)return;
  length=sizeof(Header)+capacity*sizeof(T);
  if(::ftruncate(fd,static_cast<off_t>(length))!=0){::close(fd);fd=-1;return;}
  memory=::mmap(nullptr,length,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
  if(memory==MAP_FAILED){::close(fd);fd=-1;return;}
  h=static_cast<Header*>(memory);std::memset(h,0,sizeof(*h));std::memcpy(h->magic,magic,8);h->version=1;h->bytes=sizeof(T);h->capacity=capacity;
  data=reinterpret_cast<T*>(h+1);
 }
 bool enabled() const{return h!=nullptr;}
 void Push(T value){if(!h)return;uint64_t k=h->count;if(k>=h->capacity){h->dropped++;return;}value_sequence(value,k);data[k]=value;__atomic_store_n(&h->count,k+1,__ATOMIC_RELEASE);}
 ~Buffer(){
  if(!h)return;
  if(::msync(memory,length,MS_SYNC)!=0)h->errors++;
  h->complete=1;
  if(::msync(memory,sizeof(Header),MS_SYNC)!=0)h->errors++;
  if(::ftruncate(fd,static_cast<off_t>(sizeof(Header)+h->count*sizeof(T)))!=0)h->errors++;
  if(::close(fd)!=0)h->errors++;
  if(::msync(memory,sizeof(Header),MS_SYNC)!=0)h->errors++;
  ::munmap(memory,length);
 }
 Buffer(const Buffer&)=delete;Buffer&operator=(const Buffer&)=delete;
 private:
 static void value_sequence(Core &v,uint64_t n){v.sequence=n;}
 static void value_sequence(Fusion &v,uint64_t n){v.core.sequence=n;}
 int fd{-1};void *memory{MAP_FAILED};size_t length{};Header *h{nullptr};T *data{nullptr};
};
}
