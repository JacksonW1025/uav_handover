# SITL-only P7 rate-limited recovery evidence (MC_RAPTOR_RREC > 0). Logging only; not read by any controller.
uint64 timestamp
uint64 timestamp_sample      # gyro sample of this RAPTOR cycle (time base of the virtual target)
uint8 ORB_QUEUE_LENGTH = 16
uint8 KIND_START = 1         # setpoint fresh again after an in-flight timeout capture: virtual target = vehicle state
uint8 KIND_STEP = 2          # virtual target of this cycle (the network observed it in this cycle)
uint8 KIND_END = 3           # virtual target ended; the network observes the setpoint (CONVERGED) or a capture (STALE)
uint8 END_CONVERGED = 1
uint8 END_STALE = 2
uint8 END_INACTIVE = 3
uint8 kind
uint8 end_reason
float32 rate                 # MC_RAPTOR_RREC at the start [m/s^2]
float32 omega                # w [rad/s]
float32 dt                   # integration step of this cycle [s]
bool limited                 # |acc| scaled down to rate in this cycle
float32[2] acc               # applied horizontal acceleration (NED) [m/s^2]
float32 acc_unlimited_norm   # |acc| before the limit [m/s^2]
float32 position_difference  # |sp - vt| horizontal after the update [m]
float32 velocity_difference  # |sp_vel - vt_vel| horizontal after the update [m/s]
uint64 start_sample          # gyro sample of the start cycle
float32[3] target_position   # target the network observed: virtual target horizontal, setpoint vertical (NED)
float32[3] target_velocity
float32[3] setpoint_position # external setpoint in force (NED); on KIND_END STALE the captured target
float32[3] setpoint_velocity
float32[3] vehicle_position  # vehicle state at the start (NED)
float32[3] vehicle_velocity
