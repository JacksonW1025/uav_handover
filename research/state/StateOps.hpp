#pragma once
#include <cmath>
#include <cstddef>

// Fixed-size, allocation-free state operations. Only invoked by a controller's own thread.
namespace handover_research {
constexpr unsigned MAX_DIM=32;
enum Operation {READ=1,SNAPSHOT=2,RESET=3,HOLD=4,RESTORE=5,INJECT=6,RELEASE=7};
enum Result {SUCCESS=0,DISABLED=1,ACTIVE_WRITE=2,DIMENSION=3,NONFINITE=4,BOUNDS=5,NO_SNAPSHOT=6,UNKNOWN=7};
struct StateOps {
    float snapshot[MAX_DIM]{};
    float held[MAX_DIM]{};
    unsigned saved_dim=0;
    bool holding=false;
    static void copy(float *to,const float *from,unsigned dim) {for(unsigned i=0;i<dim;i++)to[i]=from[i];}
    static Result validate(const float *v,unsigned dim,const float *bounds) {
        if(dim==0 || dim>MAX_DIM)return DIMENSION;
        for(unsigned i=0;i<dim;i++) {
            if(!std::isfinite(v[i]))return NONFINITE;
            if(std::fabs(v[i])>bounds[i])return BOUNDS;
        }
        return SUCCESS;
    }
    Result process(unsigned op,bool active,float *v,unsigned dim,const float *bounds,const float *reset,const float *input,unsigned count) {
        if(dim==0 || dim>MAX_DIM)return DIMENSION;
        if(op==READ)return SUCCESS;
        if(op==SNAPSHOT) {
            Result r=validate(v,dim,bounds);if(r!=SUCCESS)return r;
            copy(snapshot,v,dim);saved_dim=dim;return SUCCESS;
        }
        if(op==RELEASE){holding=false;return SUCCESS;}
        if(op==HOLD) {
            Result r=validate(v,dim,bounds);if(r!=SUCCESS)return r;
            copy(held,v,dim);holding=true;return SUCCESS;
        }
        if(op==RESET) {
            Result r=validate(reset,dim,bounds);if(r!=SUCCESS)return r;
            copy(v,reset,dim);if(holding)copy(held,v,dim);return SUCCESS;
        }
        if(op==RESTORE || op==INJECT) {
            if(active)return ACTIVE_WRITE;
            if(op==RESTORE && saved_dim!=dim)return NO_SNAPSHOT;
            if(op==INJECT && count!=dim)return DIMENSION;
            const float *source=op==RESTORE?snapshot:input;
            Result r=validate(source,dim,bounds);if(r!=SUCCESS)return r;
            copy(v,source,dim);if(holding)copy(held,v,dim);return SUCCESS;
        }
        return UNKNOWN;
    }
};
}
