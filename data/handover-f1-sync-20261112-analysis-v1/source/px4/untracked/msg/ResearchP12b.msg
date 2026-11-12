# P12b read-decision contract. Observations never used by the controller.
uint64 timestamp
uint64 timestamp_sample
uint8 ORB_QUEUE_LENGTH = 32
uint64 pre_read_wall_ns
uint64 call_index_pre
uint64 force_sync_pre
uint64 control_time_pre
uint64 original_control_time_pre
uint64 last_valid_read_pre
int32 repair_not_before_ms
int32 requested_phase
bool active
bool activation
bool timing_initialized_pre
bool force_sync_initialized_pre
bool gate_applicable
bool gate_permit
bool gate_pending
bool external_seen_pre
bool read_updated
bool read_valid
uint32 invalid_total
uint64 last_valid_read_post
uint64 external_timestamp
