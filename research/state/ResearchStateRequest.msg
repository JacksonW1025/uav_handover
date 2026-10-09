uint64 timestamp
uint64 request_id
uint8 target # 1 RAPTOR, 2 rate integral, 3 velocity integral
uint8 operation # 1 READ, 2 SNAPSHOT, 3 RESET, 4 HOLD, 5 RESTORE, 6 INJECT, 7 RELEASE
uint8 dimension
float32[32] values
uint8 ORB_QUEUE_LENGTH = 8
