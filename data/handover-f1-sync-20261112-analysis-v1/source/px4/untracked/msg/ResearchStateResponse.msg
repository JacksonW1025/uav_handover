uint64 timestamp # actual controller boundary after application
uint64 request_id
uint8 target
uint8 operation
uint8 result # 0 OK, 1 disabled, 2 active write, 3 dimension, 4 nonfinite, 5 bounds, 6 no snapshot, 7 unknown
uint8 dimension
bool active
bool holding
float32[32] values # actual applied/read values
uint8 ORB_QUEUE_LENGTH = 8
