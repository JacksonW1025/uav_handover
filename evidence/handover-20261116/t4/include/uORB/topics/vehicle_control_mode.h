#pragma once
#include <cstdint>
struct vehicle_control_mode_s { uint64_t timestamp; bool flag_control_allocation_enabled; };
inline vehicle_control_mode_s test_mode{1,true};
inline bool test_available=true;
