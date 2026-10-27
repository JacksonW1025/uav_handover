#include "../research/state/P14RBuffer.hpp"
#include <cassert>
#include <sys/wait.h>
#include <sys/stat.h>
#include <fstream>
#include <iostream>
int main(int argc,char **argv){
 assert(argc==2);::setenv("HANDOVER_P14R_TRACE_DIR",argv[1],1);
 {p14r::Buffer<p14r::Core> b("normal.bin","P14RCORE",2);assert(b.enabled());p14r::Core r{};r.data[0]=42.f;b.Push(r);b.Push(r);b.Push(r);}
 auto read=[&](const char *name){p14r::Header h{};std::ifstream f(std::string(argv[1])+"/"+name,std::ios::binary);f.read(reinterpret_cast<char*>(&h),sizeof(h));return h;};
 auto h=read("normal.bin");assert(h.count==2 && h.dropped==1 && h.errors==0 && h.complete==1);
 pid_t pid=::fork();assert(pid>=0);
 if(pid==0){p14r::Buffer<p14r::Core> b("abnormal.bin","P14RCORE",16);p14r::Core r{};r.data[0]=43.f;for(int i=0;i<10;i++)b.Push(r);::_exit(0);}
 int status=0;::waitpid(pid,&status,0);assert(WIFEXITED(status));h=read("abnormal.bin");assert(h.count==10 && h.complete==0 && h.errors==0);
 std::ifstream f(std::string(argv[1])+"/abnormal.bin",std::ios::binary);f.seekg(sizeof(h));for(uint64_t i=0;i<10;i++){p14r::Core r{};f.read(reinterpret_cast<char*>(&r),sizeof(r));assert(r.sequence==i && r.data[0]>42.f);}
 std::cout<<"PASS normal/overflow/abnormal committed-prefix; sizes "<<sizeof(p14r::Core)<<" "<<sizeof(p14r::Fusion)<<"\n";
}
