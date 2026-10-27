// Exact OutputPredictor source ABI for causal autonomous model and diagnostics.
#define main p14r_unused_diagnostic_main
#include "source_replay.cpp"
#undef main
extern "C" {
void *p14r_create(const p14r::Fusion *f){auto *o=new OutputPredictor;load(*o,f->core,f);return o;}
void p14r_free(void *p){delete static_cast<OutputPredictor*>(p);}
void p14r_advance(void *p,uint64_t sample,const float *da,const float *dv,float dt){auto *o=static_cast<OutputPredictor*>(p);o->calculateOutputStates(sample,Vector3f(da),dt,Vector3f(dv),dt);}
void p14r_fuse(void *p,uint64_t sample,const float *q,const float *v,const double *g,const float *bg,const float *ba){auto *o=static_cast<OutputPredictor*>(p);o->correctOutputStates(sample,Quatf(q),Vector3f(v),geo(g),Vector3f(bg),Vector3f(ba));}
void p14r_outputs(void *p,float *q,float *v,double *g,float *correction){auto *o=static_cast<OutputPredictor*>(p);o->getQuaternion().copyTo(q);o->getVelocity().copyTo(v);auto pos=o->getLatLonAlt();g[0]=pos.latitude_rad();g[1]=pos.longitude_rad();g[2]=static_cast<double>(pos.altitude());o->_delta_angle_corr.copyTo(correction);}
void p14r_fields(void *p,float *x){auto *o=static_cast<OutputPredictor*>(p);auto y=state(*o);std::memcpy(x,y.data(),y.size()*sizeof(float));}
void p14r_add_ned(const double *g,const float *d,double *out){auto y=geo(g)+Vector3f(d);out[0]=y.latitude_rad();out[1]=y.longitude_rad();out[2]=static_cast<double>(y.altitude());}
void p14r_sub_geo(const double *g,const double *anchor,float *out){auto y=geo(g)-geo(anchor);y.copyTo(out);}
void p14r_project(const double *g,const double *anchor,float *out){MapProjection projection;projection.initReference(math::degrees(anchor[0]),math::degrees(anchor[1]));projection.project(math::degrees(g[0]),math::degrees(g[1]),out[0],out[1]);out[2]=-static_cast<float>(g[2]-anchor[2]);}
void p14r_snapshot(void *p,p14r::Fusion *f){
 auto &o=*static_cast<OutputPredictor*>(p);std::memset(f,0,sizeof(*f));auto &r=f->core;auto x=state(o);std::memcpy(r.data,x.data(),31*sizeof(float));
 o._delta_vel_sum.copyTo(r.data+31);r.data[34]=o._delta_vel_dt;r.data[35]=o._dt_update_states_avg;r.data[36]=o._dt_correct_states_avg;r.data[37]=o._vel_tau;r.data[38]=o._pos_tau;r.data[39]=o._gravity;o._imu_pos_body.copyTo(r.data+40);o._output_tracking_error.copyTo(r.data+43);r.data[46]=o._unaided_yaw;o._delta_angle_sum.copyTo(r.data+47);r.data[51]=o._delta_angle_sum_dt;
 for(unsigned a=0;a<3;a++)for(unsigned b=0;b<3;b++)r.data[52+3*a+b]=o._R_to_earth_now(a,b);
 r.ids[0]=o._time_last_update_states_us;r.ids[1]=o._time_last_correct_states_us;r.ids[2]=o._output_buffer.get_length();r.ids[3]=o._output_buffer.entries();r.ids[4]=o._output_buffer._head;r.ids[5]=o._output_buffer._tail;r.ids[6]=o._output_vert_buffer.get_length();r.ids[7]=o._output_vert_buffer.entries();r.ids[8]=o._output_vert_buffer._head;r.ids[9]=o._output_vert_buffer._tail;r.ids[10]=o._output_new.time_us;r.ids[11]=o._output_vert_new.time_us;r.geo[0]=o._global_ref.latitude_rad();r.geo[1]=o._global_ref.longitude_rad();r.geo[2]=o._global_ref.altitude();
 for(unsigned j=0;j<r.ids[2];j++){const auto &b=o._output_buffer[j];f->time[j]=b.time_us;b.quat_nominal.copyTo(f->state[j]);b.vel.copyTo(f->state[j]+4);b.pos.copyTo(f->state[j]+7);}
 for(unsigned j=0;j<r.ids[6];j++){const auto &b=o._output_vert_buffer[j];f->vertical_time[j]=b.time_us;f->vertical[j][0]=b.vert_vel;f->vertical[j][1]=b.vert_vel_integ;f->vertical[j][2]=b.dt;}
}
}
