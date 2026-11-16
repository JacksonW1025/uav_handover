#include <gz/transport/Node.hh>
#include <gz/msgs/actuators.pb.h>
#include <gz/msgs/clock.pb.h>
#include <thread>
#include <chrono>
#include <fstream>
#include <filesystem>
#include <optional>
#include <mutex>
#include <atomic>
#include <csignal>
using namespace std::chrono_literals;
std::atomic<bool> running{true};void stop(int){running=false;}uint64_t wall(){return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
int main(int argc,char**argv){std::string model=argv[1],prefix=argv[2];uint64_t delay=std::stoull(argv[3]);signal(SIGINT,stop);signal(SIGTERM,stop);gz::transport::Node n;auto p=n.Advertise<gz::msgs::Actuators>("/"+model+"/command/t4_motor_speed");std::atomic<uint64_t> sim{0};std::mutex m;std::optional<gz::msgs::Actuators> held;bool active=false,used=false,ready=false;uint64_t begin=0,beginwall=0;std::ofstream log(prefix+".csv");log<<"event,wall_ns,sim_us,sample_us,v0,v1,v2,v3\n";
auto record=[&](const char*e,const gz::msgs::Actuators*x=nullptr){log<<e<<","<<wall()<<","<<sim.load()<<","<<(x?x->header().stamp().sec()*1000000ULL+x->header().stamp().nsec()/1000:0);for(int i=0;i<4;i++)log<<","<<(x&&x->velocity_size()>i?x->velocity(i):0);log<<"\n";};
auto release=[&](const char*why){record(why);active=false;if(held){p.Publish(*held);record("release_latest",&*held);held.reset();}log.flush();};
std::function<void(const gz::msgs::Clock&)> ck=[&](const gz::msgs::Clock&x){sim=x.sim().sec()*1000000ULL+x.sim().nsec()/1000;};n.Subscribe("/world/default/clock",ck);
std::function<void(const gz::msgs::Actuators&)> cb=[&](const gz::msgs::Actuators&x){std::lock_guard<std::mutex>l(m);record("source",&x);if(active&&(sim.load()>=begin+delay||wall()>=beginwall+100000000))release("deadline_callback");if(active){held=x;record("held",&x);}else{p.Publish(x);record("forward",&x);}};n.Subscribe("/"+model+"/command/motor_speed",cb);
while(running){{std::lock_guard<std::mutex>l(m);if(!ready&&p.HasConnections()&&sim>0){std::ofstream(prefix+".ready")<<sim.load();ready=true;}if(!used&&std::filesystem::exists(prefix+".trigger")){used=true;begin=sim;beginwall=wall();active=delay>0;record("window_begin");log.flush();std::ofstream(prefix+".ack")<<begin;}if(active&&std::filesystem::exists(prefix+".release"))release("fresh_active_release");if(active&&(sim.load()>=begin+delay||wall()>=beginwall+100000000))release("deadline_monitor");}std::this_thread::sleep_for(100us);}std::lock_guard<std::mutex>l(m);if(active)release("shutdown_release");record("exit");}
