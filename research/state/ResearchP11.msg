# P11 read-only complete inference observation. No controller subscribes.
uint64 timestamp
uint64 timestamp_sample
uint8 ORB_QUEUE_LENGTH = 32
uint64 sequence
uint64 run_wall_ns
uint64 read_wall_ns
uint64 external_timestamp
uint64 last_valid_read_us
uint64 local_position_sample
uint64 attitude_sample
uint32 invalid_total
bool active
bool subscription_updated
bool external_valid
bool stale
bool activation
bool native_step
bool gru_committed
bool recovery_active
float32[3] external_position # valid only when external_valid; otherwise NaN
float32[3] external_velocity
float32 external_yaw
float32[3] position
float32[3] velocity
float32[4] attitude
float32[3] angular_velocity
float32[3] network_target_position
float32[3] network_target_velocity
float32 target_yaw
float32[16] gru_before
float32[16] gru_after
float32[4] previous_action_before
float32[4] previous_action_after
float32[22] policy_input
float32[4] executor_action # clipped [-1,1], before scaling/remap; unclipped output replayed separately
