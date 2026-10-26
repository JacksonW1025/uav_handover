#ifdef __PX4_POSIX
#include <uORB/topics/research_actuator.h>
#include <lib/handover_research/ActuatorGate.hpp>
#endif
#include "mc_raptor.hpp"
#undef OK

#include <rl_tools/inference/applications/l2f/operations_generic.h>
#include <rl_tools/persist/backends/tar/operations_generic.h>

#include <sys/stat.h>
#ifdef __PX4_POSIX
#include <lib/handover_research/StateCli.hpp>
#include <uORB/topics/research_timing.h>
#include <time.h>
void Raptor::research_get(float *v) {
    auto &hidden = executor.executor.policy_state.content_state.next_content_state.state.state;
    static_assert(std::remove_reference_t<decltype(hidden)>::SPEC::SIZE == 16, "Frozen checkpoint GRU dimension changed");
    for (TI i=0;i<16;i++) v[i]=rlt::get(device,hidden,0,i);
    for (TI i=0;i<4;i++) v[16+i]=previous_action[i];
    for (TI i=0;i<3;i++) {v[20+i]=_trajectory_setpoint.position[i];v[23+i]=_trajectory_setpoint.velocity[i];}
}
void Raptor::research_set(const float *v, bool reset_state) {
    if(reset_state) this->reset();
    auto &hidden = executor.executor.policy_state.content_state.next_content_state.state.state;
    auto &temp = executor.executor.policy_state_temp.content_state.next_content_state.state.state;
    for (TI i=0;i<16;i++) {rlt::set(device,hidden,v[i],0,i);rlt::set(device,temp,v[i],0,i);}
    for (TI i=0;i<4;i++) previous_action[i]=v[16+i];
    for (TI i=0;i<3;i++) {_trajectory_setpoint.position[i]=v[20+i];_trajectory_setpoint.velocity[i]=v[23+i];}
}
#endif

#ifdef __PX4_POSIX
// Only the GRU hidden state and previous action; never RAPTOR's position/velocity target.
void Raptor::research_set_memory(const float *v) {
    auto &hidden = executor.executor.policy_state.content_state.next_content_state.state.state;
    auto &temp = executor.executor.policy_state_temp.content_state.next_content_state.state.state;
    for (TI i=0;i<handover_research::GRU_DIM;i++) {rlt::set(device,hidden,v[i],0,i);rlt::set(device,temp,v[i],0,i);}
    for (TI i=0;i<handover_research::ACTION_DIM;i++) previous_action[i]=v[handover_research::GRU_DIM+i];
}
// Latest motor command actually published by the classic allocator, in RAPTOR action space.
bool Raptor::research_classic_action(float *action) {
    research_actuator_s sample{};
    while (_research_actuator_sub.update(&sample)) if (sample.owner==2) {_research_classic=sample;_research_classic_set=true;}
    constexpr hrt_abstime MAX_AGE_US=50000;
    bool valid=_research_classic_set && hrt_absolute_time()-_research_classic.timestamp<=MAX_AGE_US;
    if (valid) {
        const handover_research::ActionConversion r=handover_research::motor_to_action(_research_classic.control,_research_classic_action);
        _research_clipped_total+=r.clipped;valid=r.valid;
    }
    if (!valid) {++_research_classic_unavailable_total;return false;}
    for (TI i=0;i<4;i++) action[i]=_research_classic_action[i];
    return true;
}
void Raptor::research_teacher_force(bool active) {
    static const param_t rini=param_find("MC_RAPTOR_RINI"), rsh=param_find("MC_RAPTOR_RSH");
    int32_t mode=0, enabled=0;param_get(rini,&mode);param_get(rsh,&enabled);
    _research_mode=enabled?mode:0;_research_teacher_forced=false;
    if (active || !handover_research::teacher_forcing(_research_mode)) return;
    float action[4];
    if (research_classic_action(action)) {
        for (TI i=0;i<4;i++) previous_action[i]=action[i];
        _research_teacher_forced=true;
    }
}
void Raptor::research_entry(int32_t mode, const float *before, const float *classic, bool classic_valid) {
    research_memory_s m{};
    m.timestamp=hrt_absolute_time();m.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    m.kind=research_memory_s::KIND_ENTRY;m.entry_mode=mode;m.active=true;
    for (TI i=0;i<16;i++) m.gru_before_entry[i]=before[i];
    for (TI i=0;i<4;i++) {m.previous_action_before_entry[i]=before[16+i];m.classic_action[i]=classic_valid?classic[i]:NAN;}
    if (mode>=handover_research::ENTRY_CLASSIC_ACTION) {
        float written[handover_research::MEMORY_DIM]{};
        m.entry_result=handover_research::entry_memory(mode,before,classic,classic_valid,_research_state.engine.staged,
            _research_state.engine.staged_dim,_research_exit.memory,_research_exit.valid,RESET_PREVIOUS_ACTION_VALUE,written);
        if (m.entry_result==handover_research::ENTRY_APPLIED) {
            research_set_memory(written);
            PX4_INFO("Research mode-entry treatment %d applied",(int)mode);
        } else {
            PX4_ERR("Research mode-entry treatment %d NOT applied: result %d",(int)mode,(int)m.entry_result);
        }
    }
    float after[32]{};research_get(after);
    for (TI i=0;i<16;i++) m.gru[i]=after[i];
    for (TI i=0;i<4;i++) m.previous_action[i]=after[16+i];
    m.classic_actuator_timestamp=_research_classic_set?_research_classic.actuator_timestamp:0;
    m.clipped_total=_research_clipped_total;m.classic_unavailable_total=_research_classic_unavailable_total;
    _research_memory_pub.publish(m);
}
void Raptor::research_log_step(bool active, const float *previous_action_used, bool native_step) {
    research_memory_s m{};
    m.timestamp=hrt_absolute_time();m.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    m.kind=research_memory_s::KIND_STEP;m.entry_mode=_research_mode;m.active=active;m.native_step=native_step;
    m.teacher_forced=_research_teacher_forced;
    for (TI i=0;i<22;i++) m.policy_input[i]=rlt::get(device,executor.input,0,i);
    float memory[32]{};research_get(memory);
    for (TI i=0;i<16;i++) m.gru[i]=memory[i];
    for (TI i=0;i<4;i++) {m.previous_action[i]=previous_action_used[i];m.classic_action[i]=_research_teacher_forced?_research_classic_action[i]:NAN;}
    m.classic_actuator_timestamp=_research_teacher_forced?_research_classic.actuator_timestamp:0;
    m.clipped_total=_research_clipped_total;m.classic_unavailable_total=_research_classic_unavailable_total;
    _research_memory_pub.publish(m);
}
#endif

ModuleBase::Descriptor Raptor::desc{task_spawn, custom_command, print_usage};

Raptor::Raptor(): ModuleParams(nullptr), ScheduledWorkItem(MODULE_NAME, px4::wq_configurations::rate_ctrl)
{
	// node state
	timestamp_last_angular_velocity_set = false;
	timestamp_last_local_position_set = false;
	timestamp_last_attitude_set = false;
	timestamp_last_trajectory_setpoint_set = false;
	timestamp_last_vehicle_status_set = false;
	previous_trajectory_setpoint_stale = false;
	previous_active = false;
	timeout_message_sent = false;
	timestamp_last_policy_frequency_check_set = false;
	last_intermediate_status_set = false;
	last_native_status_set = false;
	policy_frequency_check_counter = 0;
	flightmode_state = FlightModeState::UNREGISTERED;
	can_arm = false;
	trajectory_setpoint_dt_index = 0;
	trajectory_setpoint_dts_full = false;
	trajectory_setpoint_invalid_count = 0;
	trajectory_setpoint_dt_max_since_reset = 0;
	internal_reference_activation_position[0] = 0.0f;
	internal_reference_activation_position[1] = 0.0f;
	internal_reference_activation_position[2] = 0.0f;
	internal_reference_params_changed = false;

#ifdef __PX4_POSIX
    _p11_pub.advertise();
#endif
	_actuator_motors_pub.advertise();
	_tune_control_pub.advertise();
#ifdef __PX4_POSIX
	param_find("MC_RAPTOR_RTGT");
	param_find("MC_RAPTOR_RTDEC");
	param_find("MC_RAPTOR_RREC");
	_research_recovery_pub.advertise();
#endif
}
void Raptor::reset()
{

	trajectory_setpoint_dt_index = 0;
	trajectory_setpoint_dts_full = false;
	trajectory_setpoint_invalid_count = 0;
	trajectory_setpoint_dt_max_since_reset = 0;
	timestamp_last_trajectory_setpoint_set = false;


	for (TI action_i = 0; action_i < EXECUTOR_SPEC::OUTPUT_DIM; action_i++) {
		this->previous_action[action_i] = RESET_PREVIOUS_ACTION_VALUE;
	}

	rlt::reset(device, executor, policy, rng);
}

Raptor::~Raptor()
{
	perf_free(_loop_perf);
	perf_free(_loop_interval_perf);
}

#ifdef MC_RAPTOR_EMBED_POLICY
bool Raptor::test_policy()
{
#else
bool Raptor::test_policy(FILE *f, TI input_offset, TI output_offset)
{
#endif
	using namespace rl_tools::inference::applications::l2f;
#ifndef RL_TOOLS_DISABLE_TEST
	// This tests the policy using a known input output pair that has been saved into the policy checkpoint to verify that it has been loaded correctly
	using POLICY = EXECUTOR_CONFIG::POLICY_TEST;
	POLICY::template Buffer<false> buffers_test;
	POLICY::State<false> policy_state_test;
	rl_tools::Tensor<rl_tools::tensor::Specification<EXECUTOR_CONFIG::TYPE_POLICY::DEFAULT, TI, rl_tools::tensor::Shape<TI, 1, POLICY::OUTPUT_SHAPE::LAST>, false>>
			test_output;
	rl_tools::Mode<rl_tools::mode::Evaluation<>> mode;
	using EXAMPLE_INPUT_SPEC = MC_RAPTOR_EXAMPLE_NAMESPACE::input::SPEC;
	using EXAMPLE_OUTPUT_SPEC = MC_RAPTOR_EXAMPLE_NAMESPACE::output::SPEC;
	float acc = 0;
	uint64_t num_values = 0;
	rl_tools::inference::applications::l2f::Action<EXECUTOR_SPEC> action;

	for (TI batch_i = 0; batch_i < EXECUTOR_CONFIG::TEST_BATCH_SIZE_ACTUAL; batch_i++) {
		rl_tools::reset(device, policy, policy_state_test, rng);

		for (TI step_i = 0; step_i < EXECUTOR_CONFIG::TEST_SEQUENCE_LENGTH_ACTUAL; step_i++) {
#ifdef MC_RAPTOR_EMBED_POLICY
			const auto step_input = rl_tools::view(device, MC_RAPTOR_EXAMPLE_NAMESPACE::input::container, step_i);
			const auto batch_input = rl_tools::view_range(device, step_input, batch_i, rlt::tensor::ViewSpec<0, 1> {});
			const auto step_output_target = rl_tools::view(device, MC_RAPTOR_EXAMPLE_NAMESPACE::output::container, step_i);
			const auto batch_output_target = rl_tools::view_range(device, step_output_target, batch_i, rlt::tensor::ViewSpec<0, 1> {});
#else
			rl_tools::Tensor<rl_tools::tensor::Specification<EXECUTOR_CONFIG::TYPE_POLICY::DEFAULT, TI, rl_tools::tensor::Shape<TI, 1, EXAMPLE_INPUT_SPEC::SHAPE::LAST>, false>>
					batch_input;
			rl_tools::Tensor<rl_tools::tensor::Specification<EXECUTOR_CONFIG::TYPE_POLICY::DEFAULT, TI, rl_tools::tensor::Shape<TI, 1, EXAMPLE_OUTPUT_SPEC::SHAPE::LAST>, false>>
					batch_output_target;
			fseek(f, input_offset + (step_i * EXAMPLE_INPUT_SPEC::STRIDE::FIRST + batch_i * EXAMPLE_INPUT_SPEC::STRIDE::template GET<1>)*sizeof(
				      EXAMPLE_INPUT_SPEC::T), SEEK_SET);
			fread(batch_input._data, sizeof(EXAMPLE_INPUT_SPEC::T), EXAMPLE_INPUT_SPEC::SHAPE::LAST, f);
			fseek(f, output_offset + (step_i * EXAMPLE_OUTPUT_SPEC::STRIDE::FIRST + batch_i * EXAMPLE_OUTPUT_SPEC::STRIDE::template GET<1>)*sizeof(
				      EXAMPLE_OUTPUT_SPEC::T), SEEK_SET);
			fread(batch_output_target._data, sizeof(EXAMPLE_OUTPUT_SPEC::T), EXAMPLE_OUTPUT_SPEC::SHAPE::LAST, f);
#endif
			rl_tools::utils::assert_exit(device, !rl_tools::is_nan(device, batch_input), "input is nan");
			rl_tools::evaluate_step(device, policy, batch_input, policy_state_test, test_output, buffers_test, rng, mode);
			rl_tools::utils::assert_exit(device, !rl_tools::is_nan(device, test_output), "output is nan");

			for (TI action_i = 0; action_i < EXECUTOR_CONFIG::OUTPUT_DIM; action_i++) {
				acc += rl_tools::math::abs(device.math, rl_tools::get(device, test_output, 0, action_i) - rl_tools::get(device, batch_output_target, 0,
							   action_i));
				num_values += 1;
				rl_tools::utils::assert_exit(device, !rl_tools::math::is_nan(device.math, acc), "output is nan");

				if (batch_i == 0 && step_i == EXECUTOR_CONFIG::TEST_SEQUENCE_LENGTH_ACTUAL - 1) {
					action.action[action_i] = rl_tools::get(device, test_output, 0, action_i);
				}
			}
		}
	}

	float abs_diff = acc / num_values;
	PX4_INFO("Checkpoint test diff: %f", (double)abs_diff);

	for (TI output_i = 0; output_i < EXECUTOR_CONFIG::OUTPUT_DIM; output_i++) {
		PX4_INFO("output[%d]: %f", (int)output_i, (double)action.action[output_i]);
	}

	constexpr float EPSILON = 1e-5;

	bool healthy = abs_diff < EPSILON;

	if (!healthy) {
		PX4_ERR("Checkpoint test failed with diff %.10f", (double)abs_diff);
		return false;

	} else {
		PX4_INFO("Checkpoint test passed with diff %.10f", (double)abs_diff);
		return true;
	}

#else
	return 0;
#endif
}

bool Raptor::init()
{
#ifdef __PX4_POSIX
    _p12_pub.advertise();
#endif
	this->init_time = hrt_absolute_time();

	if (!_vehicle_angular_velocity_sub.registerCallback()) {
		PX4_ERR("vehicle_angular_velocity_sub callback registration failed");
		return false;
	}

#ifndef MC_RAPTOR_EMBED_POLICY
	const char *path = PX4_STORAGEDIR "/raptor/policy.tar";

	struct stat st;
	bool file_exists = (stat(path, &st) == 0);

	if (file_exists) {
		PX4_INFO("Policy checkpoint %s exists", path);
		FILE *f = fopen(path, "rb");

		if (!f) {
			PX4_ERR("Failed to open %s: %s", path, strerror(errno));
			return false;
		}

		if (fseek(f, 0, SEEK_END) != 0) {
			PX4_ERR("fseek failed: %s", strerror(errno));
			fclose(f);
			return false;
		}

		long size = ftell(f);

		if (size < 0) {
			PX4_ERR("ftell failed: %s", strerror(errno));
			fclose(f);
			return false;

		} else {
			rewind(f);
			bool successfully_loaded = false;
			using SPEC = rlt::persist::backends::tar::ReaderGroupSpecification<TI, rlt::persist::backends::tar::PosixFileData<TI>>;

			rlt::persist::backends::tar::ReaderGroup<SPEC> reader_group;
			reader_group.data.f = f;
			reader_group.data.size = size;
			auto actor_group = rlt::get_group(device, reader_group, "actor");
			successfully_loaded = rlt::load(device, policy, actor_group);
			constexpr TI METADATA_BUFFER_SIZE = 256;
			char metadata_buffer[METADATA_BUFFER_SIZE];
			TI read_size = 0;
			rlt::persist::backends::tar::get(device, reader_group.data, "actor/meta", metadata_buffer, METADATA_BUFFER_SIZE, read_size);
			TI checkpoint_name_position = 0;
			TI checkpoint_name_len = 0;

			if (rlt::persist::backends::tar::seek_in_metadata(device, metadata_buffer, METADATA_BUFFER_SIZE, "checkpoint_name",
					checkpoint_name_position, checkpoint_name_len)) {
				strncpy(checkpoint_name, metadata_buffer + checkpoint_name_position, CHECKPOINT_NAME_LENGTH);
				checkpoint_name[checkpoint_name_len < CHECKPOINT_NAME_LENGTH ? checkpoint_name_len : CHECKPOINT_NAME_LENGTH - 1] = '\0';

			} else {
				PX4_ERR("Failed to get checkpoint name from metadata");
				return false;
			}

			if (successfully_loaded) {
				PX4_INFO("Policy loaded from file %s", path);
				TI input_offset = 0;
				TI input_size = 0;
				rlt::persist::backends::tar::seek(device, reader_group.data, "example/input/data", input_offset, input_size);
				PX4_INFO("Input offset: %d", (int)input_offset);
				TI output_offset = 0;
				TI output_size = 0;
				rlt::persist::backends::tar::seek(device, reader_group.data, "example/output/data", output_offset, output_size);
				PX4_INFO("Output offset: %d", (int)output_offset);

				if (!test_policy(f, input_offset, output_offset)) {
					PX4_ERR("Checkpoint test failed");
					return false;
				}

			} else {
				PX4_ERR("Failed to load policy from file %s", path);
				return false;
			}

			fclose(f);
		}

	} else {
		PX4_INFO("File %s does not exist", path);
		return false;
	}

#else

	strncpy(checkpoint_name, MC_RAPTOR_META_NAMESPACE::name, CHECKPOINT_NAME_LENGTH);

	if (!test_policy()) {
		PX4_ERR("Checkpoint test failed");
		return false;
	}

#endif
	PX4_INFO("Checkpoint name: %s", checkpoint_name);


	register_ext_component_request_s register_ext_component_request{};
	register_ext_component_request.timestamp = hrt_absolute_time();
	strncpy(register_ext_component_request.name, "RAPTOR", sizeof(register_ext_component_request.name) - 1);
	register_ext_component_request.request_id = Raptor::EXT_COMPONENT_REQUEST_ID;
	register_ext_component_request.px4_ros2_api_version = register_ext_component_request_s::LATEST_PX4_ROS2_API_VERSION;
	register_ext_component_request.register_arming_check = true;
	register_ext_component_request.register_mode = true;
	register_ext_component_request.enable_replace_internal_mode = _param_mc_raptor_offboard.get();
	register_ext_component_request.replace_internal_mode = vehicle_status_s::NAVIGATION_STATE_OFFBOARD;
	register_ext_component_request.request_offboard_setpoints = true;
	_register_ext_component_request_pub.publish(register_ext_component_request);

	int32_t imu_gyro_ratemax = _param_imu_gyro_ratemax.get();

	if (imu_gyro_ratemax % POLICY_CONTROL_FREQUENCY_TRAINING != 0) {
		PX4_WARN("IMU_GYRO_RATEMAX=%d Hz is not a multiple of the training frequency (%d Hz)", (int)imu_gyro_ratemax,
			 (int)POLICY_CONTROL_FREQUENCY_TRAINING);
	}

	int32_t force_sync_native = imu_gyro_ratemax / POLICY_CONTROL_FREQUENCY_TRAINING;
	executor.executor.force_sync_native = force_sync_native;
	executor.executor.force_sync_native_initialized = true;
	PX4_INFO("IMU_GYRO_RATEMAX=%d Hz", (int)imu_gyro_ratemax);
	PX4_INFO("POLICY_CONTROL_FREQUENCY_TRAINING=%d Hz", (int)POLICY_CONTROL_FREQUENCY_TRAINING);
	PX4_INFO("Setting force_sync_native = %d Hz / %d Hz = %d", (int)imu_gyro_ratemax, (int)POLICY_CONTROL_FREQUENCY_TRAINING,
		 (int)force_sync_native);

	this->use_internal_reference = _param_mc_raptor_intref.get();

	this->reset();

	return true;
}
template <typename T>
T clip(T x, T max, T min)
{
	if (x > max) {
		return max;
	}

	if (x < min) {
		return min;
	}

	return x;
}
template <typename T>
void quaternion_multiplication(T q1[4], T q2[4], T q_res[4])
{
	q_res[0] = q1[0] * q2[0] - q1[1] * q2[1] - q1[2] * q2[2] - q1[3] * q2[3];
	q_res[1] = q1[0] * q2[1] + q1[1] * q2[0] + q1[2] * q2[3] - q1[3] * q2[2];
	q_res[2] = q1[0] * q2[2] - q1[1] * q2[3] + q1[2] * q2[0] + q1[3] * q2[1];
	q_res[3] = q1[0] * q2[3] + q1[1] * q2[2] - q1[2] * q2[1] + q1[3] * q2[0];
}
template <typename T>
void quaternion_conjugate(T q[4], T q_res[4])
{
	q_res[0] = +q[0];
	q_res[1] = -q[1];
	q_res[2] = -q[2];
	q_res[3] = -q[3];
}
template <typename T>
void quaternion_to_rotation_matrix(T q[4], T R[9])
{
	// row-major
	T qw = q[0];
	T qx = q[1];
	T qy = q[2];
	T qz = q[3];

	R[0] = 1 - 2 * qy * qy - 2 * qz * qz;
	R[1] =     2 * qx * qy - 2 * qw * qz;
	R[2] =     2 * qx * qz + 2 * qw * qy;
	R[3] =     2 * qx * qy + 2 * qw * qz;
	R[4] = 1 - 2 * qx * qx - 2 * qz * qz;
	R[5] =     2 * qy * qz - 2 * qw * qx;
	R[6] =     2 * qx * qz - 2 * qw * qy;
	R[7] =     2 * qy * qz + 2 * qw * qx;
	R[8] = 1 - 2 * qx * qx - 2 * qy * qy;
}

template <typename T>
void rotate_vector(T R[9], T v[3], T v_rotated[3])
{
	v_rotated[0] = R[0] * v[0] + R[1] * v[1] + R[2] * v[2];
	v_rotated[1] = R[3] * v[0] + R[4] * v[1] + R[5] * v[2];
	v_rotated[2] = R[6] * v[0] + R[7] * v[1] + R[8] * v[2];
}

void Raptor::observe(rl_tools::inference::applications::l2f::Observation<EXECUTOR_SPEC> &observation)
{
#ifdef __PX4_POSIX
	// P7: while the rate-limited recovery is active the network observes the virtual target (horizontal position and
	// velocity) instead of the external setpoint; the setpoint is restored when observe() returns.
	const ResearchRecoveryView research_recovery_view(*this);
#endif
	// converting from FRD to FLU
#ifdef __PX4_POSIX
    if (_p11_enabled) {
        struct timespec p11_pre_begin{};clock_gettime(CLOCK_MONOTONIC,&p11_pre_begin);
        _p11.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
        _p11.local_position_sample=_vehicle_local_position.timestamp_sample;
        _p11.attitude_sample=_vehicle_attitude.timestamp_sample;
        _p11.stale=previous_trajectory_setpoint_stale;
        _p11.recovery_active=_research_recovery.active;
        _p11.target_yaw=_trajectory_setpoint.yaw;
        float p11_memory[32]{};research_get(p11_memory);
        for (TI i=0;i<16;i++) _p11.gru_before[i]=p11_memory[i];
        for (TI i=0;i<4;i++) {_p11.attitude[i]=_vehicle_attitude.q[i];_p11.previous_action_before[i]=previous_action[i];}
        for (TI i=0;i<3;i++) {
            _p11.position[i]=position[i];_p11.velocity[i]=linear_velocity[i];
            _p11.angular_velocity[i]=_vehicle_angular_velocity.xyz[i];
            _p11.network_target_position[i]=_trajectory_setpoint.position[i];
            _p11.network_target_velocity[i]=_trajectory_setpoint.velocity[i];
        }
        struct timespec p11_pre_end{};clock_gettime(CLOCK_MONOTONIC,&p11_pre_end);
        _p11_pre_ns=static_cast<uint64_t>(p11_pre_end.tv_sec-p11_pre_begin.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_pre_end.tv_nsec-p11_pre_begin.tv_nsec);
    }
#endif
	T Rt_inv[9];

	{
		// Orientation
		// FRD to FLU
		T q_target[4];
		q_target[0] = cosf(0.5f * _trajectory_setpoint.yaw); // minus because the setpoint yaw is in NED
		q_target[1] = 0;
		q_target[2] = 0;
		q_target[3] = sinf(0.5f * _trajectory_setpoint.yaw);

		T qt[4], qtc[4], qr[4];
		qt[0] = +q_target[0]; // conjugate to build the difference between setpoint and current
		qt[1] = +q_target[1];
		qt[2] = -q_target[2];
		qt[3] = -q_target[3];
		quaternion_conjugate(qt, qtc);
		quaternion_to_rotation_matrix(qtc, Rt_inv);

		qr[0] = +_vehicle_attitude.q[0];
		qr[1] = +_vehicle_attitude.q[1];
		qr[2] = -_vehicle_attitude.q[2];
		qr[3] = -_vehicle_attitude.q[3];
		// qr = qt * qd
		// qd = qt' * qr
		T qd[4];
		quaternion_multiplication(qtc, qr, qd);

		observation.orientation[0] = qd[0];
		observation.orientation[1] = qd[1];
		observation.orientation[2] = qd[2];
		observation.orientation[3] = qd[3];
	}

	{
		// Position
		T p[3], pt[3]; // FLU
		p[0] = +(position[0] - _trajectory_setpoint.position[0]);
		p[1] = -(position[1] - _trajectory_setpoint.position[1]);
		p[2] = -(position[2] - _trajectory_setpoint.position[2]);
		rotate_vector(Rt_inv, p, pt); // The position and velocity error are in the target frame
		observation.position[0] = clip(pt[0], max_position_error, -max_position_error);
		observation.position[1] = clip(pt[1], max_position_error, -max_position_error);
		observation.position[2] = clip(pt[2], max_position_error, -max_position_error);
	}
	{
		// Linear Velocity
		T v[3], vt[3];
		v[0] = +(linear_velocity[0] - _trajectory_setpoint.velocity[0]);
		v[1] = -(linear_velocity[1] - _trajectory_setpoint.velocity[1]);
		v[2] = -(linear_velocity[2] - _trajectory_setpoint.velocity[2]);
		rotate_vector(Rt_inv, v, vt);
		observation.linear_velocity[0] = clip(vt[0], max_velocity_error, -max_velocity_error);
		observation.linear_velocity[1] = clip(vt[1], max_velocity_error, -max_velocity_error);
		observation.linear_velocity[2] = clip(vt[2], max_velocity_error, -max_velocity_error);
	}
	{
		// Angular Velocity
		observation.angular_velocity[0] = +_vehicle_angular_velocity.xyz[0];
		observation.angular_velocity[1] = -_vehicle_angular_velocity.xyz[1];
		observation.angular_velocity[2] = -_vehicle_angular_velocity.xyz[2];
	}

	for (TI action_i = 0; action_i < EXECUTOR_CONFIG::OUTPUT_DIM; action_i++) {
		observation.previous_action[action_i] = this->previous_action[action_i];
	}
}


#ifdef __PX4_POSIX
void Raptor::research_exit_lifecycle(bool active) {
    static const param_t rsh=param_find("MC_RAPTOR_RSH");
    int32_t enabled=0;param_get(rsh,&enabled);
    if (!enabled || !_research_exit.due(active)) return;
    float live[32]{};research_get(live);
    _research_exit.store(live);
    research_memory_s m{};
    m.timestamp=hrt_absolute_time();m.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    m.kind=research_memory_s::KIND_EXIT;m.entry_mode=_research_mode;m.active=false;
    for (TI i=0;i<16;i++) m.gru[i]=_research_exit.memory[i];
    for (TI i=0;i<4;i++) {m.previous_action[i]=_research_exit.memory[16+i];m.classic_action[i]=NAN;}
    m.clipped_total=_research_clipped_total;m.classic_unavailable_total=_research_classic_unavailable_total;
    _research_memory_pub.publish(m);
    PX4_INFO("Research exit memory stored");
}
#endif

void Raptor::updateArmingCheckReply()
{
	if (flightmode_state == FlightModeState::CONFIGURED) {
		if (_arming_check_request_sub.updated()) {
			arming_check_request_s arming_check_request;
			_arming_check_request_sub.copy(&arming_check_request);
			arming_check_reply_s arming_check_reply;
			arming_check_reply.timestamp = hrt_absolute_time();
			arming_check_reply.request_id = arming_check_request.request_id;
			arming_check_reply.registration_id = ext_component_arming_check_id;
			arming_check_reply.health_component_index = arming_check_reply.HEALTH_COMPONENT_INDEX_NONE;
			arming_check_reply.num_events = 0;
			arming_check_reply.can_arm_and_run = can_arm;
			arming_check_reply.mode_req_angular_velocity = true;
			arming_check_reply.mode_req_local_position = true;
			arming_check_reply.mode_req_attitude = true;
			arming_check_reply.mode_req_local_alt = true;
			arming_check_reply.mode_req_home_position = false;
			arming_check_reply.mode_req_mission = false;
			arming_check_reply.mode_req_global_position = false;
			arming_check_reply.mode_req_prevent_arming = false;
			arming_check_reply.mode_req_manual_control = false;
			_arming_check_reply_pub.publish(arming_check_reply);
		}
	}
}


void Raptor::Run()
{
	if (should_exit()) {
		_vehicle_angular_velocity_sub.unregisterCallback();

		if (flightmode_state >= FlightModeState::CONFIGURED) {
			unregister_ext_component_s unregister_ext_component{};
			unregister_ext_component.timestamp = hrt_absolute_time();
			strncpy(unregister_ext_component.name, "RAPTOR", sizeof(unregister_ext_component.name) - 1);
			unregister_ext_component.arming_check_id = ext_component_arming_check_id;
			unregister_ext_component.mode_id = ext_component_mode_id;
			unregister_ext_component.mode_executor_id = -1;
			_unregister_ext_component_pub.publish(unregister_ext_component);
		}

		ScheduleClear();
		exit_and_cleanup(desc);
		return;
	}

	register_ext_component_reply_s register_ext_component_reply;

	if (_register_ext_component_reply_sub.update(&register_ext_component_reply)) {
		if (register_ext_component_reply.request_id == Raptor::EXT_COMPONENT_REQUEST_ID && register_ext_component_reply.success) {
			ext_component_arming_check_id = register_ext_component_reply.arming_check_id;
			ext_component_mode_id = register_ext_component_reply.mode_id;
			flightmode_state = FlightModeState::CONFIGURED;
			PX4_INFO("Raptor mode registration successful, arming_check_id: %d, mode_id: %d", ext_component_arming_check_id, ext_component_mode_id);
		}
	}

	perf_count(_loop_interval_perf);

	perf_begin(_loop_perf);
	hrt_abstime current_time = hrt_absolute_time();

	raptor_status_s status{};
	status.timestamp = current_time;
	status.timestamp_sample = current_time;
	status.exit_reason = raptor_status_s::EXIT_REASON_NONE;
	status.substep = 0;
#ifdef __PX4_POSIX
    struct timespec p11_cycle_begin{};clock_gettime(CLOCK_MONOTONIC,&p11_cycle_begin);
    const uint64_t p11_cycle_start=static_cast<uint64_t>(p11_cycle_begin.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_cycle_begin.tv_nsec);
    static const param_t p11_param=param_find("MC_RAPTOR_P11"), p11_rsh=param_find("MC_RAPTOR_RSH");
    int32_t p11_enable=0,p11_research=0;
    param_get(p11_param,&p11_enable);param_get(p11_rsh,&p11_research);
    _p11_enabled=p11_enable && p11_research;
    if (_p11_enabled) {
        _p11=research_p11_s{};_p11.timestamp=current_time;_p11.sequence=++_p11_sequence;
        struct timespec p11_wall{};clock_gettime(CLOCK_MONOTONIC,&p11_wall);
        _p11.run_wall_ns=static_cast<uint64_t>(p11_wall.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_wall.tv_nsec);
    }
#endif
	status.active = false;
	status.control_interval = NAN;
	status.trajectory_setpoint_dt_mean = NAN;
	status.trajectory_setpoint_dt_max = NAN;
	status.trajectory_setpoint_dt_max_since_activation = NAN;

	if (trajectory_setpoint_dts_full || trajectory_setpoint_dt_index > 0) {
		float trajectory_setpoint_dt_mean = 0;
		float trajectory_setpoint_dt_max = 0;

		for (TI i = 0; i < (trajectory_setpoint_dts_full ? NUM_TRAJECTORY_SETPOINT_DTS : trajectory_setpoint_dt_index); i++) {
			TI index = trajectory_setpoint_dts_full ? i : trajectory_setpoint_dt_index - 1 - i;
			trajectory_setpoint_dt_mean += trajectory_setpoint_dts[index];

			if (trajectory_setpoint_dts[index] > trajectory_setpoint_dt_max) {
				trajectory_setpoint_dt_max = trajectory_setpoint_dts[index];
			}
		}

		if (trajectory_setpoint_dt_max > trajectory_setpoint_dt_max_since_reset) {
			trajectory_setpoint_dt_max_since_reset = trajectory_setpoint_dt_max;
		}

		trajectory_setpoint_dt_mean /= NUM_TRAJECTORY_SETPOINT_DTS;
		status.trajectory_setpoint_dt_mean = trajectory_setpoint_dt_mean;
		status.trajectory_setpoint_dt_max = trajectory_setpoint_dt_max;
		status.trajectory_setpoint_dt_max_since_activation = trajectory_setpoint_dt_max_since_reset;
	}

	status.subscription_update_vehicle_status = _vehicle_status_sub.update(&_vehicle_status);

	if (status.subscription_update_vehicle_status) {
		timestamp_last_vehicle_status = current_time;
		timestamp_last_vehicle_status_set = true;
	}

	bool next_active = flightmode_state == FlightModeState::CONFIGURED && timestamp_last_vehicle_status_set && _vehicle_status.nav_state == ext_component_mode_id;

#ifdef __PX4_POSIX
    research_exit_lifecycle(next_active);
#endif
	if (!previous_active && next_active) {

		// Activate setpoint type
		setpoint_config_s setpoint_config{};
		setpoint_config.timestamp = hrt_absolute_time();
		setpoint_config.source_id = ext_component_mode_id;
		setpoint_config.type = setpoint_config_s::TYPE_DIRECT_ACTUATORS;
		setpoint_config.should_apply = true;
		_setpoint_config_pub.publish(setpoint_config);

#ifdef __PX4_POSIX
        int32_t preserve=0, enabled=0;
        param_get(param_find("MC_RAPTOR_RINI"),&preserve);
        param_get(param_find("MC_RAPTOR_RSH"),&enabled);
        float memory[32]{};
        if(preserve==1 && enabled)research_get(memory);
        const int32_t entry_mode=enabled?preserve:0;
        float entry_before[32]{};research_get(entry_before);
        float entry_classic[4]{};
        const bool entry_classic_valid=handover_research::needs_classic_action(entry_mode) && research_classic_action(entry_classic);
#endif
        this->reset();
#ifdef __PX4_POSIX
        if(preserve==1 && enabled)research_set(memory,false);
        PX4_INFO("Research mode-entry memory: %s",preserve==1 && enabled?"preserved; timing rebased":"reset");
        research_entry(entry_mode,entry_before,entry_classic,entry_classic_valid);
#endif
		PX4_INFO("Resetting Inference Executor (Recurrent State)");

	} else {
		if (previous_active && !next_active) {
			PX4_INFO("inactive");
		}
	}
#ifdef __PX4_POSIX
    research_teacher_force(next_active);
#endif

	bool angular_velocity_update = false;
	status.subscription_update_angular_velocity = _vehicle_angular_velocity_sub.update(&_vehicle_angular_velocity);
#ifdef __PX4_POSIX
    // Schedule another work item until the queue is drained, including early returns.
    if(_vehicle_angular_velocity_sub.updated())ScheduleNow();
#endif

	if (status.subscription_update_angular_velocity) {
		timestamp_last_angular_velocity = current_time;
		timestamp_last_angular_velocity_set = true;
		angular_velocity_update = true;
	}

	status.timestamp_last_vehicle_angular_velocity = current_time;
	status.timestamp_sample = _vehicle_angular_velocity.timestamp_sample;

	status.subscription_update_local_position = _vehicle_local_position_sub.update(&_vehicle_local_position);

	if (status.subscription_update_local_position) {
		timestamp_last_local_position = current_time;
		timestamp_last_local_position_set = true;
	}

	status.timestamp_last_vehicle_local_position = current_time;

	status.subscription_update_attitude = _vehicle_attitude_sub.update(&_vehicle_attitude);

	if (status.subscription_update_attitude) {
		timestamp_last_attitude = current_time;
		timestamp_last_attitude_set = true;
	}

	status.timestamp_last_vehicle_attitude = timestamp_last_attitude;

#ifdef __PX4_POSIX
    static const param_t p12_on=param_find("MC_RAPTOR_P12"),p12_ph=param_find("MC_RAPTOR_P12PH"),p12_r=param_find("MC_RAPTOR_P12R");
    int32_t p12_enable=0,p12_phase=0,p12_repair=0;
    param_get(p12_on,&p12_enable);param_get(p12_ph,&p12_phase);param_get(p12_r,&p12_repair);
    _p12_enabled=p12_enable && _p11_enabled;
    _p12_repair=p12_repair!=0;
    if (!previous_active && next_active) _p12_seen=false;
    _p12=research_p12_s{};
    if (_p12_enabled) {
        _p12.timestamp=current_time;_p12.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
        _p12.active=next_active;_p12.requested_phase=p12_phase;_p12.repair_requested=_p12_repair;
        _p12.lp_updated=status.subscription_update_local_position;_p12.attitude_updated=status.subscription_update_attitude;
        _p12.last_gru_sample_before=_last_gru_sample;
        _p12.call_index_before=executor.executor.intermediate_step;
        _p12.history_count_before=executor.steps_since_original_control_step;
        for (TI i=0;i<4;i++) _p12.history_before[i]=executor.action_history[0][i];
        _p12.predicted_commit=!executor.executor.last_control_timestamp_original_set ||
            (executor.executor.force_sync_native!=0 && executor.executor.intermediate_step%executor.executor.force_sync_native==0);
        _p12.gate_pending=_trajectory_setpoint_sub.updated();
        _p12.gate_permit=handover_research::p12_delivery_allowed(p12_phase,next_active,
            executor.executor.last_control_timestamp_original_set,executor.executor.intermediate_step,executor.executor.force_sync_native);
        struct timespec p12_begin{};clock_gettime(CLOCK_MONOTONIC,&p12_begin);
        _p12.read_begin_wall_ns=static_cast<uint64_t>(p12_begin.tv_sec)*1000000000ULL+static_cast<uint64_t>(p12_begin.tv_nsec);
    }
#endif
	trajectory_setpoint_s temp_trajectory_setpoint;
	bool use_external_reference = !use_internal_reference;
#ifdef __PX4_POSIX
    // P12 native-state delivery gate: do not consume on the other phase.
    // The uORB latest value remains pending; timestamps and the strict guard are untouched.
    status.subscription_update_trajectory_setpoint = use_external_reference &&
        (!_p12_enabled || _p12.gate_permit) && _trajectory_setpoint_sub.update(&temp_trajectory_setpoint);
    if (_p12_enabled) {
        struct timespec p12_end{};clock_gettime(CLOCK_MONOTONIC,&p12_end);
        _p12.read_end_wall_ns=static_cast<uint64_t>(p12_end.tv_sec)*1000000000ULL+static_cast<uint64_t>(p12_end.tv_nsec);
    }
#else
	status.subscription_update_trajectory_setpoint = use_external_reference && _trajectory_setpoint_sub.update(&temp_trajectory_setpoint);
#endif

	if (status.subscription_update_trajectory_setpoint) {
		if (
			PX4_ISFINITE(temp_trajectory_setpoint.position[0]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.position[1]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.position[2]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.yaw) &&
			PX4_ISFINITE(temp_trajectory_setpoint.velocity[0]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.velocity[1]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.velocity[2]) &&
			PX4_ISFINITE(temp_trajectory_setpoint.yawspeed)
		) {
			if (timestamp_last_trajectory_setpoint_set) {
				trajectory_setpoint_dts[trajectory_setpoint_dt_index] = current_time - timestamp_last_trajectory_setpoint;
				trajectory_setpoint_dt_index++;

				if (trajectory_setpoint_dt_index == NUM_TRAJECTORY_SETPOINT_DTS) {
					if (next_active && !trajectory_setpoint_dts_full) {
						PX4_INFO("trajectory_setpoint_dts_full");
					}

					trajectory_setpoint_dts_full = true;
					trajectory_setpoint_dt_index = 0;
				}
			}

			timestamp_last_trajectory_setpoint_set = true;
			status.timestamp_last_trajectory_setpoint = current_time;
			timestamp_last_trajectory_setpoint = current_time;
			_trajectory_setpoint = temp_trajectory_setpoint;

		} else {
			trajectory_setpoint_invalid_count++;

			if (next_active && trajectory_setpoint_invalid_count % TRAJECTORY_SETPOINT_INVALID_COUNT_WARNING_INTERVAL == 0) {
				PX4_WARN("trajectory_setpoint invalid, count: %d", (int)trajectory_setpoint_invalid_count);
			}
		}
	}

#ifdef __PX4_POSIX
    if (_p11_enabled) {
        _p11.subscription_updated=status.subscription_update_trajectory_setpoint;
        _p11.external_valid=_p11.subscription_updated && status.timestamp_last_trajectory_setpoint==current_time;
        _p11.external_timestamp=_p11.subscription_updated?temp_trajectory_setpoint.timestamp:0;
        _p11.last_valid_read_us=timestamp_last_trajectory_setpoint_set?timestamp_last_trajectory_setpoint:0;
        _p11.invalid_total=trajectory_setpoint_invalid_count;
        for (TI i=0;i<3;i++) {
            _p11.external_position[i]=_p11.external_valid?temp_trajectory_setpoint.position[i]:NAN;
            _p11.external_velocity[i]=_p11.external_valid?temp_trajectory_setpoint.velocity[i]:NAN;
        }
        _p11.external_yaw=_p11.external_valid?temp_trajectory_setpoint.yaw:NAN;
        struct timespec p11_read{};clock_gettime(CLOCK_MONOTONIC,&p11_read);
        _p11.read_wall_ns=static_cast<uint64_t>(p11_read.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_read.tv_nsec);
    }
#endif
	constexpr bool PUBLISH_NON_COMPLETE_STATUS = true;
#ifdef __PX4_POSIX
    if (_p12b_enabled) {
        _p12b.read_updated=status.subscription_update_trajectory_setpoint;
        _p12b.read_valid=_p11.external_valid;
        _p12b.last_valid_read_post=timestamp_last_trajectory_setpoint_set?timestamp_last_trajectory_setpoint:0;
        _p12b.external_timestamp=_p11.external_timestamp;
        _p12b.invalid_total=trajectory_setpoint_invalid_count;
        _p12b_pub.publish(_p12b);
    }
#endif

	if (!angular_velocity_update) {
		status.exit_reason = raptor_status_s::EXIT_REASON_NO_ANGULAR_VELOCITY_UPDATE;

		if constexpr(PUBLISH_NON_COMPLETE_STATUS) {
			_raptor_status_pub.publish(status);
		}

		updateArmingCheckReply();
		return;
	}

	if (!timestamp_last_angular_velocity_set || !timestamp_last_local_position_set || !timestamp_last_attitude_set) {
		status.exit_reason = raptor_status_s::EXIT_REASON_NOT_ALL_OBSERVATIONS_SET;
		status.vehicle_angular_velocity_stale = !timestamp_last_angular_velocity_set;
		status.vehicle_local_position_stale = !timestamp_last_local_position_set;
		status.vehicle_attitude_stale = !timestamp_last_attitude_set;

		if constexpr(PUBLISH_NON_COMPLETE_STATUS) {
			_raptor_status_pub.publish(status);
		}

		can_arm = false;
		updateArmingCheckReply();
		return;
	}

	if ((current_time - timestamp_last_angular_velocity) > OBSERVATION_TIMEOUT_ANGULAR_VELOCITY) {
		status.exit_reason = raptor_status_s::EXIT_REASON_ANGULAR_VELOCITY_STALE;

		if constexpr(PUBLISH_NON_COMPLETE_STATUS) {
			_raptor_status_pub.publish(status);
		}

		if (!timeout_message_sent) {
			PX4_ERR("angular velocity timeout");
			timeout_message_sent = true;
		}

		can_arm = false;
		updateArmingCheckReply();
		return;
	}

	if ((current_time - timestamp_last_local_position) > OBSERVATION_TIMEOUT_LOCAL_POSITION) {
		status.exit_reason = raptor_status_s::EXIT_REASON_LOCAL_POSITION_STALE;

		if constexpr(PUBLISH_NON_COMPLETE_STATUS) {
			_raptor_status_pub.publish(status);
		}

		if (!timeout_message_sent) {
			PX4_ERR("local position timeout");
			timeout_message_sent = true;
		}

		can_arm = false;
		updateArmingCheckReply();
		return;

	} else {
		position[0] = _vehicle_local_position.x;
		position[1] = _vehicle_local_position.y;
		position[2] = _vehicle_local_position.z;
		linear_velocity[0] = _vehicle_local_position.vx;
		linear_velocity[1] = _vehicle_local_position.vy;
		linear_velocity[2] = _vehicle_local_position.vz;
	}

	// position and linear_velocity are guaranteed to be set after this point
	auto previous_internal_reference = internal_reference;
	internal_reference = static_cast<InternalReference>(_param_mc_raptor_intref.get());
	bool internal_reference_changed = previous_internal_reference != internal_reference;

	if (internal_reference_changed) {
		PX4_INFO("internal reference changed from %d to %d", (int)previous_internal_reference, (int)internal_reference);
	}

	if (use_internal_reference && internal_reference != InternalReference::NONE) {
		if (next_active && (!previous_active || internal_reference_changed || internal_reference_params_changed)) {
			internal_reference_activation_position[0] = position[0];
			internal_reference_activation_position[1] = - position[1];
			internal_reference_activation_position[2] = - position[2];
			internal_reference_activation_orientation[0] = _vehicle_attitude.q[0];
			internal_reference_activation_orientation[1] = _vehicle_attitude.q[1];
			internal_reference_activation_orientation[2] = -_vehicle_attitude.q[2];
			internal_reference_activation_orientation[3] = -_vehicle_attitude.q[3];
			internal_reference_activation_time = current_time;
			PX4_INFO("internal reference activated at: %f %f %f", (double)internal_reference_activation_position[0],
				 (double)internal_reference_activation_position[1], (double)internal_reference_activation_position[2]);
			internal_reference_params_changed = false;
		}

		Setpoint setpoint{};

		if (internal_reference == InternalReference::LISSAJOUS) {
			setpoint = lissajous(static_cast<T>(current_time - internal_reference_activation_time) / 1000000, lissajous_params);

		} else {
			PX4_ERR("internal reference type not supported");
		}

		auto &q = internal_reference_activation_orientation;
		matrix::Quatf q_activation_frame(q[0], q[1], q[2], q[3]);
		matrix::Vector3f position_activation_frame = q_activation_frame.rotateVector(matrix::Vector3f(setpoint.position[0], setpoint.position[1],
				setpoint.position[2]));
		matrix::Vector3f linear_velocity_activation_frame = q_activation_frame.rotateVector(matrix::Vector3f(setpoint.linear_velocity[0],
				setpoint.linear_velocity[1], setpoint.linear_velocity[2]));

		_trajectory_setpoint.position[0] = +(internal_reference_activation_position[0] + position_activation_frame(0));
		_trajectory_setpoint.position[1] = -(internal_reference_activation_position[1] + position_activation_frame(1));
		_trajectory_setpoint.position[2] = -(internal_reference_activation_position[2] + position_activation_frame(2));
		_trajectory_setpoint.yaw = - atan2f(2.0f * (q[1] * q[2] + q[0] * q[3]), 1.0f - 2.0f * (q[2] * q[2] + q[3] * q[3])) - setpoint.yaw;
		_trajectory_setpoint.velocity[0] = +linear_velocity_activation_frame(0);
		_trajectory_setpoint.velocity[1] = -linear_velocity_activation_frame(1);
		_trajectory_setpoint.velocity[2] = -linear_velocity_activation_frame(2);
		_trajectory_setpoint.yawspeed = -setpoint.yaw_rate;
		timestamp_last_trajectory_setpoint_set = true;
		status.timestamp_last_trajectory_setpoint = current_time;
		timestamp_last_trajectory_setpoint = current_time;

		status.internal_reference_position[0] = _trajectory_setpoint.position[0];
		status.internal_reference_position[1] = _trajectory_setpoint.position[1];
		status.internal_reference_position[2] = _trajectory_setpoint.position[2];
		status.internal_reference_linear_velocity[0] = _trajectory_setpoint.velocity[0];
		status.internal_reference_linear_velocity[1] = _trajectory_setpoint.velocity[1];
		status.internal_reference_linear_velocity[2] = _trajectory_setpoint.velocity[2];
	}

	if ((current_time - timestamp_last_attitude) > OBSERVATION_TIMEOUT_ATTITUDE) {
		status.exit_reason = raptor_status_s::EXIT_REASON_ATTITUDE_STALE;

		if constexpr(PUBLISH_NON_COMPLETE_STATUS) {
			_raptor_status_pub.publish(status);
		}

		if (!timeout_message_sent) {
			PX4_ERR("attitude timeout");
			timeout_message_sent = true;
		}

		can_arm = false;
		updateArmingCheckReply();
		return;
	}

	timeout_message_sent = false;

	// is ready to control at this point
	can_arm = true;
	updateArmingCheckReply();

	if (!timestamp_last_trajectory_setpoint_set || use_internal_reference
	    || (current_time - timestamp_last_trajectory_setpoint) > TRAJECTORY_SETPOINT_TIMEOUT) {
		status.trajectory_setpoint_stale = true;

		if (!previous_trajectory_setpoint_stale || (!previous_active && next_active)) {
			_trajectory_setpoint.position[0] = position[0];
			_trajectory_setpoint.position[1] = position[1];
			_trajectory_setpoint.position[2] = position[2];
			auto &q = _vehicle_attitude.q;
			_trajectory_setpoint.yaw = atan2f(2.0f * (q[1] * q[2] + q[0] * q[3]), 1.0f - 2.0f * (q[2] * q[2] + q[3] * q[3]));
			_trajectory_setpoint.velocity[0] = 0;
			_trajectory_setpoint.velocity[1] = 0;
			_trajectory_setpoint.velocity[2] = 0;
			_trajectory_setpoint.yawspeed = 0;
#ifdef __PX4_POSIX
			research_target_capture(!previous_active && next_active, next_active);
#endif

			if (!previous_trajectory_setpoint_stale) {
				PX4_WARN("trajectory_setpoint turned stale at: %f %f %f, yaw: %f %llu / %llu us", (double)position[0], (double)position[1],
					 (double)position[2],
					 (double)_trajectory_setpoint.yaw, (unsigned long long)(current_time - timestamp_last_trajectory_setpoint),
					 (unsigned long long)(TRAJECTORY_SETPOINT_TIMEOUT));

			} else {
				PX4_WARN("trajectory_setpoint reset due to activation at: %f %f %f, yaw: %f", (double)position[0], (double)position[1], (double)position[2],
					 (double)_trajectory_setpoint.yaw);
			}
		}

		previous_trajectory_setpoint_stale = true;

	} else {
		if (previous_trajectory_setpoint_stale) {
			PX4_WARN("trajectory_setpoint turned non-stale at: %f %f %f", (double)position[0], (double)position[1], (double)position[2]);
			previous_trajectory_setpoint_stale = false;
		}

		status.trajectory_setpoint_stale = false;
	}





#ifdef __PX4_POSIX
	research_target_step(next_active, status.trajectory_setpoint_stale);
	research_recovery_transition(next_active, status.trajectory_setpoint_stale, !previous_active && next_active);
#endif
	rl_tools::inference::applications::l2f::Observation<EXECUTOR_SPEC> observation;
	rl_tools::inference::applications::l2f::Action<EXECUTOR_SPEC> action;
#ifdef __PX4_POSIX
    const auto generation=_vehicle_angular_velocity_sub.get_last_generation();
    if(_sample_generation && generation-_sample_generation>1)_sample_missed+=generation-_sample_generation-1;
    _sample_generation=generation;
    const unsigned input_result=_sample_clock.accept(_vehicle_angular_velocity.timestamp_sample);
    if(input_result) {
        research_timing_s skipped{};
        skipped.timestamp=current_time;skipped.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
        skipped.schema_version=2;skipped.active=next_active;skipped.mode_id=ext_component_mode_id;
        skipped.accepted_total=_sample_clock.accepted;skipped.duplicate_total=_sample_clock.duplicate;
        skipped.regressed_total=_sample_clock.regressed;skipped.source_missed_total=_sample_missed;
        skipped.source_generation=generation;skipped.input_result=input_result;
        skipped.native_total=_native_total;skipped.gru_commit_total=_gru_total;skipped.last_gru_sample=_last_gru_sample;
        skipped.executor_ok=true;skipped.output_finite=true;
        handover_research::TimingRecord skipped_record(skipped);
        perf_end(_loop_perf);return;
    }
#endif
#ifdef __PX4_POSIX
    for (TI i=0;i<16;i++) _research_state._bounds[i]=1.f;
    for (TI i=16;i<20;i++) _research_state._bounds[i]=1.f;
    for (TI i=23;i<26;i++) _research_state._bounds[i]=10.f;
    _research_state.update(next_active,
        [this](float *v) { research_get(v); },
        [this](const float *v, bool reset_state) { research_set(v,reset_state); });
    struct timespec wall_start{}, wall_end{};
    clock_gettime(CLOCK_MONOTONIC,&wall_start);
#endif
	observe(observation);
#ifdef __PX4_POSIX
    const uint32_t executor_dt_us=executor.executor.last_control_timestamp_set ?
        (_vehicle_angular_velocity.timestamp_sample*1000-executor.executor.last_control_timestamp)/1000 : 0;
    const uint32_t native_dt_us=executor.executor.last_control_timestamp_original_set ?
        (_vehicle_angular_velocity.timestamp_sample*1000-executor.executor.last_control_timestamp_original)/1000 : 0;
    hrt_abstime nanoseconds = _vehicle_angular_velocity.timestamp_sample * 1000;
#else
	hrt_abstime nanoseconds = current_time * 1000;
#endif
	auto executor_status = rl_tools::control(device, executor, nanoseconds, policy, observation, action, rng);
#ifdef __PX4_POSIX
    clock_gettime(CLOCK_MONOTONIC,&wall_end);
    research_timing_s timing{};
    timing.timestamp=current_time;
    timing.schema_version=2;
    timing.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    timing.local_position_sample=_vehicle_local_position.timestamp_sample;
    timing.attitude_sample=_vehicle_attitude.timestamp_sample;
    timing.control_start_wall_ns=static_cast<uint64_t>(wall_start.tv_sec)*1000000000ULL+wall_start.tv_nsec;
    timing.control_end_wall_ns=static_cast<uint64_t>(wall_end.tv_sec)*1000000000ULL+wall_end.tv_nsec;
    timing.accepted_total=_sample_clock.accepted;
    timing.duplicate_total=_sample_clock.duplicate;
    timing.regressed_total=_sample_clock.regressed;
    timing.source_generation=_sample_generation;
    timing.source_missed_total=_sample_missed;
    timing.input_dt_us=_sample_clock.dt;
    timing.executor_dt_us=executor_dt_us;
    timing.native_dt_us=native_dt_us;
    timing.executor_called=true;
    timing.native_step=executor_status.source==decltype(executor_status.source)::CONTROL && executor_status.step_type==decltype(executor_status.step_type)::NATIVE;
    timing.gru_committed=timing.native_step && !_research_state.engine.holding;
    if(timing.native_step)++_native_total;
    if(timing.gru_committed){++_gru_total;_last_gru_sample=timing.timestamp_sample;}
    timing.native_total=_native_total;timing.gru_commit_total=_gru_total;timing.last_gru_sample=_last_gru_sample;
    timing.timing_jitter_ok=executor_status.timing_jitter.OK;
    timing.timing_bias_ok=executor_status.timing_bias.OK;
    timing.jitter_ratio=executor_status.timing_jitter.MAGNITUDE;
    timing.bias_ratio=executor_status.timing_bias.MAGNITUDE;
    timing.timestamp_invalid=executor_status.TIMESTAMP_INVALID;
    timing.timestamp_order_invalid=executor_status.LAST_CONTROL_TIMESTAMP_GREATER_THAN_LAST_OBSERVATION_TIMESTAMP;
    timing.inference_duration_us=(wall_end.tv_sec-wall_start.tv_sec)*1000000+(wall_end.tv_nsec-wall_start.tv_nsec)/1000;
    timing.active=next_active;
    timing.executor_ok=executor_status.OK;
    timing.control_step=executor_status.source==decltype(executor_status.source)::CONTROL;
    timing.mode_id=ext_component_mode_id;
    timing.output_finite=true;
    if(timing.control_step)for(TI i=0;i<4;i++) {timing.action[i]=action.action[i];timing.output_finite &= PX4_ISFINITE(action.action[i]);}
    handover_research::TimingRecord timing_record(timing);
    if(_research_state.engine.holding)research_set(_research_state.engine.held,false);
    if(timing.control_step && (!timing.output_finite || executor_status.TIMESTAMP_INVALID || executor_status.LAST_CONTROL_TIMESTAMP_GREATER_THAN_LAST_OBSERVATION_TIMESTAMP)) {
        PX4_ERR("Research guard: invalid inference; actuator publication withheld");
        can_arm=false;updateArmingCheckReply();return;
    }
#endif

#ifdef __PX4_POSIX
    // Logged after the timed observe+control span; the GRU is the committed state after this inference.
    if (executor_status.source==decltype(executor_status.source)::CONTROL)
        research_log_step(next_active,observation.previous_action,executor_status.step_type==decltype(executor_status.step_type)::NATIVE);
#endif
	if (!executor_status.OK) {
		if (executor_status.TIMESTAMP_INVALID) {
			PX4_ERR("RLtools executor error: Timestamp invalid");
		}

		if (executor_status.LAST_CONTROL_TIMESTAMP_GREATER_THAN_LAST_OBSERVATION_TIMESTAMP) {
			PX4_ERR("RLtools executor error: Last control timestamp %llu greater than last observation timestamp %llu",
				(unsigned long long)executor.executor.last_control_timestamp, (unsigned long long)executor.executor.last_observation_timestamp);
		}
	}

	if (executor_status.source != decltype(executor_status.source)::CONTROL) {
		// status.exit_reason = raptor_status_s::EXIT_REASON_EXECUTOR_STATUS_SOURCE_NOT_CONTROL;
		// if constexpr(PUBLISH_NON_COMPLETE_STATUS){
		// 	_raptor_status_pub.publish(status);
		// }
		// Exit early if it is not time to control
		return;
	}


	status.active = next_active;


	// no return after this point!

	raptor_input_s input_msg;
	input_msg.active = status.active;
	static_assert(raptor_input_s::ACTION_DIM == EXECUTOR_CONFIG::OUTPUT_DIM);
	input_msg.timestamp = current_time;
	input_msg.timestamp_sample = _vehicle_angular_velocity.timestamp_sample;

	for (TI dim_i = 0; dim_i < 3; dim_i++) {
		input_msg.position[dim_i] = observation.position[dim_i];
		input_msg.orientation[dim_i] = observation.orientation[dim_i];
		input_msg.linear_velocity[dim_i] = observation.linear_velocity[dim_i];
		input_msg.angular_velocity[dim_i] = observation.angular_velocity[dim_i];
	}

	input_msg.orientation[3] = observation.orientation[3];

	for (TI dim_i = 0; dim_i < EXECUTOR_CONFIG::OUTPUT_DIM; dim_i++) {
		input_msg.previous_action[dim_i] = observation.previous_action[dim_i];
	}

	_raptor_input_pub.publish(input_msg);
	_raptor_status_pub.publish(status);

	actuator_motors_s actuator_motors{};
	actuator_motors.timestamp = hrt_absolute_time();
	actuator_motors.timestamp_sample = _vehicle_angular_velocity.timestamp_sample;

	for (TI action_i = 0; action_i < actuator_motors_s::NUM_CONTROLS; action_i++) {
		if (action_i < EXECUTOR_CONFIG::OUTPUT_DIM) {
			T value = action.action[action_i];
#ifdef __PX4_POSIX
            if(!_research_state.engine.holding) {
                this->previous_action[action_i] = value;
            }
#else
            this->previous_action[action_i] = value;
#endif
			value = (value + 1) / 2;
			constexpr T training_min = 0;
			constexpr T training_max = 1.0;
			T scaled_value = (training_max - training_min) * value + training_min;
			actuator_motors.control[action_i] = scaled_value;

		} else {
			actuator_motors.control[action_i] = NAN;
		}
	}

	if constexpr(Raptor::REMAP_FROM_CRAZYFLIE) {
		actuator_motors_s temp = actuator_motors;
		temp.control[0] = actuator_motors.control[0];
		temp.control[1] = actuator_motors.control[2];
		temp.control[2] = actuator_motors.control[3];
		temp.control[3] = actuator_motors.control[1];
		actuator_motors = temp;
	}

	if (status.active) {
#ifdef __PX4_POSIX
        handover_research::ActuatorGate publication_gate(true);
        if (publication_gate.allowed()) {
#endif
		_actuator_motors_pub.publish(actuator_motors);
#ifdef __PX4_POSIX
        timing.actuator_published=true;
        timing.actuator_publish_sim_us=hrt_absolute_time();
        struct timespec publish_wall{};clock_gettime(CLOCK_MONOTONIC,&publish_wall);
        timing.actuator_publish_wall_ns=static_cast<uint64_t>(publish_wall.tv_sec)*1000000000ULL+publish_wall.tv_nsec;
#endif
#ifdef __PX4_POSIX
    research_actuator_s ownership{};
    ownership.timestamp=hrt_absolute_time();ownership.actuator_timestamp=actuator_motors.timestamp;ownership.owner=1;
    for(unsigned i=0;i<4;i++)ownership.control[i]=actuator_motors.control[i];
    static uORB::Publication<research_actuator_s> ownership_pub{ORB_ID(research_actuator)};
    ownership_pub.publish(ownership);
        } // publication_gate.allowed()
#endif
	}

	perf_end(_loop_perf);
#ifdef __PX4_POSIX
    struct timespec p11_post_begin{};clock_gettime(CLOCK_MONOTONIC,&p11_post_begin);
    timing.p11_cycle_wall_start_ns=p11_cycle_start;
    if (_p11_enabled) {
        _p11.active=next_active;_p11.activation=!previous_active && next_active;
        _p11.native_step=timing.native_step;_p11.gru_committed=timing.gru_committed;
        float p11_after[32]{};research_get(p11_after);
        for (TI i=0;i<16;i++) _p11.gru_after[i]=p11_after[i];
        for (TI i=0;i<4;i++) {_p11.previous_action_after[i]=previous_action[i];_p11.executor_action[i]=action.action[i];}
        for (TI i=0;i<22;i++) _p11.policy_input[i]=rlt::get(device,executor.input,0,i);
        struct timespec p11_pub_begin{},p11_pub_end{};clock_gettime(CLOCK_MONOTONIC,&p11_pub_begin);
        _p11_pub.publish(_p11);
        clock_gettime(CLOCK_MONOTONIC,&p11_pub_end);
        timing.p11_setup_ns=_p11.run_wall_ns-p11_cycle_start;
        timing.p11_pre_ns=_p11_pre_ns;
        timing.p11_post_copy_ns=static_cast<uint64_t>(p11_pub_begin.tv_sec-p11_post_begin.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_pub_begin.tv_nsec-p11_post_begin.tv_nsec);
        timing.p11_publication_ns=static_cast<uint64_t>(p11_pub_end.tv_sec-p11_pub_begin.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_pub_end.tv_nsec-p11_pub_begin.tv_nsec);
    }
    struct timespec p11_cycle_end{};clock_gettime(CLOCK_MONOTONIC,&p11_cycle_end);
    timing.p11_cycle_wall_end_ns=static_cast<uint64_t>(p11_cycle_end.tv_sec)*1000000000ULL+static_cast<uint64_t>(p11_cycle_end.tv_nsec);
#endif
	previous_active = next_active;

	if (executor_status.source == decltype(executor_status.source)::CONTROL) {
		if (executor_status.step_type == decltype(executor_status.step_type)::INTERMEDIATE) {
			this->last_intermediate_status = executor_status;
			this->last_intermediate_status_set = true;

		} else if (executor_status.step_type == decltype(executor_status.step_type)::NATIVE) {
			this->last_native_status = executor_status;
			this->last_native_status_set = true;
		}
	}

#ifdef __PX4_POSIX
    if (_p12_enabled) {
        if (_p11.external_valid && next_active) _p12_seen=true;
        _p12.external_seen=_p12_seen;
        _p12.actual_commit=timing.gru_committed;
        _p12.call_index_after=executor.executor.intermediate_step;
        _p12.history_count_after=executor.steps_since_original_control_step;
        for (TI i=0;i<4;i++) _p12.history_after[i]=executor.action_history[0][i];
        _p12_pub.publish(_p12);
    }
    struct timespec p12_cycle_end{};clock_gettime(CLOCK_MONOTONIC,&p12_cycle_end);
    // P12 full-cycle envelope includes its own publication and parameter reads.
    timing.p11_cycle_wall_end_ns=static_cast<uint64_t>(p12_cycle_end.tv_sec)*1000000000ULL+static_cast<uint64_t>(p12_cycle_end.tv_nsec);
#endif
	if (!this->timestamp_last_policy_frequency_check_set
	    || (current_time - timestamp_last_policy_frequency_check) > POLICY_FREQUENCY_CHECK_INTERVAL) {
		if (this->timestamp_last_policy_frequency_check_set) {
			if (last_intermediate_status_set) {
				if (!this->last_intermediate_status.timing_bias.OK || !this->last_intermediate_status.timing_jitter.OK) {
					PX4_WARN("Raptor: INTERMEDIATE: BIAS %fx JITTER %fx", (double)this->last_intermediate_status.timing_bias.MAGNITUDE,
						 (double)this->last_intermediate_status.timing_jitter.MAGNITUDE);

				} else {
					if (ENABLE_CONTROL_FREQUENCY_INFO && this->policy_frequency_check_counter % POLICY_FREQUENCY_INFO_INTERVAL == 0) {
						PX4_INFO("Raptor: INTERMEDIATE: BIAS %fx JITTER %fx", (double)this->last_intermediate_status.timing_bias.MAGNITUDE,
							 (double)this->last_intermediate_status.timing_jitter.MAGNITUDE);
					}
				}
			}

			if (last_native_status_set) {
				if (!this->last_native_status.timing_bias.OK || !this->last_native_status.timing_jitter.OK) {
					PX4_WARN("Raptor: NATIVE: BIAS %fx JITTER %fx", (double)this->last_native_status.timing_bias.MAGNITUDE,
						 (double)this->last_native_status.timing_jitter.MAGNITUDE);

				} else {
					if (ENABLE_CONTROL_FREQUENCY_INFO && this->policy_frequency_check_counter % POLICY_FREQUENCY_INFO_INTERVAL == 0) {
						PX4_INFO("Raptor: NATIVE: BIAS %fx JITTER %fx", (double)this->last_native_status.timing_bias.MAGNITUDE,
							 (double)this->last_native_status.timing_jitter.MAGNITUDE);
					}
				}
			}
		}

		this->num_healthy_executor_statii_intermediate = 0;
		this->num_non_healthy_executor_statii_intermediate = 0;
		this->num_healthy_executor_statii_native = 0;
		this->num_non_healthy_executor_statii_native = 0;
		this->num_statii = 0;
		this->timestamp_last_policy_frequency_check = current_time;
		this->timestamp_last_policy_frequency_check_set = true;
		this->policy_frequency_check_counter++;
	}

	this->num_statii++;
	this->num_healthy_executor_statii_intermediate += executor_status.OK && executor_status.source == decltype(executor_status.source)::CONTROL
			&& executor_status.step_type == decltype(executor_status.step_type)::INTERMEDIATE;
	this->num_non_healthy_executor_statii_intermediate += (!executor_status.OK)
			&& executor_status.source == decltype(executor_status.source)::CONTROL
			&& executor_status.step_type == decltype(executor_status.step_type)::INTERMEDIATE;
	this->num_healthy_executor_statii_native += executor_status.OK && executor_status.source == decltype(executor_status.source)::CONTROL
			&& executor_status.step_type == decltype(executor_status.step_type)::NATIVE;
	this->num_non_healthy_executor_statii_native += (!executor_status.OK)
			&& executor_status.source == decltype(executor_status.source)::CONTROL
			&& executor_status.step_type == decltype(executor_status.step_type)::NATIVE;
}

#ifdef __PX4_POSIX
// P4-01c: called in the cycle in which RAPTOR captured its target (the original capture has just written the current
// position and yaw with zero velocity). Mode 1 replaces the zero velocity by the current horizontal velocity in the
// activation cycle only; research_target_step() then evaluates the profile every cycle while RAPTOR holds that target.
// P5: mode 2 does the same at activation and at every in-flight setpoint-timeout capture while active.
void Raptor::research_target_capture(bool activation, bool active) {
    static const param_t rsh=param_find("MC_RAPTOR_RSH"),rtgt=param_find("MC_RAPTOR_RTGT"),rtdec=param_find("MC_RAPTOR_RTDEC");
    int32_t enabled=0,mode=0;float decel=0.f;param_get(rsh,&enabled);
    if (!enabled) return;
    param_get(rtgt,&mode);param_get(rtdec,&decel);
    // P12_CAPTURE_OVERLAY: no reset, no hidden/history write, no live parameter change.
    if (_p12_enabled) mode=handover_research::p12_capture_mode(_p12_repair,activation,active,_p12_seen);
    // P12_CONT_REPAIR_WINDOW: preserve the complete legacy overlay prefix.
    if (_p12_enabled) {
        static const param_t window_param=param_find("MC_RAPTOR_P12MS");
        int32_t not_before_ms=-1;param_get(window_param,&not_before_ms);
        if (!handover_research::p12_repair_window_open(_vehicle_angular_velocity.timestamp_sample,not_before_ms)) mode=0;
    }
    if (_research_target.active) {_research_target.active=false;research_target_publish(research_target_s::KIND_END,research_target_s::END_RECAPTURE);}
    _research_target_mode=mode;_research_target_decel=decel;_research_target_activation=activation;
    _research_target_capture_time=hrt_absolute_time();_research_target_capture_sample=_vehicle_angular_velocity.timestamp_sample;
    _research_target_local_sample=_vehicle_local_position.timestamp_sample;
    for (TI i=0;i<3;i++) {_research_target_vehicle_position[i]=position[i];_research_target_vehicle_velocity[i]=linear_velocity[i];}
    _research_target_phase=handover_research::TARGET_PHASE_HOLD;
    if (handover_research::speed_matched_capture(mode,activation,active)) {
        float p[3]={_trajectory_setpoint.position[0],_trajectory_setpoint.position[1],_trajectory_setpoint.position[2]},v[3];
        if (_research_target.start(_research_target_capture_sample,p,linear_velocity,decel)) {
            _research_target_phase=_research_target.evaluate(_research_target_capture_sample,p,v);
            for (TI i=0;i<3;i++) {_trajectory_setpoint.position[i]=p[i];_trajectory_setpoint.velocity[i]=v[i];}
            PX4_INFO("Research takeover target T1: speed %.3f m/s, decel %.2f m/s^2",(double)_research_target.speed0,(double)decel);
        } else {
            PX4_ERR("Research takeover target T1 NOT started (decel %.3f)",(double)decel);
        }
    }
    research_target_publish(research_target_s::KIND_CAPTURE,0);
}
void Raptor::research_target_step(bool active, bool stale) {
    if (!_research_target.active) return;
    if (!active || !stale) {
        _research_target.active=false;
        research_target_publish(research_target_s::KIND_END,active?research_target_s::END_EXTERNAL_SETPOINT:research_target_s::END_INACTIVE);
        return;
    }
    float p[3],v[3];_research_target_phase=_research_target.evaluate(_vehicle_angular_velocity.timestamp_sample,p,v);
    for (TI i=0;i<3;i++) {_trajectory_setpoint.position[i]=p[i];_trajectory_setpoint.velocity[i]=v[i];}
    research_target_publish(research_target_s::KIND_PROFILE,0);
}
void Raptor::research_target_publish(uint8_t kind, uint8_t end_reason) {
    research_target_s m{};
    m.timestamp=hrt_absolute_time();m.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    m.kind=kind;m.mode=_research_target_mode;m.activation=_research_target_activation;
    m.phase=kind==research_target_s::KIND_END?0:_research_target_phase;m.end_reason=end_reason;m.decel=_research_target_decel;
    m.capture_timestamp=_research_target_capture_time;m.capture_sample=_research_target_capture_sample;m.local_position_sample=_research_target_local_sample;
    for (TI i=0;i<3;i++) {
        m.vehicle_position[i]=_research_target_vehicle_position[i];m.vehicle_velocity[i]=_research_target_vehicle_velocity[i];
        m.position[i]=_trajectory_setpoint.position[i];m.velocity[i]=_trajectory_setpoint.velocity[i];
    }
    m.yaw=_trajectory_setpoint.yaw;
    _research_target_pub.publish(m);
}
#endif

int Raptor::task_spawn(int argc, char *argv[])
{
	Raptor *instance = new Raptor();

	if (instance) {
		desc.object.store(instance);
		desc.task_id = task_id_is_work_queue;

		if (instance->init()) {
			return PX4_OK;
		}

	} else {
		PX4_ERR("alloc failed");
	}

	delete instance;
	desc.object.store(nullptr);
	desc.task_id = -1;

	return PX4_ERROR;
}

#ifdef __PX4_POSIX
// P7: called every cycle after the takeover-target step. Arms at an in-flight setpoint-timeout capture while active (not
// at the activation capture), starts the virtual target in the cycle the setpoint is fresh again (MC_RAPTOR_RREC > 0),
// ends it at a new timeout or when RAPTOR becomes inactive.
void Raptor::research_recovery_transition(bool active, bool stale, bool activation) {
    const bool was_stale=_research_recovery_previous_stale;
    _research_recovery_previous_stale=stale;
    if (!active) {
        _research_recovery_armed=false;
        if (_research_recovery.active) {_research_recovery.active=false;research_recovery_publish(research_recovery_s::KIND_END,research_recovery_s::END_INACTIVE);}
        return;
    }
    if (stale) {
        if (activation) _research_recovery_armed=false;
        else if (!was_stale) _research_recovery_armed=true;
        if (_research_recovery.active) {_research_recovery.active=false;research_recovery_publish(research_recovery_s::KIND_END,research_recovery_s::END_STALE);}
        return;
    }
    if (!was_stale || !_research_recovery_armed) return;
    _research_recovery_armed=false;
    static const param_t rsh=param_find("MC_RAPTOR_RSH"),rrec=param_find("MC_RAPTOR_RREC");
    int32_t enabled=0;float rate=0.f;param_get(rsh,&enabled);param_get(rrec,&rate);
    if (!enabled || !(rate>0.f)) return;
    const float p[3]={position[0],position[1],position[2]},v[3]={linear_velocity[0],linear_velocity[1],linear_velocity[2]};
    if (!_research_recovery.start(_vehicle_angular_velocity.timestamp_sample,p,v,rate)) {PX4_ERR("Research recovery NOT started (rate %.3f)",(double)rate);return;}
    for (TI i=0;i<3;i++) {_research_recovery_vehicle_position[i]=p[i];_research_recovery_vehicle_velocity[i]=v[i];}
    _research_recovery_last=handover_research::RecoveryStep{};
    research_recovery_publish(research_recovery_s::KIND_START,0);
    PX4_INFO("Research recovery: virtual target, rate %.2f m/s^2",(double)rate);
}
// Inside observe(): one step of the virtual target against the external setpoint in force; the network then observes it.
bool Raptor::research_recovery_apply(float saved[4]) {
    if (!_research_recovery.active) return false;
    const float sp_p[2]={_trajectory_setpoint.position[0],_trajectory_setpoint.position[1]};
    const float sp_v[2]={_trajectory_setpoint.velocity[0],_trajectory_setpoint.velocity[1]};
    _research_recovery_last=_research_recovery.step(_vehicle_angular_velocity.timestamp_sample,sp_p,sp_v);
    if (!_research_recovery.active) {research_recovery_publish(research_recovery_s::KIND_END,research_recovery_s::END_CONVERGED);return false;}
    research_recovery_publish(research_recovery_s::KIND_STEP,0);
    for (TI i=0;i<2;i++) {
        saved[i]=sp_p[i];saved[2+i]=sp_v[i];
        _trajectory_setpoint.position[i]=float(_research_recovery.p[i]);_trajectory_setpoint.velocity[i]=float(_research_recovery.v[i]);
    }
    return true;
}
void Raptor::research_recovery_restore(const float saved[4]) {
    for (TI i=0;i<2;i++) {_trajectory_setpoint.position[i]=saved[i];_trajectory_setpoint.velocity[i]=saved[2+i];}
}
void Raptor::research_recovery_publish(uint8_t kind, uint8_t end_reason) {
    research_recovery_s m{};
    m.timestamp=hrt_absolute_time();m.timestamp_sample=_vehicle_angular_velocity.timestamp_sample;
    m.kind=kind;m.end_reason=end_reason;m.rate=float(_research_recovery.rate);m.omega=float(handover_research::RecoveryTarget::OMEGA);
    const handover_research::RecoveryStep &s=_research_recovery_last;
    m.dt=float(s.dt);m.limited=s.limited;m.acc[0]=float(s.acc[0]);m.acc[1]=float(s.acc[1]);m.acc_unlimited_norm=float(s.acc_unlimited);
    m.position_difference=float(s.position_difference);m.velocity_difference=float(s.velocity_difference);m.start_sample=_research_recovery.start_us;
    const bool step=kind==research_recovery_s::KIND_STEP;
    for (TI i=0;i<3;i++) {
        m.setpoint_position[i]=_trajectory_setpoint.position[i];m.setpoint_velocity[i]=_trajectory_setpoint.velocity[i];
        m.target_position[i]=i<2 && (step || kind==research_recovery_s::KIND_START)?float(_research_recovery.p[i]):_trajectory_setpoint.position[i];
        m.target_velocity[i]=i<2 && (step || kind==research_recovery_s::KIND_START)?float(_research_recovery.v[i]):_trajectory_setpoint.velocity[i];
        m.vehicle_position[i]=_research_recovery_vehicle_position[i];m.vehicle_velocity[i]=_research_recovery_vehicle_velocity[i];
    }
    _research_recovery_pub.publish(m);
}
#endif

int Raptor::print_status()
{
	perf_print_counter(_loop_perf);
	perf_print_counter(_loop_interval_perf);
	perf_print_counter(_loop_interval_policy_perf);
	PX4_INFO_RAW("Checkpoint: %s\n", checkpoint_name);
	return 0;
}

int Raptor::custom_command(int argc, char *argv[])
{
#ifdef __PX4_POSIX
    if(argc>=1 && strcmp(argv[0],"state")==0)return handover_research::state_command(argc,argv);
#endif
	if (argc >= 2 && strcmp(argv[0], "intref") == 0) {
		if (strcmp(argv[1], "lissajous") == 0) {
			// Usage: mc_raptor intref lissajous <A> <B> <C> <fa> <fb> <fc> <duration> <ramp>
			if (argc != 10) {
				PX4_ERR("Usage: mc_raptor intref lissajous <A> <B> <C> <fa> <fb> <fc> <duration> <ramp>");
				return PX4_ERROR;
			}

			Raptor *instance = get_instance<Raptor>(desc);

			if (instance == nullptr) {
				PX4_ERR("mc_raptor is not running");
				return PX4_ERROR;
			}

			instance->lissajous_params.A = strtof(argv[2], nullptr);
			instance->lissajous_params.B = strtof(argv[3], nullptr);
			instance->lissajous_params.C = strtof(argv[4], nullptr);
			instance->lissajous_params.a = strtof(argv[5], nullptr);
			instance->lissajous_params.b = strtof(argv[6], nullptr);
			instance->lissajous_params.c = strtof(argv[7], nullptr);
			instance->lissajous_params.duration = strtof(argv[8], nullptr);
			instance->lissajous_params.ramp_duration = strtof(argv[9], nullptr);
			instance->internal_reference_params_changed = true;

			PX4_INFO("Lissajous params set: A=%.2f B=%.2f C=%.2f fa=%.2f fb=%.2f fc=%.2f duration=%.2f ramp=%.2f \n",
				 (double)instance->lissajous_params.A,
				 (double)instance->lissajous_params.B,
				 (double)instance->lissajous_params.C,
				 (double)instance->lissajous_params.a,
				 (double)instance->lissajous_params.b,
				 (double)instance->lissajous_params.c,
				 (double)instance->lissajous_params.duration,
				 (double)instance->lissajous_params.ramp_duration);


			return PX4_OK;
		}
	}

	return print_usage("unknown command");
}

int Raptor::print_usage(const char *reason)
{
	if (reason) {
		PX4_WARN("%s\n", reason);
	}

	PRINT_MODULE_DESCRIPTION(
		R"DESCR_STR(
### Description
RAPTOR Policy Flight Mode

)DESCR_STR");

	PRINT_MODULE_USAGE_NAME("mc_raptor", "template");
	PRINT_MODULE_USAGE_COMMAND("start");
	PRINT_MODULE_USAGE_COMMAND_DESCR("intref", "Modify internal reference");
	PRINT_MODULE_USAGE_ARG("lissajous", "Set Lissajous trajectory parameters", false);
	PRINT_MODULE_USAGE_ARG("<A>", "Amplitude X [m]", false);
	PRINT_MODULE_USAGE_ARG("<B>", "Amplitude Y [m]", false);
	PRINT_MODULE_USAGE_ARG("<C>", "Amplitude Z [m]", false);
	PRINT_MODULE_USAGE_ARG("<fa>", "Frequency a", false);
	PRINT_MODULE_USAGE_ARG("<fb>", "Frequency b", false);
	PRINT_MODULE_USAGE_ARG("<fc>", "Frequency c", false);
	PRINT_MODULE_USAGE_ARG("<duration>", "Total duration [s]", false);
	PRINT_MODULE_USAGE_ARG("<ramp>", "Ramp duration [s]", false);
	PRINT_MODULE_USAGE_DEFAULT_COMMANDS();

	return 0;
}

extern "C" __EXPORT int mc_raptor_main(int argc, char *argv[])
{
	return ModuleBase::main(Raptor::desc, argc, argv);
}
