#include <gz/transport/Node.hh>
#include <gz/msgs/actuators.pb.h>
#include <gz/msgs/world_control.pb.h>
#include <gz/msgs/boolean.pb.h>
#include <chrono>
#include <thread>
#include <mutex>
#include <optional>
#include <atomic>
#include <iostream>
#include <stdexcept>
using namespace std::chrono_literals;
int main(int argc,char**argv){bool lag=argc>1&&std::string(argv[1])=="lag";gz::transport::Node n;auto downstream=n.Advertise<gz::msgs::Actuators>("/t4/command/motor_speed");auto source=n.Advertise<gz::msgs::Actuators>("/t4/source");std::mutex m;std::optional<gz::msgs::Actuators> held;std::atomic<int> seen{0};
std::function<void(const gz::msgs::Actuators&)> cb=[&](const gz::msgs::Actuators&x){std::lock_guard<std::mutex>l(m);if(lag&&x.header().stamp().nsec()==4000000){held=x;std::cout<<"relay_held,N4000\n";}else{if(!downstream.Publish(x))throw std::runtime_error("relay publish failed");std::cout<<"relay_forward,"<<x.header().stamp().nsec()/1000<<"\n";}++seen;};if(!n.Subscribe("/t4/source",cb))return 2;
for(int i=0;i<100&&!downstream.HasConnections();i++)std::this_thread::sleep_for(100ms);if(!downstream.HasConnections())throw std::runtime_error("no motor subscriber");
auto step=[&](int count){gz::msgs::WorldControl req;req.set_pause(true);req.set_multi_step(count);gz::msgs::Boolean rep;bool result=false;if(!n.Request("/world/t4_bench/control",req,2000,rep,result)||!result||!rep.data())throw std::runtime_error("world step failed");std::this_thread::sleep_for(200ms);};
auto send=[&](int id,double v){gz::msgs::Actuators x;x.mutable_header()->mutable_stamp()->set_nsec(id*1000);x.add_velocity(v);int before=seen.load();std::cout<<"source_publish,"<<id<<","<<v<<"\n";if(!source.Publish(x))throw std::runtime_error("source publish failed");for(int i=0;i<100&&seen.load()==before;i++)std::this_thread::sleep_for(10ms);if(seen.load()==before)throw std::runtime_error("relay receipt timeout");std::this_thread::sleep_for(100ms);};
step(1);send(1000,10);step(1);send(4000,11);step(1);step(1);if(lag){{std::lock_guard<std::mutex>l(m);if(!held)throw std::runtime_error("missing held");downstream.Publish(*held);held.reset();std::cout<<"relay_release,N4000,after_two_steps\n";}std::this_thread::sleep_for(100ms);}step(28);std::cout<<"DONE\n";}
