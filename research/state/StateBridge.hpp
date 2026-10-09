#pragma once
#include "StateOps.hpp"
#include <drivers/drv_hrt.h>
#include <parameters/param.h>
#include <uORB/Publication.hpp>
#include <uORB/Subscription.hpp>
#include <uORB/topics/research_state_request.h>
#include <uORB/topics/research_state_response.h>
namespace handover_research {
class StateBridge {
public:
    StateBridge(unsigned target,unsigned dim,float bound):_target(target),_dim(dim) {for(unsigned i=0;i<dim;i++)_bounds[i]=bound;}
    StateOps engine{};
    float _bounds[MAX_DIM]{};
    template<typename GET,typename SET>
    void update(bool active,GET get,SET set) {
        int32_t enabled=0;param_t p=param_find("MC_RAPTOR_RSH");
        if(p!=PARAM_INVALID)param_get(p,&enabled);
        if(!enabled)engine.holding=false;
        if(engine.holding)set(engine.held,false);
        research_state_request_s req{};
        if(!_request.update(&req) || req.target!=_target)return;
        float values[MAX_DIM]{},zero[MAX_DIM]{};
        get(values);get(zero);
        // RESET clears memory, preserves the six reference fields for RAPTOR.
        for(unsigned i=0;i<(_target==1?20:_dim);i++)zero[i]=0;
        Result r=enabled?engine.process(req.operation,active,values,_dim,_bounds,zero,req.values,req.dimension):DISABLED;
        if(r==SUCCESS && (req.operation==RESET || req.operation==RESTORE || req.operation==INJECT))set(values,req.operation==RESET);
        research_state_response_s response{};response.timestamp=hrt_absolute_time();response.request_id=req.request_id;
        response.target=_target;response.operation=req.operation;response.result=r;response.dimension=_dim;
        response.active=active;response.holding=engine.holding;
        get(response.values);_response.publish(response);
    }
private:
    unsigned _target,_dim;
    uORB::Subscription _request{ORB_ID(research_state_request)};
    uORB::Publication<research_state_response_s> _response{ORB_ID(research_state_response)};
};
}
