uint64 timestamp
uint8 ORB_QUEUE_LENGTH = 32
uint8 schema_version
uint64 timestamp_sample
uint64 accepted_total
uint64 duplicate_total
uint64 regressed_total
uint64 source_missed_total
uint64 native_total
uint64 gru_commit_total
uint64 last_gru_sample
uint32 source_generation
uint32 input_dt_us
uint32 executor_dt_us
uint32 native_dt_us
uint8 input_result
bool executor_called
bool native_step
bool gru_committed
bool timing_jitter_ok
bool timing_bias_ok
bool timestamp_invalid
bool timestamp_order_invalid
float32 jitter_ratio
float32 bias_ratio
uint32 inference_duration_us # CLOCK_MONOTONIC wall duration, includes observation construction
uint8 mode_id
bool active
bool executor_ok
bool control_step
bool output_finite
float32[4] action
bool actuator_published
uint64[3] scope_calls
uint64[3] scope_warnings
uint64[3] scope_jitter
uint64[3] scope_bias
uint64[3] scope_rejected
uint64[3] scope_hard
uint64[3] scope_duration_sum_us
uint32[3] scope_duration_max_us
uint64[3] scope_over_2500us
uint64[3] scope_unclassified_warning

# Preparation trace: source times retain their individual meanings.
uint64 local_position_sample
uint64 attitude_sample
uint64 control_start_wall_ns
uint64 control_end_wall_ns
uint64 actuator_publish_wall_ns
uint64 actuator_publish_sim_us

# P11 v2 complete observation accounting; active control rows, zero means unavailable.
uint64 p11_cycle_wall_start_ns
uint64 p11_cycle_wall_end_ns
uint64 p11_setup_ns
uint64 p11_pre_ns
uint64 p11_post_copy_ns
uint64 p11_publication_ns
