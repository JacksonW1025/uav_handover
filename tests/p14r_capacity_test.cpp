#include "../research/state/P14RBuffer.hpp"
#include <cassert>
#include <iostream>
int main(int argc,char **argv){assert(argc==2);::setenv("HANDOVER_P14R_TRACE_DIR",argv[1],1);auto *a=new p14r::Buffer<p14r::Core>("full-core.bin","P14RCORE",p14r::CORE_CAPACITY);auto *b=new p14r::Buffer<p14r::Fusion>("full-fusion.bin","P14RFUS1",p14r::FUSION_CAPACITY);auto *c=new p14r::Buffer<p14r::Core>("full-gyro.bin","P14RGYRO",p14r::GYRO_CAPACITY);p14r::Core x{};p14r::Fusion y{};assert(a->enabled()&&b->enabled()&&c->enabled());for(int k=0;k<300000;k++)a->Push(x);for(int k=0;k<150000;k++)b->Push(y);for(int k=0;k<75000;k++)c->Push(x);std::cout<<"COMMITTED 300s at max1000/500/250Hz, process-lifetime exit\n";return 0;}
