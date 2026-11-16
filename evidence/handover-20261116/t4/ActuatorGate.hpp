#pragma once
#include <pthread.h>
#include <uORB/Subscription.hpp>
#include <uORB/topics/vehicle_control_mode.h>

namespace handover_research {
// SITL-only publication arbitration. Both writers check the latest commander
// allocation flag under the same lock, instead of independent cached copies.
class ActuatorGate {
public:
    explicit ActuatorGate(bool neural) {
        pthread_mutex_lock(&mutex());
        static uORB::Subscription mode_sub{ORB_ID(vehicle_control_mode)};
        vehicle_control_mode_s mode{};
        _allowed = mode_sub.copy(&mode) && mode.timestamp != 0
            && (neural != mode.flag_control_allocation_enabled);
    }
    ~ActuatorGate() { pthread_mutex_unlock(&mutex()); }
    bool allowed() const { return _allowed; }
    ActuatorGate(const ActuatorGate &) = delete;
    ActuatorGate &operator=(const ActuatorGate &) = delete;
private:
    static pthread_mutex_t &mutex() {
        static pthread_mutex_t value = PTHREAD_MUTEX_INITIALIZER;
        return value;
    }
    bool _allowed{false};
};
}
