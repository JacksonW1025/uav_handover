// Actual process-lifetime recorder, producer deliberately alive at main return.
#include "../research/state/P14RBuffer.hpp"
#include <thread>
#include <atomic>
#include <cassert>
#include <unistd.h>
std::atomic<bool> ready{false};
void produce(){static auto *buf=new p14r::Buffer<p14r::Core>("lifetime.bin","P14RCORE",4096);p14r::Core v{};for(;;){v.data[0]=1.f;buf->Push(v);ready.store(true);::usleep(100);}}
int main(int argc,char**argv){assert(argc==2);::setenv("HANDOVER_P14R_TRACE_DIR",argv[1],1);std::thread(produce).detach();while(!ready.load())::usleep(100);::usleep(2000);return 0;}
