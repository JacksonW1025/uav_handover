# SITL-only queued, calibrated observations before latest-only publication coalescing.
uint64 timestamp
uint64 timestamp_sample
float32[3] xyz
float32[3] xyz_derivative
uint8 ORB_QUEUE_LENGTH = 32
