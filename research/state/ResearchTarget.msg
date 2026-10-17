# SITL-only RAPTOR takeover target evidence (P4-01c, MC_RAPTOR_RTGT). Logging only; not read by any controller.
uint64 timestamp
uint64 timestamp_sample      # gyro sample of this RAPTOR cycle (time base of the T1 profile)
uint8 ORB_QUEUE_LENGTH = 16
uint8 KIND_CAPTURE = 1       # RAPTOR captured its target in this cycle (activation, or 200 ms setpoint timeout)
uint8 KIND_PROFILE = 2       # T1: RAPTOR target of this cycle
uint8 KIND_END = 3           # T1 profile ended
uint8 END_EXTERNAL_SETPOINT = 1
uint8 END_RECAPTURE = 2
uint8 END_INACTIVE = 3
uint8 kind
int32 mode                   # MC_RAPTOR_RTGT at the capture (0 zero-velocity capture, 1 speed-matched at activation, 2 speed-matched at activation and in-flight timeout; rows only while MC_RAPTOR_RSH is on)
bool activation              # capture in the activation cycle
uint8 phase                  # 1 hold (zero-velocity capture), 2 decelerating, 3 stopped at the end point; 0 on KIND_END
uint8 end_reason
float32 decel                # MC_RAPTOR_RTDEC at the capture [m/s^2]
uint64 capture_timestamp     # hrt time of the capture cycle
uint64 capture_sample        # gyro sample of the capture cycle (profile time zero)
uint64 local_position_sample # vehicle_local_position.timestamp_sample used for the capture
float32[3] vehicle_position  # vehicle position at the capture (NED)
float32[3] vehicle_velocity  # vehicle velocity at the capture (NED)
float32[3] position          # RAPTOR target position after this cycle's update (NED)
float32[3] velocity          # RAPTOR target velocity after this cycle's update (NED)
float32 yaw                  # RAPTOR target yaw (NED)
