uint64 timestamp
uint32 inference_duration_us # CLOCK_MONOTONIC wall duration, includes observation construction
uint8 mode_id
bool active
bool executor_ok
bool control_step
bool output_finite
float32[4] action
