#pragma once
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#include <px4_platform_common/log.h>
#include <uORB/Publication.hpp>
#include <uORB/Subscription.hpp>
#include <uORB/topics/research_state_request.h>
#include <uORB/topics/research_state_response.h>
#include <drivers/drv_hrt.h>
namespace handover_research {
inline int state_command(int argc,char *argv[]) {
    if(argc<3){PX4_ERR("state <raptor|rate|velocity> <read|snapshot|reset|hold|restore|inject|release> [values...]");return -1;}
    research_state_request_s req{};
    const char *targets[]={"raptor","rate","velocity"};
    const char *ops[]={"read","snapshot","reset","hold","restore","inject","release"};
    for(unsigned i=0;i<3;i++)if(strcmp(argv[1],targets[i])==0)req.target=i+1;
    for(unsigned i=0;i<7;i++)if(strcmp(argv[2],ops[i])==0)req.operation=i+1;
    if(!req.target || !req.operation || argc-3>32)return -1;
    req.dimension=argc-3;
    if(req.operation!=6 && req.dimension!=0)return -1;
    for(unsigned i=0;i<req.dimension;i++) {
        char *end=nullptr;req.values[i]=strtof(argv[3+i],&end);
        if(end==argv[3+i] || *end!='\0')return -1;
    }
    uORB::Subscription sub{ORB_ID(research_state_response)};
    research_state_response_s response{};sub.copy(&response);
    uORB::Publication<research_state_request_s> pub{ORB_ID(research_state_request)};
    req.timestamp=hrt_absolute_time();req.request_id=req.timestamp;
    pub.publish(req);
    for(unsigned attempt=0;attempt<400;attempt++) {
        if(sub.update(&response) && response.request_id==req.request_id && response.target==req.target) {
            PX4_INFO_RAW("{\"request_id\":%llu,\"applied_us\":%llu,\"target\":%u,",
              (unsigned long long)response.request_id,(unsigned long long)response.timestamp,(unsigned)response.target);
            PX4_INFO_RAW("\"operation\":%u,\"result\":%u,\"dimension\":%u,\"active\":%s,\"holding\":%s,\"values\":[",
              (unsigned)response.operation,(unsigned)response.result,(unsigned)response.dimension,response.active?"true":"false",response.holding?"true":"false");
            for(unsigned i=0;i<response.dimension;i++)PX4_INFO_RAW("%s%.9g",i?",":"",(double)response.values[i]);
            PX4_INFO_RAW("]}\n");return response.result==0?0:-1;
        }
        usleep(5000);
    }
    PX4_ERR("state operation acknowledgement timed out");return -1;
}
}
