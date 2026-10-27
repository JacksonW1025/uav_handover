#include "../research/state/P14HSnapshot.hpp"
#include <cassert>
#include <cstring>
#include <sys/stat.h>
#include <fstream>
int main(int argc,char **argv){assert(argc==3);{
 p14h::Buffer b(argv[1],3);assert(b.enabled());p14h::Row r{};r.nstate=25;r.ndof=24;
 for(int j=0;j<5;j++){r.latest_us=static_cast<uint64_t>(4000*j);r.covariance[33]=1.0f;b.Push(r);}
 if(std::strcmp(argv[2],"abnormal")==0)_exit(0);
 }
 return 0;
}
