from pathlib import Path
import hashlib,json,subprocess
import argparse
parser=argparse.ArgumentParser(description="Extract fixed source blocks; writes only into a NEW output directory; does not compile or run")
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();P=args.source.resolve();s=P.read_text();out=args.output.resolve()
assert hashlib.sha256(P.read_bytes()).hexdigest()=='c09c440ee50be15e85072d663c89c376308c029c98883e9877e0f1c25809bdf0', 'wrong plugin source version'
out.mkdir(exist_ok=False)

callback=s.split('void ResearchMulticopterMotorModelPrivate::OnActuatorMsg(')[1].split('//////////////////////////////////////////////////')[0];body=callback[callback.index('{')+1:callback.rindex('}')]
a=s.index('    std::lock_guard<std::mutex> lock(this->recvdActuatorsMsgMutex);',s.index('void ResearchMulticopterMotorModelPrivate::UpdateForcesAndMoments'));b=s.index('\n  }',a);consume=s[a:b]
code='''#include <gz/msgs/actuators.pb.h>
#include <mutex>
#include <optional>
#include <cassert>
#include <iostream>
namespace msgs=gz::msgs;
uint64_t ResearchMonotonicNs(){return 0;} // irrelevant arrival wall clock: deterministic test
struct Slot {std::mutex recvdActuatorsMsgMutex;std::optional<msgs::Actuators> recvdActuatorsMsg;uint32_t researchReceived=0;uint64_t researchArrivalNs=0, applied=0;double input=0;
void callback(const msgs::Actuators &_msg){CALLBACK}
void step(uint64_t t,const char* arm){std::optional<msgs::Actuators> msg;uint32_t traceReceived=0;uint64_t traceArrivalNs=0;
{CONSUME}
if(msg){applied=msg->header().stamp().sec()*1000000ULL+msg->header().stamp().nsec()/1000ULL;input=msg->velocity(0);}
std::cout<<arm<<","<<t<<","<<applied<<","<<input<<","<<traceReceived<<"\\n";}
};
msgs::Actuators command(uint64_t id,double value){msgs::Actuators x;x.mutable_header()->mutable_stamp()->set_sec(id/1000000);x.mutable_header()->mutable_stamp()->set_nsec((id%1000000)*1000);for(int i=0;i<4;i++)x.add_velocity(value);return x;}
int main(){std::cout<<"arm,step_us,applied_sample_us,motor0_reference,received\\n";
Slot normal;normal.callback(command(1000,10));normal.step(4000,"normal");normal.callback(command(4000,11));normal.step(8000,"normal");assert(normal.applied==4000&&normal.input==11);
Slot lag;lag.callback(command(1000,10));lag.step(4000,"injected_callback_lag");lag.step(8000,"injected_callback_lag");assert(lag.applied==1000&&lag.input==10);lag.step(12000,"injected_callback_lag");lag.callback(command(4000,11));lag.step(16000,"injected_callback_lag");assert(lag.applied==4000&&lag.input==11);
Slot burst;burst.callback(command(1000,10));burst.step(4000,"injected_burst");burst.callback(command(4000,11));burst.callback(command(8000,12));burst.step(12000,"injected_burst");assert(burst.applied==8000&&burst.input==12);}
'''.replace('CALLBACK',body).replace('CONSUME',consume)
(out/'delivery_primitive.cpp').write_text(code)
meta={'source':'ResearchMulticopterMotorModel.cc','source_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'callback_body_verbatim':body,'consume_block_verbatim':consume,'test_type':'synthetic source-extracted callback/slot component; actual gz-msgs protobuf, no transport, no simulator, no flight','injection':'deliberate callback delivery scheduling; normal vs 8ms additional simulated callback delay; burst is explicit coalescing demonstration','not_measured':['real scheduler distribution','default PX4 failure','physical thrust','closed-loop effect'],'source_extracted_sha256':hashlib.sha256(code.encode()).hexdigest()};(out/'provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
