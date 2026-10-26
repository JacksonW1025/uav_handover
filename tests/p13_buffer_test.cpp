#include "P13PhysicsTrace.hh"
#include <cassert>
#include <filesystem>
int main() {
 const char *path="/tmp/p13-buffer-unit.bin";std::remove(path);
 {p13::Buffer<uint64_t> b(path,"P13TEST1",1);b.Push(11);b.Push(22);}
 FILE *f=std::fopen(path,"rb");assert(f);p13::Header h{};uint64_t v=0;
 assert(std::fread(&h,sizeof(h),1,f)==1);assert(std::fread(&v,sizeof(v),1,f)==1);assert(std::fgetc(f)==EOF);std::fclose(f);
 assert(h.count==1 && h.dropped==1 && h.errors==0 && h.complete==1 && v==11);
 // O_EXCL refusal must never overwrite existing evidence.
 {p13::Buffer<uint64_t> b(path,"P13TEST1",1);b.Push(33);}
 f=std::fopen(path,"rb");assert(f);assert(std::fread(&h,sizeof(h),1,f)==1);assert(std::fread(&v,sizeof(v),1,f)==1);std::fclose(f);assert(v==11);
 std::remove(path);std::puts("PASS bounded buffer, overflow count and no overwrite");
}
