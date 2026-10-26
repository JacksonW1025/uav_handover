#pragma once
#include <cstdint>

// P12 experiment-only delivery gate. No clock or timeout is changed.
namespace handover_research {
inline bool p12_delivery_allowed(int32_t phase, bool active, bool initialized,
                                 uint64_t call_index, uint64_t force_sync) {
    if (!active || phase == 0 || !initialized || force_sync == 0) return true;
    const bool commits = call_index % force_sync == 0;
    return phase == 1 ? commits : phase == 2 ? !commits : false;
}
// All arms use the original T0 activation. Repair starts only on an active,
// nonactivation timeout after an actual external read since that activation.
inline int32_t p12_capture_mode(bool repair, bool activation, bool active, bool external_seen) {
    return repair && !activation && active && external_seen ? 2 : 0;
}
}
