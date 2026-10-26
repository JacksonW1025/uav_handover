#pragma once
#ifdef __PX4_POSIX
#include <lib/handover_research/StateBridge.hpp>
#endif

#include "trajectories/lissajous.hpp"

#include <px4_platform_common/defines.h>
#include <px4_platform_common/module.h>
#include <px4_platform_common/module_params.h>
#include <px4_platform_common/posix.h>
#include <px4_platform_common/px4_work_queue/ScheduledWorkItem.hpp>

#include <drivers/drv_hrt.h>
#include <lib/perf/perf_counter.h>

#include <uORB/Publication.hpp>
#include <uORB/Subscription.hpp>
#include <uORB/SubscriptionCallback.hpp>
#include <uORB/topics/vehicle_local_position.h>
#include <uORB/topics/vehicle_odometry.h>
#include <uORB/topics/vehicle_attitude.h>
#include <uORB/topics/vehicle_angular_velocity.h>
#ifdef __PX4_POSIX
#include <uORB/topics/research_angular_velocity.h>
#endif
#include <uORB/topics/actuator_motors.h>
#ifdef __PX4_POSIX
#include <uORB/topics/research_actuator.h>
#include <uORB/topics/research_memory.h>
#include <lib/handover_research/ActionMap.hpp>
#include <lib/handover_research/MemoryInit.hpp>
#endif
#ifdef __PX4_POSIX
#include <uORB/topics/research_target.h>
#include <lib/handover_research/TargetProfile.hpp>
#endif
#include <uORB/topics/trajectory_setpoint.h>
#ifdef __PX4_POSIX
#include <uORB/topics/research_recovery.h>
#include <lib/handover_research/RecoveryTarget.hpp>
#endif
#include <uORB/topics/register_ext_component_request.h>
#include <uORB/topics/register_ext_component_reply.h>
#include <uORB/topics/unregister_ext_component.h>
#include <uORB/topics/vehicle_status.h>
#include <uORB/topics/raptor_status.h>
#ifdef __PX4_POSIX
#include <uORB/topics/research_p12.h>
#include <lib/handover_research/P12Controls.hpp>
#endif
#include <uORB/topics/raptor_input.h>
#ifdef __PX4_POSIX
#include <uORB/topics/research_p11.h>
#endif
#include <uORB/topics/tune_control.h>
#ifdef __PX4_POSIX
#include <uORB/topics/research_p12b.h>
#include <lib/handover_research/P12bTrace.hpp>
#endif
#include <uORB/topics/setpoint_config.h>
#include <uORB/topics/arming_check_request.h>
#include <uORB/topics/arming_check_reply.h>
#undef OK

#ifdef __PX4_POSIX
#include <rl_tools/operations/cpu.h>
#else
#include <rl_tools/operations/arm.h>
#endif

#include <rl_tools/nn/layers/standardize/operations_generic.h>
#include <rl_tools/nn/layers/dense/operations_arm/opt.h>
#include <rl_tools/nn/layers/sample_and_squash/operations_generic.h>
#include <rl_tools/nn/layers/gru/operations_generic.h>
#include <rl_tools/nn_models/mlp/operations_generic.h>
#include <rl_tools/nn_models/sequential/operations_generic.h>

#include <rl_tools/inference/executor/executor.h>
#include <rl_tools/inference/applications/l2f/l2f.h>

#include "blob/policy.h"

#include <rl_tools/persist/backends/tar/operations_posix.h>
#include <rl_tools/nn/optimizers/adam/instance/persist.h>
#include <rl_tools/nn/layers/gru/persist.h>
#include <rl_tools/nn/layers/dense/persist.h>
#include <rl_tools/nn_models/sequential/persist.h>

namespace rlt = rl_tools;

#define MC_RAPTOR_POLICY_NAMESPACE rlt::checkpoint::actor
#define MC_RAPTOR_EXAMPLE_NAMESPACE rlt::checkpoint::example
#define MC_RAPTOR_META_NAMESPACE rlt::checkpoint::meta
// #define MC_RAPTOR_EMBED_POLICY // you can use this to directly embed the policy into the firmware instead of loading it from the sd card. To fit into the flash you might need to disable some unnecessary features in the .px4board config.





using namespace time_literals;

class Raptor : public ModuleBase, public ModuleParams, public px4::ScheduledWorkItem
{
public:
	static Descriptor desc;

	Raptor();
	~Raptor() override;

	/** @see ModuleBase */
	static int task_spawn(int argc, char *argv[]);

	/** @see ModuleBase */
	static int custom_command(int argc, char *argv[]);

	/** @see ModuleBase */
	static int print_usage(const char *reason = nullptr);

	bool init();

	int print_status() override;

private:
#ifdef __PX4_POSIX
	handover_research::StateBridge _research_state{1, 26, 100.f};
	void research_get(float *values);
	void research_set(const float *values, bool reset_state);
    handover_research::SampleClock _sample_clock{};
    unsigned _sample_generation{0};
    uint64_t _sample_missed{0}, _native_total{0}, _gru_total{0}, _last_gru_sample{0};
#endif
#ifdef __PX4_POSIX
	using DEVICE = rlt::devices::DefaultCPU;
#else
	using DEV_SPEC = rlt::devices::DefaultARMSpecification;
	using DEVICE = rlt::devices::arm::OPT<DEV_SPEC>;
#endif
	using TI = typename DEVICE::index_t;
	using RNG = DEVICE::SPEC::RANDOM::ENGINE<>;
	using T = float;
	static constexpr uint64_t EXT_COMPONENT_REQUEST_ID = 1337;
	DEVICE device;
	RNG rng;
	hrt_abstime init_time;
	// node constants
	static constexpr TI OBSERVATION_TIMEOUT_ANGULAR_VELOCITY = 10 * 1000;
	static constexpr TI OBSERVATION_TIMEOUT_LOCAL_POSITION = 100 * 1000;
	static constexpr TI OBSERVATION_TIMEOUT_ATTITUDE = 50 * 1000;
	static constexpr TI TRAJECTORY_SETPOINT_TIMEOUT = 200 * 1000;
	static constexpr T RESET_PREVIOUS_ACTION_VALUE = 0; // -1 to 1
	static constexpr bool ENABLE_CONTROL_FREQUENCY_INFO = false;

	T max_position_error = 0.5;
	T max_velocity_error = 1.0;

#ifdef __PX4_POSIX
    bool _p12_enabled{false}, _p12_seen{false}, _p12_repair{false};
    research_p12_s _p12{};
    uORB::Publication<research_p12_s> _p12_pub{ORB_ID(research_p12)};
#endif
	void Run() override;
#ifdef __PX4_POSIX
    bool _p12b_enabled{false};
    research_p12b_s _p12b{};
    uORB::Publication<research_p12b_s> _p12b_pub{ORB_ID(research_p12b)};
#endif

	decltype(register_ext_component_reply_s::mode_id) ext_component_mode_id = 255;
	decltype(register_ext_component_reply_s::arming_check_id) ext_component_arming_check_id;

	enum class FlightModeState : TI {
		UNREGISTERED = 0,
		CONFIGURED = 1
	};
	FlightModeState flightmode_state = FlightModeState::UNREGISTERED;
	bool can_arm = false;
	void updateArmingCheckReply();

	// node state
	vehicle_local_position_s _vehicle_local_position{};
#ifdef __PX4_POSIX
    research_angular_velocity_s _vehicle_angular_velocity{};
#else
	vehicle_angular_velocity_s _vehicle_angular_velocity{};
#endif
	vehicle_attitude_s _vehicle_attitude{};
	vehicle_status_s _vehicle_status{};
	trajectory_setpoint_s _trajectory_setpoint{};
	hrt_abstime timestamp_last_local_position, timestamp_last_angular_velocity, timestamp_last_attitude, timestamp_last_trajectory_setpoint,
		    timestamp_last_manual_control_input, timestamp_last_vehicle_status;
	bool timestamp_last_local_position_set = false, timestamp_last_angular_velocity_set = false, timestamp_last_attitude_set = false,
	     timestamp_last_trajectory_setpoint_set = false, timestamp_last_manual_control_input_set = false, timestamp_last_vehicle_status_set = false;
	bool timeout_message_sent = false;
	bool previous_trajectory_setpoint_stale = false;
#ifdef __PX4_POSIX
    bool _p11_enabled{false};
    uint64_t _p11_sequence{0};
    uint64_t _p11_pre_ns{0};
    research_p11_s _p11{};
    uORB::Publication<research_p11_s> _p11_pub{ORB_ID(research_p11)};
#endif
	bool previous_active = false;

	T position[3];
	T linear_velocity[3];

	uORB::Subscription _vehicle_local_position_sub{ORB_ID(vehicle_local_position)};
	uORB::Subscription _vehicle_attitude_sub{ORB_ID(vehicle_attitude)};
	uORB::Subscription _register_ext_component_reply_sub{ORB_ID(register_ext_component_reply)};
	uORB::Subscription _trajectory_setpoint_sub{ORB_ID(trajectory_setpoint)};
	uORB::Subscription _arming_check_request_sub{ORB_ID(arming_check_request)};
	uORB::Subscription _vehicle_status_sub{ORB_ID(vehicle_status)};
#ifdef __PX4_POSIX
    uORB::SubscriptionCallbackWorkItem _vehicle_angular_velocity_sub{this, ORB_ID(research_angular_velocity)};
#else
	uORB::SubscriptionCallbackWorkItem _vehicle_angular_velocity_sub{this, ORB_ID(vehicle_angular_velocity)};
#endif
	uORB::Publication<actuator_motors_s> _actuator_motors_pub{ORB_ID(actuator_motors)};
	uORB::Publication<raptor_status_s> _raptor_status_pub{ORB_ID(raptor_status)};
	uORB::Publication<raptor_input_s> _raptor_input_pub{ORB_ID(raptor_input)};
	uORB::Publication<tune_control_s> _tune_control_pub{ORB_ID(tune_control)};
	uORB::Publication<register_ext_component_request_s> _register_ext_component_request_pub{ORB_ID(register_ext_component_request)};
	uORB::Publication<unregister_ext_component_s> _unregister_ext_component_pub{ORB_ID(unregister_ext_component)};
	uORB::Publication<setpoint_config_s> _setpoint_config_pub{ORB_ID(setpoint_config)};
	uORB::Publication<arming_check_reply_s> _arming_check_reply_pub{ORB_ID(arming_check_reply)};
	// Performance (perf) counters
	perf_counter_t	_loop_perf{perf_alloc(PC_ELAPSED, MODULE_NAME": cycle")};
	perf_counter_t	_loop_interval_perf{perf_alloc(PC_INTERVAL, MODULE_NAME": interval")};
	perf_counter_t	_loop_interval_policy_perf{perf_alloc(PC_INTERVAL, MODULE_NAME": interval_policy")};

	struct EXECUTOR_CONFIG {
		static constexpr TI ACTION_HISTORY_LENGTH = 1;
		static constexpr TI CONTROL_INTERVAL_INTERMEDIATE_NS = 2.5 * 1000 * 1000; // Inference is at 500hz
		static constexpr TI CONTROL_INTERVAL_NATIVE_NS = 10 * 1000 * 1000; // Training is 100hz
		static constexpr TI TIMING_STATS_NUM_STEPS = 100;
		static constexpr bool FORCE_SYNC_INTERMEDIATE = true;
		static constexpr bool FORCE_SYNC_NATIVE_RUNTIME = true;
		static constexpr TI FORCE_SYNC_NATIVE = 8;
		static constexpr bool DYNAMIC_ALLOCATION = false;

		using ACTOR_TYPE_ORIGINAL = MC_RAPTOR_POLICY_NAMESPACE ::TYPE;
		using POLICY_TEST = MC_RAPTOR_POLICY_NAMESPACE ::TYPE::template CHANGE_BATCH_SIZE<TI, 1>::template CHANGE_SEQUENCE_LENGTH<TI, 1>;
		using POLICY_BATCH_SIZE = ACTOR_TYPE_ORIGINAL::template CHANGE_BATCH_SIZE<TI, 1>;
#ifdef MC_RAPTOR_EMBED_POLICY
		using POLICY = POLICY_BATCH_SIZE;
#else
		using POLICY = POLICY_BATCH_SIZE::template CHANGE_CAPABILITY<rlt::nn::capability::Forward<false, false>>;
#endif
		using TYPE_POLICY = typename POLICY::TYPE_POLICY;

#if defined(__PX4_POSIX)
		// Relax warning levels for Gazebo sitl. Because Gazebo SITL runs at 250Hz IMU rate, it is not a clean multiple of the training frequency (100hz), hence if the thresholds are set too strict, warnings will be triggered all the time. Generally, Raptor is quite robuts agains control frequency deviations.
		struct WARNING_LEVELS: rlt::inference::executor::WarningLevelsDefault<TYPE_POLICY> {
			using T = typename TYPE_POLICY::DEFAULT;
			static constexpr T INTERMEDIATE_TIMING_JITTER_HIGH_THRESHOLD = 2.0;
			static constexpr T INTERMEDIATE_TIMING_JITTER_LOW_THRESHOLD = 0.5;
			static constexpr T INTERMEDIATE_TIMING_BIAS_HIGH_THRESHOLD = 2.0;
			static constexpr T INTERMEDIATE_TIMING_BIAS_LOW_THRESHOLD = 0.5;
			static constexpr T NATIVE_TIMING_JITTER_HIGH_THRESHOLD = 2.0;
			static constexpr T NATIVE_TIMING_JITTER_LOW_THRESHOLD = 0.5;
			static constexpr T NATIVE_TIMING_BIAS_HIGH_THRESHOLD = 2.0;
			static constexpr T NATIVE_TIMING_BIAS_LOW_THRESHOLD = 0.5;
		};
#else
		struct WARNING_LEVELS: rlt::inference::executor::WarningLevelsDefault<TYPE_POLICY> {
			using T = typename TYPE_POLICY::DEFAULT;
			static constexpr T NATIVE_TIMING_JITTER_HIGH_THRESHOLD = 1.5;
			static constexpr T NATIVE_TIMING_JITTER_LOW_THRESHOLD = 0.5;
		};
#endif
		using TIMESTAMP = hrt_abstime;
		static constexpr TI OUTPUT_DIM = 4;
		static constexpr TI TEST_SEQUENCE_LENGTH_ACTUAL = 5;
		static constexpr TI TEST_BATCH_SIZE_ACTUAL = 2;

		using EXECUTOR_SPEC =
			rl_tools::inference::applications::l2f::Specification<TYPE_POLICY, TI, TIMESTAMP, ACTION_HISTORY_LENGTH, OUTPUT_DIM, POLICY, CONTROL_INTERVAL_INTERMEDIATE_NS, CONTROL_INTERVAL_NATIVE_NS, FORCE_SYNC_INTERMEDIATE, FORCE_SYNC_NATIVE, FORCE_SYNC_NATIVE_RUNTIME, WARNING_LEVELS, DYNAMIC_ALLOCATION>;
		using EXECUTOR_STATUS = rlt::inference::executor::Status<EXECUTOR_SPEC::EXECUTOR_SPEC>;
	};
	using EXECUTOR_SPEC = EXECUTOR_CONFIG::EXECUTOR_SPEC;
	rl_tools::inference::applications::L2F<EXECUTOR_SPEC> executor;
#ifdef MC_RAPTOR_EMBED_POLICY
	const decltype(MC_RAPTOR_POLICY_NAMESPACE ::module) &policy = MC_RAPTOR_POLICY_NAMESPACE::module;
#else
	EXECUTOR_CONFIG::POLICY policy;
#endif
	static constexpr TI CHECKPOINT_NAME_LENGTH = 100;
	char checkpoint_name[CHECKPOINT_NAME_LENGTH] = "n/a";

#ifdef MC_RAPTOR_EMBED_POLICY
	bool test_policy();
#else
	bool test_policy(FILE *f, TI input_offset, TI output_offset);
#endif

	void reset();
#ifdef __PX4_POSIX
    // P3 N3: memory held unchanged since RAPTOR's most recent exit (SITL research only).
    void research_exit_lifecycle(bool active);
    handover_research::ExitMemory _research_exit{};
#endif
	void observe(rl_tools::inference::applications::l2f::Observation<EXECUTOR_SPEC> &observation);
#ifdef __PX4_POSIX
    // P7 rate-limited recovery (SITL research only).
    void research_recovery_transition(bool active, bool stale, bool activation);
    bool research_recovery_apply(float saved[4]);
    void research_recovery_restore(const float saved[4]);
    void research_recovery_publish(uint8_t kind, uint8_t end_reason);
    struct ResearchRecoveryView {
        Raptor &raptor;
        float saved[4]{};
        bool on;
        explicit ResearchRecoveryView(Raptor &r) : raptor(r), on(r.research_recovery_apply(saved)) {}
        ~ResearchRecoveryView() {if (on) raptor.research_recovery_restore(saved);}
    };
    uORB::Publication<research_recovery_s> _research_recovery_pub{ORB_ID(research_recovery)};
    handover_research::RecoveryTarget _research_recovery{};
    handover_research::RecoveryStep _research_recovery_last{};
    bool _research_recovery_previous_stale{false}, _research_recovery_armed{false};
    float _research_recovery_vehicle_position[3]{}, _research_recovery_vehicle_velocity[3]{};
#endif

	static constexpr bool REMAP_FROM_CRAZYFLIE =
		true; // Policy (Crazyflie assignment) => Quadrotor (PX4 Quadrotor X assignment) PX4 SIH assumes the Quadrotor X configuration, which assumes different rotor positions than the crazyflie mapping (from crazyflie outputs to PX4): 1=>1, 2=>4, 3=>2, 4=>3
	// controller state

	// messaging state
	static constexpr TI POLICY_INTERVAL_WARNING_THRESHOLD = 100; // us
	static constexpr TI POLICY_FREQUENCY_CHECK_INTERVAL = 1000 * 1000; // 1s
	static constexpr TI POLICY_FREQUENCY_INFO_INTERVAL = 10; // 10 x POLICY_FREQUENCY_CHECK_INTERVAL = 10x
	static constexpr TI POLICY_CONTROL_FREQUENCY_TRAINING = 100;

	TI num_statii;
	TI num_healthy_executor_statii_intermediate, num_non_healthy_executor_statii_intermediate, num_healthy_executor_statii_native,
	num_non_healthy_executor_statii_native;
	EXECUTOR_CONFIG::EXECUTOR_STATUS last_intermediate_status, last_native_status;
	bool last_intermediate_status_set, last_native_status_set;

	TI policy_frequency_check_counter;
	hrt_abstime timestamp_last_policy_frequency_check;
	bool timestamp_last_policy_frequency_check_set = false;

	static constexpr TI NUM_TRAJECTORY_SETPOINT_DTS = 100;
	int32_t trajectory_setpoint_dts[NUM_TRAJECTORY_SETPOINT_DTS];
	TI trajectory_setpoint_dt_index = 0;
	TI trajectory_setpoint_dt_max_since_reset = 0;
	bool trajectory_setpoint_dts_full = false;

	static constexpr TI TRAJECTORY_SETPOINT_INVALID_COUNT_WARNING_INTERVAL = 100;
	TI trajectory_setpoint_invalid_count = 0;

	float previous_action[EXECUTOR_SPEC::OUTPUT_DIM];
#ifdef __PX4_POSIX
    // P2 mode-entry treatments and recurrent-memory evidence (SITL research only).
    void research_set_memory(const float *values);
    bool research_classic_action(float *action);
    void research_teacher_force(bool active);
    void research_entry(int32_t mode, const float *before, const float *classic, bool classic_valid);
    void research_log_step(bool active, const float *previous_action_used, bool native_step);
    uORB::Subscription _research_actuator_sub{ORB_ID(research_actuator)};
    uORB::Publication<research_memory_s> _research_memory_pub{ORB_ID(research_memory)};
    research_actuator_s _research_classic{};
    bool _research_classic_set{false}, _research_teacher_forced{false};
    int32_t _research_mode{0};
    float _research_classic_action[4]{};
    uint32_t _research_clipped_total{0}, _research_classic_unavailable_total{0};
#endif
#ifdef __PX4_POSIX
    // P4-01c takeover target (SITL research only).
    void research_target_capture(bool activation, bool active);
    void research_target_step(bool active, bool stale);
    void research_target_publish(uint8_t kind, uint8_t end_reason);
    uORB::Publication<research_target_s> _research_target_pub{ORB_ID(research_target)};
    handover_research::TargetProfile _research_target{};
    int32_t _research_target_mode{0};
    float _research_target_decel{0.f}, _research_target_vehicle_position[3]{}, _research_target_vehicle_velocity[3]{};
    bool _research_target_activation{false};
    uint8_t _research_target_phase{0};
    hrt_abstime _research_target_capture_time{0}, _research_target_capture_sample{0}, _research_target_local_sample{0};
#endif
	bool use_internal_reference = false;
	bool internal_reference_params_changed = false;
	T internal_reference_activation_position[3];
	T internal_reference_activation_orientation[4];
	hrt_abstime internal_reference_activation_time;
	enum class InternalReference : TI { // make sure this corresponds to the enum values for MC_RAPTOR_INTREF in module.yaml
		NONE = 0,
		LISSAJOUS = 1
	};
	InternalReference internal_reference = InternalReference::NONE;
	LissajousParameters lissajous_params{}; // Set via 'mc_raptor intref lissajous ...' command
	DEFINE_PARAMETERS(
		(ParamInt<px4::params::IMU_GYRO_RATEMAX>) _param_imu_gyro_ratemax,
		(ParamBool<px4::params::MC_RAPTOR_OFFB>) _param_mc_raptor_offboard,
		(ParamInt<px4::params::MC_RAPTOR_INTREF>) _param_mc_raptor_intref
	)


};
