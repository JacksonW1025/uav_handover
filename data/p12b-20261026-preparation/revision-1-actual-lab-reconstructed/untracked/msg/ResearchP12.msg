# P12 direct executor history and experiment-only delivery gate evidence.
uint64 timestamp
uint64 timestamp_sample
uint8 ORB_QUEUE_LENGTH = 32
uint64 read_begin_wall_ns
uint64 read_end_wall_ns
uint64 last_gru_sample_before
uint64 call_index_before
uint64 call_index_after
uint32 history_count_before
uint32 history_count_after
int32 requested_phase
bool active
bool predicted_commit
bool actual_commit
bool gate_pending
bool gate_permit
bool lp_updated
bool attitude_updated
bool external_seen
bool repair_requested
float32[4] history_before
float32[4] history_after
