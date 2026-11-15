#include <gz/msgs/actuators.pb.h>
#include <mutex>
#include <optional>
#include <cassert>
#include <iostream>
namespace msgs=gz::msgs;
uint64_t ResearchMonotonicNs(){return 0;} // irrelevant arrival wall clock: deterministic test
struct Slot {std::mutex recvdActuatorsMsgMutex;std::optional<msgs::Actuators> recvdActuatorsMsg;uint32_t researchReceived=0;uint64_t researchArrivalNs=0, applied=0;double input=0;
void callback(const msgs::Actuators &_msg){
  std::lock_guard<std::mutex> lock(this->recvdActuatorsMsgMutex);
  this->recvdActuatorsMsg = _msg;
  ++this->researchReceived;
  this->researchArrivalNs = ResearchMonotonicNs();
}
void step(uint64_t t,const char* arm){std::optional<msgs::Actuators> msg;uint32_t traceReceived=0;uint64_t traceArrivalNs=0;
{    std::lock_guard<std::mutex> lock(this->recvdActuatorsMsgMutex);
    if (this->recvdActuatorsMsg.has_value())
    {
      msg = *this->recvdActuatorsMsg;
      this->recvdActuatorsMsg.reset();
    }
    traceReceived = this->researchReceived;
    traceArrivalNs = this->researchArrivalNs;
    this->researchReceived = 0;}
if(msg){applied=msg->header().stamp().sec()*1000000ULL+msg->header().stamp().nsec()/1000ULL;input=msg->velocity(0);}
std::cout<<arm<<","<<t<<","<<applied<<","<<input<<","<<traceReceived<<"\n";}
};
msgs::Actuators command(uint64_t id,double value){msgs::Actuators x;x.mutable_header()->mutable_stamp()->set_sec(id/1000000);x.mutable_header()->mutable_stamp()->set_nsec((id%1000000)*1000);for(int i=0;i<4;i++)x.add_velocity(value);return x;}
int main(){std::cout<<"arm,step_us,applied_sample_us,motor0_reference,received\n";
Slot normal;normal.callback(command(1000,10));normal.step(4000,"normal");normal.callback(command(4000,11));normal.step(8000,"normal");assert(normal.applied==4000&&normal.input==11);
Slot lag;lag.callback(command(1000,10));lag.step(4000,"injected_callback_lag");lag.step(8000,"injected_callback_lag");assert(lag.applied==1000&&lag.input==10);lag.step(12000,"injected_callback_lag");lag.callback(command(4000,11));lag.step(16000,"injected_callback_lag");assert(lag.applied==4000&&lag.input==11);
Slot burst;burst.callback(command(1000,10));burst.step(4000,"injected_burst");burst.callback(command(4000,11));burst.callback(command(8000,12));burst.step(12000,"injected_burst");assert(burst.applied==8000&&burst.input==12);}
