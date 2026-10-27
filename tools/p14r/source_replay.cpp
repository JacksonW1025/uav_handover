// Known-input diagnostic against the actual OutputPredictor implementation.
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <vector>
#include <fstream>
#include <iostream>
#include <algorithm>
#include <map>
#include <matrix/math.hpp>
#define private public
#include "output_predictor.h"
#undef private
#include "P14RBuffer.hpp"
using matrix::Quatf;using matrix::Vector3f;
LatLonAlt geo(const double *x){LatLonAlt g;g._latitude_rad=x[0];g._longitude_rad=x[1];g._altitude=static_cast<float>(x[2]);return g;}
void load(OutputPredictor &o,const p14r::Core &r,const p14r::Fusion *f){
 const float *d=r.data;o._output_new.quat_nominal=Quatf(d);o._output_new.vel=Vector3f(d+4);o._output_new.pos=Vector3f(d+7);o._output_new.time_us=r.ids[10];
 o._output_vert_new.time_us=r.ids[11];o._output_vert_new.vert_vel=d[10];o._output_vert_new.vert_vel_integ=d[11];o._output_vert_new.dt=d[12];
 o._gyro_bias=Vector3f(d+13);o._accel_bias=Vector3f(d+16);o._delta_angle_corr=Vector3f(d+19);o._vel_err_integ=Vector3f(d+22);o._pos_err_integ=Vector3f(d+25);o._vel_imu_rel_body_ned=Vector3f(d+28);o._delta_vel_sum=Vector3f(d+31);o._delta_vel_dt=d[34];o._dt_update_states_avg=d[35];o._dt_correct_states_avg=d[36];o._vel_tau=d[37];o._pos_tau=d[38];o._gravity=d[39];o._imu_pos_body=Vector3f(d+40);o._output_tracking_error=Vector3f(d+43);o._unaided_yaw=d[46];o._delta_angle_sum=Quatf(d+47);o._delta_angle_sum_dt=d[51];
 for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)o._R_to_earth_now(a,b)=d[52+3*a+b];o._global_ref=geo(r.geo);o._time_last_update_states_us=r.ids[0];o._time_last_correct_states_us=r.ids[1];
 if(f){o._output_buffer.allocate(r.ids[2]);o._output_vert_buffer.allocate(r.ids[6]);for(unsigned j=0;j<r.ids[2];j++){auto &x=o._output_buffer[j];x.time_us=f->time[j];x.quat_nominal=Quatf(f->state[j]);x.vel=Vector3f(f->state[j]+4);x.pos=Vector3f(f->state[j]+7);}for(unsigned j=0;j<r.ids[6];j++){auto &x=o._output_vert_buffer[j];x.time_us=f->vertical_time[j];x.vert_vel=f->vertical[j][0];x.vert_vel_integ=f->vertical[j][1];x.dt=f->vertical[j][2];}o._output_buffer._head=r.ids[4];o._output_buffer._tail=r.ids[5];o._output_buffer._first_write=r.ids[3]==0;o._output_vert_buffer._head=r.ids[8];o._output_vert_buffer._tail=r.ids[9];o._output_vert_buffer._first_write=r.ids[7]==0;}
}
std::vector<float> state(OutputPredictor &o){std::vector<float> x(31);o._output_new.quat_nominal.copyTo(x.data());o._output_new.vel.copyTo(x.data()+4);o._output_new.pos.copyTo(x.data()+7);x[10]=o._output_vert_new.vert_vel;x[11]=o._output_vert_new.vert_vel_integ;x[12]=o._output_vert_new.dt;o._gyro_bias.copyTo(x.data()+13);o._accel_bias.copyTo(x.data()+16);o._delta_angle_corr.copyTo(x.data()+19);o._vel_err_integ.copyTo(x.data()+22);o._pos_err_integ.copyTo(x.data()+25);o._vel_imu_rel_body_ned.copyTo(x.data()+28);return x;}
void apply(OutputPredictor &o,const p14r::Core &r){if(r.kind==1)o.calculateOutputStates(r.sample_us,Vector3f(r.data+64),r.data[70],Vector3f(r.data+67),r.data[71]);else if(r.kind==3)o.correctOutputStates(r.sample_us,Quatf(r.data+64),Vector3f(r.data+68),geo(r.geo+3),Vector3f(r.data+74),Vector3f(r.data+77));}
template<class T>std::vector<T> read(const char *name){std::ifstream f(name,std::ios::binary);p14r::Header h{};f.read(reinterpret_cast<char*>(&h),sizeof(h));if(h.bytes!=sizeof(T))throw 1;std::vector<T> x(h.count);f.read(reinterpret_cast<char*>(x.data()),static_cast<std::streamsize>(sizeof(T)*h.count));return x;}
int main(int argc,char **argv){if(argc!=4)return 2;auto core=read<p14r::Core>(argv[1]);auto fusion=read<p14r::Fusion>(argv[2]);std::map<uint64_t,const p14r::Fusion*> frames;for(const auto &f:fusion)frames[f.core.wall_ns]=&f;double single_calc=0,single_fuse=0,continuous=0;size_t nc=0,nf=0,ncon=0;OutputPredictor one,carried;bool initialized=false;uint64_t first=0,last=0;
 std::ofstream errors(argv[3]);errors<<"sample_us,kind,single_max,continuous_max\n";
 for(size_t j=0;j+1<core.size();j++){const auto &r=core[j];if(r.kind!=1 && r.kind!=3)continue;const auto &post=core[j+1];if(post.kind!=r.kind+1 ||post.sample_us!=r.sample_us)continue;auto f=frames.find(r.wall_ns);bool can=r.kind==1||f!=frames.end();double err=0,ce=-1;
  if(can){load(one,r,r.kind==3?f->second:nullptr);apply(one,r);auto x=state(one);for(size_t k=0;k<x.size();k++)err=std::max(err,std::abs(static_cast<double>(x[k])-post.data[k]));if(r.kind==1){single_calc=std::max(single_calc,err);nc++;}else{single_fuse=std::max(single_fuse,err);nf++;}}
  if(!initialized && r.kind==3 && f!=frames.end() && r.sample_us>=55000000ULL){load(carried,r,f->second);initialized=true;first=r.sample_us;}
  if(initialized){apply(carried,r);auto x=state(carried);ce=0;for(size_t k=0;k<x.size();k++)ce=std::max(ce,std::abs(static_cast<double>(x[k])-post.data[k]));continuous=std::max(continuous,ce);ncon++;last=r.sample_us;}
  errors<<r.sample_us<<","<<r.kind<<","<<(can?err:-1)<<","<<ce<<"\n";
 }
 std::cout<<"{\"single_calc_rows\":"<<nc<<",\"single_calc_max\":"<<single_calc<<",\"single_fusion_rows\":"<<nf<<",\"single_fusion_max\":"<<single_fuse<<",\"continuous_rows\":"<<ncon<<",\"continuous_max\":"<<continuous<<",\"first_sample_us\":"<<first<<",\"last_sample_us\":"<<last<<",\"future_inputs\":\"actual IMU deltas and fused q/v/global position/bias, diagnostic only\"}\n";
 return 0;
}
