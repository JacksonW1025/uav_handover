// Exact OutputPredictor source ABI for causal autonomous model and diagnostics.
#define main p14r_unused_diagnostic_main
#include "source-replay-v1.cpp"
#undef main
extern "C" {
void *p14r_create(const p14r::Fusion *f){auto *o=new OutputPredictor;load(*o,f->core,f);return o;}
void p14r_free(void *p){delete static_cast<OutputPredictor*>(p);}
void p14r_advance(void *p,uint64_t sample,const float *da,const float *dv,float dt){auto *o=static_cast<OutputPredictor*>(p);o->calculateOutputStates(sample,Vector3f(da),dt,Vector3f(dv),dt);}
void p14r_fuse(void *p,uint64_t sample,const float *q,const float *v,const double *g,const float *bg,const float *ba){auto *o=static_cast<OutputPredictor*>(p);o->correctOutputStates(sample,Quatf(q),Vector3f(v),geo(g),Vector3f(bg),Vector3f(ba));}
void p14r_outputs(void *p,float *q,float *v,double *g,float *correction){auto *o=static_cast<OutputPredictor*>(p);o->getQuaternion().copyTo(q);o->getVelocity().copyTo(v);auto pos=o->getLatLonAlt();g[0]=pos.latitude_rad();g[1]=pos.longitude_rad();g[2]=static_cast<double>(pos.altitude());o->_delta_angle_corr.copyTo(correction);}
void p14r_fields(void *p,float *x){auto *o=static_cast<OutputPredictor*>(p);auto y=state(*o);std::memcpy(x,y.data(),y.size()*sizeof(float));}
}
