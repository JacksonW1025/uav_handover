#pragma once
#include <uORB/topics/vehicle_control_mode.h>
#define ORB_ID(x) 0
namespace uORB {class Subscription {public:explicit Subscription(int){} bool copy(vehicle_control_mode_s *out){*out=test_mode;return test_available;}};}
