#pragma once
#include <uORB/Publication.hpp>
#include <uORB/topics/research_timing.h>
namespace handover_research {
// Publish once after actuator arbitration, including all early-return paths.
// Cumulative counters keep warning counts exact when ULog omits individual rows.
class TimingRecord {
public:
    explicit TimingRecord(research_timing_s &value): v(value) {}
    ~TimingRecord() {
        static uint64_t calls[3]{}, warnings[3]{}, jitter[3]{}, bias[3]{}, rejected[3]{}, hard[3]{}, sums[3]{}, over_budget[3]{}, unclassified[3]{};
        static uint32_t maximum[3]{};
        for(unsigned i=0;i<3;i++) {
            const bool scope=i==0 || (i==1 ? v.active : v.actuator_published);
            if(scope) {
                if(v.executor_called) {
                    ++calls[i];sums[i]+=v.inference_duration_us;
                    if(v.inference_duration_us>2500)++over_budget[i];
                    if(v.inference_duration_us>maximum[i])maximum[i]=v.inference_duration_us;
                    if(!v.executor_ok) {
                        ++warnings[i];
                        if(!v.timestamp_invalid && !v.timestamp_order_invalid && v.timing_jitter_ok && v.timing_bias_ok)++unclassified[i];
                    }
                    if(v.control_step && !v.timing_jitter_ok)++jitter[i];
                    if(v.control_step && !v.timing_bias_ok)++bias[i];
                    if(v.timestamp_invalid || v.timestamp_order_invalid || !v.output_finite)++hard[i];
                }
                if(v.input_result)++rejected[i];
            }
            v.scope_calls[i]=calls[i];v.scope_warnings[i]=warnings[i];v.scope_jitter[i]=jitter[i];
            v.scope_bias[i]=bias[i];v.scope_rejected[i]=rejected[i];v.scope_hard[i]=hard[i];
            v.scope_unclassified_warning[i]=unclassified[i];
            v.scope_over_2500us[i]=over_budget[i];
            v.scope_duration_sum_us[i]=sums[i];v.scope_duration_max_us[i]=maximum[i];
        }
        static uORB::Publication<research_timing_s> pub{ORB_ID(research_timing)};
        pub.publish(v);
    }
private:
    research_timing_s &v;
};
}
