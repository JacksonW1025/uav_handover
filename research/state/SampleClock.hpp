#pragma once
#include <cstdint>
namespace handover_research {
struct SampleClock {
    uint64_t last{0}, accepted{0}, duplicate{0}, regressed{0};
    uint32_t dt{0};
    unsigned accept(uint64_t sample) {
        if (!sample || sample < last) { ++regressed; return 2; }
        if (sample == last) { ++duplicate; return 1; }
        dt = last ? static_cast<uint32_t>(sample-last) : 0;
        last=sample; ++accepted; return 0;
    }
};
}
