uint64 timestamp
uint64 timestamp_sample # Sample selected by the mixer provider; not physics acknowledgement
uint64 wall_monotonic_ns
uint8 ORB_QUEUE_LENGTH = 32
uint64 attempts_total
uint64 published_total
uint64 repeated_sample_total
uint64 regressed_sample_total
uint64 negative_age_total
uint64[8] age_bins # <=0, <=4, <=8, <=12, <=20, <=40, <=100, >100 ms; nonzero samples only
bool transport_published
bool armed
float32[4] motor_speed
uint64 skipped_publication_total # actuator_motors publications overwritten before the mixer read them (uORB generation gaps)
