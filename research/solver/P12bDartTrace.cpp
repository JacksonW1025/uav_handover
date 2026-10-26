// Passive symbol interposition for installed DART 6.13.2. No solver arguments
// or state are changed. Build against matching distro headers, NDEBUG ABI.
#include <dart/constraint/ServoMotorConstraint.hpp>
#include <dart/constraint/JointConstraint.hpp>
#include <dart/constraint/DantzigBoxedLcpSolver.hpp>
#include <dart/constraint/PgsBoxedLcpSolver.hpp>
#include <dart/dynamics/Joint.hpp>
#include <dart/constraint/BoxedLcpConstraintSolver.hpp>
#include <dart/constraint/ConstrainedGroup.hpp>
#include <dlfcn.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <vector>
#include <algorithm>
#include <unistd.h>
namespace {
template<class F> F next(const char *name) { void *p=dlsym(RTLD_NEXT,name); if(!p){std::fprintf(stderr,"P12B missing symbol %s\n",name);std::abort();} return reinterpret_cast<F>(p); }
uint64_t wall(){timespec t{};clock_gettime(CLOCK_MONOTONIC,&t);return uint64_t(t.tv_sec)*1000000000ULL+uint64_t(t.tv_nsec);}
FILE *output(){static FILE *f=[](){const char *dir=std::getenv("HANDOVER_P12B_SOLVER_TRACE");if(!dir)return static_cast<FILE*>(nullptr);char path[4096];std::snprintf(path,sizeof(path),"%s/dart-solver-%d.bin",dir,int(getpid()));FILE *v=std::fopen(path,"wb");if(!v){std::perror("P12B solver trace");std::abort();}std::setvbuf(v,nullptr,_IOFBF,1048576);return v;}();return f;}
#pragma pack(push,1)
struct Head{uint32_t magic=0x42323150,type=0,bytes=0,version=2;uint64_t step=0,wall_ns=0,sim_us=0;};
struct Servo{Head h;uint64_t constraint=0,joint=0,bptr=0,dim=0,dof=0,actuator_type=0,limits_enforced=0;char name[96]{};double dt=0,cfm=0;uint8_t active[6]{};double command[6]{},free_velocity[6]{},force_lo[6]{},force_hi[6]{},velocity_lo[6]{},velocity_hi[6]{},position[6]{},position_lo[6]{},position_hi[6]{};};
struct Solve{Head h;uint64_t solver=0,bptr=0;int32_t n=0,stride=0,nub=0,kind=0,success=0,early=0;};
struct GroupRow{Head h;uint64_t offset=0,dim=0;char type[96]{};};
struct World{Head h;uint64_t joint=0;char name[96]{};double velocity[6]{};uint64_t dof=0;double time_after=0;};
#pragma pack(pop)
thread_local uint64_t step=0,sim=0,group_offset=0;
thread_local bool group_probe=false;
thread_local std::vector<dart::dynamics::Joint*> joints;
Head header(uint32_t type,uint32_t bytes){Head h;h.type=type;h.bytes=bytes;h.step=step;h.sim_us=sim;h.wall_ns=wall();return h;}
void put(const void *p,size_t n){if(std::fwrite(p,1,n,output())!=n){std::perror("P12B solver write");std::abort();}}
using SolverFn=bool(*)(void*,int,double*,double*,double*,int,double*,double*,int*,bool);
bool solve(void *self,int n,double *A,double *x,double *b,int nub,double *lo,double *hi,int *fi,bool early,int kind,SolverFn real){
 if(!output())return real(self,n,A,x,b,nub,lo,hi,fi,early);
 // dPAD(n) from the exact installed ODE/DART layout. Preserve ALL rows,
 // coupling terms and original arrays before in-place solver permutation.
 int stride=n>1?((n+3)&~3):n;std::vector<double> mat(size_t(n)*stride),rhs(b,b+n),lower(lo,lo+n),upper(hi,hi+n);std::vector<int> findex(fi,fi+n);
 std::copy(A,A+size_t(n)*stride,mat.begin());
 bool ok=real(self,n,A,x,b,nub,lo,hi,fi,early);
 Solve row;row.h=header(2,uint32_t(sizeof(row)+sizeof(double)*(mat.size()+size_t(n)*4)+sizeof(int)*size_t(n)));row.solver=reinterpret_cast<uint64_t>(self);row.bptr=reinterpret_cast<uint64_t>(b);row.n=n;row.stride=stride;row.nub=nub;row.kind=kind;row.success=ok;row.early=early;
 put(&row,sizeof(row));put(mat.data(),mat.size()*sizeof(double));put(rhs.data(),size_t(n)*sizeof(double));put(lower.data(),size_t(n)*sizeof(double));put(upper.data(),size_t(n)*sizeof(double));put(x,size_t(n)*sizeof(double));put(findex.data(),size_t(n)*sizeof(int));return ok;
}
}
namespace dart {namespace constraint {
void BoxedLcpConstraintSolver::solveConstrainedGroup(ConstrainedGroup &group){
 static auto real=next<void(*)(void*,ConstrainedGroup&)>("_ZN4dart10constraint24BoxedLcpConstraintSolver21solveConstrainedGroupERNS0_16ConstrainedGroupE");
 if(output()){
  group_offset=0;group_probe=true;
  for(size_t i=0;i<group.getNumConstraints();++i){auto ptr=group.getConstraint(i);const auto &type=ptr->getType();GroupRow row;row.h=header(4,sizeof(row));row.offset=group_offset;row.dim=ptr->getDimension();std::snprintf(row.type,sizeof(row.type),"%s",type.c_str());put(&row,sizeof(row));group_offset+=row.dim;}
  group_probe=false;
 }
 real(this,group);
}
void JointConstraint::getInformation(ConstraintInfo *info){
 static auto real=next<void(*)(void*,ConstraintInfo*)>("_ZN4dart10constraint15JointConstraint14getInformationEPNS0_14ConstraintInfoE");real(this,info);if(!output())return;
 Servo row;row.h=header(1,sizeof(row));row.constraint=reinterpret_cast<uint64_t>(this);row.joint=reinterpret_cast<uint64_t>(mJoint);row.bptr=reinterpret_cast<uint64_t>(info->b);row.dim=mDim;row.dof=mJoint->getNumDofs();row.actuator_type=uint64_t(mJoint->getActuatorType());row.limits_enforced=mJoint->areLimitsEnforced();row.dt=1.0/info->invTimeStep;row.cfm=getConstraintForceMixing();std::snprintf(row.name,sizeof(row.name),"%s",mJoint->getName().c_str());
 for(size_t i=0;i<std::min<size_t>(row.dof,6);++i){row.active[i]=mActive[i];row.command[i]=mJoint->getCommand(i);row.free_velocity[i]=mJoint->getVelocity(i);row.force_lo[i]=mJoint->getForceLowerLimit(i);row.force_hi[i]=mJoint->getForceUpperLimit(i);row.velocity_lo[i]=mJoint->getVelocityLowerLimit(i);row.velocity_hi[i]=mJoint->getVelocityUpperLimit(i);row.position[i]=mJoint->getPosition(i);row.position_lo[i]=mJoint->getPositionLowerLimit(i);row.position_hi[i]=mJoint->getPositionUpperLimit(i);}
 if(std::find(joints.begin(),joints.end(),mJoint)==joints.end()){joints.push_back(mJoint);}
 put(&row,sizeof(row));
}
bool DantzigBoxedLcpSolver::solve(int n,double *A,double *x,double *b,int nub,double *lo,double *hi,int *fi,bool early){static auto real=next<SolverFn>("_ZN4dart10constraint21DantzigBoxedLcpSolver5solveEiPdS2_S2_iS2_S2_Pib");return ::solve(this,n,A,x,b,nub,lo,hi,fi,early,1,real);}
bool PgsBoxedLcpSolver::solve(int n,double *A,double *x,double *b,int nub,double *lo,double *hi,int *fi,bool early){static auto real=next<SolverFn>("_ZN4dart10constraint17PgsBoxedLcpSolver5solveEiPdS2_S2_iS2_S2_Pib");return ::solve(this,n,A,x,b,nub,lo,hi,fi,early,2,real);}
}}
extern "C" void p12b_world_step(void*,bool) asm("_ZN4dart10simulation5World4stepEb");
extern "C" void p12b_world_step(void *self,bool reset){
 static auto real=next<void(*)(void*,bool)>("_ZN4dart10simulation5World4stepEb");if(!output()){real(self,reset);return;}
 static auto gettime=next<double(*)(const void*)>("_ZNK4dart10simulation5World7getTimeEv");++step;joints.clear();sim=uint64_t(gettime(self)*1000000.0+.5);real(self,reset);
 for(auto *j:joints){World row;row.h=header(3,sizeof(row));row.joint=reinterpret_cast<uint64_t>(j);std::snprintf(row.name,sizeof(row.name),"%s",j->getName().c_str());row.dof=j->getNumDofs();row.time_after=gettime(self);for(size_t i=0;i<std::min<size_t>(row.dof,6);++i)row.velocity[i]=j->getVelocity(i);put(&row,sizeof(row));}
 std::fflush(output());
}
// Verify that the case seed reaches Gazebo's actual RNG setter, not only argv.
extern "C" void p12b_rand_seed(unsigned int) asm("_ZN2gz4math2v74Rand4SeedEj");
extern "C" void p12b_rand_seed(unsigned int value){
 static auto real=next<void(*)(unsigned int)>("_ZN2gz4math2v74Rand4SeedEj");real(value);
 if(output()){Head h=header(6,uint32_t(sizeof(Head)+sizeof(uint64_t)));uint64_t seed=value;put(&h,sizeof(h));put(&seed,sizeof(seed));std::fflush(output());}
}
