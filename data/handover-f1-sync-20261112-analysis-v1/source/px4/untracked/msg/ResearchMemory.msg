# SITL-only RAPTOR recurrent memory evidence (P2, P3). Logging only; not read by any controller.
uint64 timestamp
uint64 timestamp_sample
uint8 ORB_QUEUE_LENGTH = 16
uint8 KIND_STEP = 1  # after a control inference
uint8 KIND_ENTRY = 2 # mode-entry cycle, after the original reset and any MC_RAPTOR_RINI treatment
uint8 KIND_EXIT = 3  # first inactive cycle after RAPTOR was active: memory held for MC_RAPTOR_RINI=6 (gru, previous_action)
uint8 kind
int32 entry_mode     # effective MC_RAPTOR_RINI (0 while MC_RAPTOR_RSH is off)
uint8 entry_result   # 0 none, 1 applied, 2 classic action unavailable, 3 no staged memory, 4 unknown mode, 5 no exit memory
bool active
bool native_step
bool teacher_forced  # previous action replaced by classic's applied motors before this inference
float32[16] gru      # step: committed hidden state after inference; entry: after the entry write
float32[4] previous_action # step: previous action used by this inference; entry: after the entry write
float32[16] gru_before_entry
float32[4] previous_action_before_entry
float32[4] classic_action  # latest classic applied motors converted to RAPTOR action space
uint64 classic_actuator_timestamp # actuator_motors.timestamp of that classic command (0: none)
uint32 clipped_total             # converted components clipped to [-1, 1]
uint32 classic_unavailable_total # conversions requested without a valid fresh classic command
float32[22] policy_input # step: executor input of this inference (relative position, rotation matrix, velocity, angular velocity, action history fed to the policy); P3
