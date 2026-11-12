uint64 timestamp
uint8 ORB_QUEUE_LENGTH = 32
uint64 actuator_timestamp # exact published actuator_motors.timestamp
uint8 owner # 1 RAPTOR, 2 classical control allocator
float32[4] control
