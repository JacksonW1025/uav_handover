#include <rl_tools/operations/cpu.h>
#include <rl_tools/nn/layers/standardize/operations_generic.h>
#include <rl_tools/nn/layers/dense/operations_generic.h>
#include <rl_tools/nn/layers/sample_and_squash/operations_generic.h>
#include <rl_tools/nn/layers/gru/operations_generic.h>
#include <rl_tools/nn_models/mlp/operations_generic.h>
#include <rl_tools/nn_models/sequential/operations_generic.h>
#include <rl_tools/inference/executor/executor.h>

#include "actor.h"
#include "sim_hal.h"

namespace rlt = rl_tools;

namespace other {
    using DEV_SPEC = rlt::devices::DefaultCPUSpecification;
    using DEVICE = rlt::devices::CPU<DEV_SPEC>;
}

struct RL_TOOLS_INFERENCE_APPLICATIONS_L2F_CONFIG {
    using DEVICE = other::DEVICE;
    using TI = typename other::DEVICE::index_t;
    using RNG = other::DEVICE::SPEC::RANDOM::ENGINE<>;
    static constexpr TI TEST_SEQUENCE_LENGTH_ACTUAL = 5;
    static constexpr TI TEST_BATCH_SIZE_ACTUAL = 2;
    using ACTOR_TYPE_ORIGINAL = rlt::checkpoint::actor::TYPE;
    using POLICY_TEST = rlt::checkpoint::actor::TYPE::template CHANGE_BATCH_SIZE<TI, 1>::template CHANGE_SEQUENCE_LENGTH<TI, 1>;
    using POLICY = ACTOR_TYPE_ORIGINAL::template CHANGE_BATCH_SIZE<TI, 1>::template CHANGE_SEQUENCE_LENGTH<TI, 1>;
    using TYPE_POLICY = typename POLICY::SPEC::TYPE_POLICY;
    using T = typename TYPE_POLICY::DEFAULT;
    static auto& policy() {
        return rlt::checkpoint::actor::module;
    }
    static constexpr TI ACTION_HISTORY_LENGTH = 1;
    static constexpr TI CONTROL_INTERVAL_INTERMEDIATE_NS = 1 * 1000 * 1000; // 1000 Hz stabilizer loop
    static constexpr TI CONTROL_INTERVAL_NATIVE_NS = 10 * 1000 * 1000;      // 100 Hz native GRU step
    static constexpr TI TIMING_STATS_NUM_STEPS = 100;
    static constexpr bool FORCE_SYNC_INTERMEDIATE = true;
    static constexpr TI FORCE_SYNC_NATIVE = 10;
    static constexpr bool FORCE_SYNC_NATIVE_RUNTIME = false;
    static constexpr bool DYNAMIC_ALLOCATION = false;
    struct WARNING_LEVELS: rlt::inference::executor::WarningLevelsDefault<TYPE_POLICY> {
        static constexpr T INTERMEDIATE_TIMING_JITTER_HIGH_THRESHOLD = 1.3;
        static constexpr T INTERMEDIATE_TIMING_JITTER_LOW_THRESHOLD = 0.7;
    };
};

// Rename upstream reset/control symbols slightly so we can wrap them with non-intrusive research hooks
#define rl_tools_inference_applications_l2f_reset _upstream_rlt_l2f_reset
#define rl_tools_inference_applications_l2f_control _upstream_rlt_l2f_control
#include <rl_tools/inference/applications/l2f/c_backend.h>
#undef rl_tools_inference_applications_l2f_reset
#undef rl_tools_inference_applications_l2f_control

static bool g_teacher_force_shadow = false;
static bool g_skip_activation_reset = false;
static bool g_neural_owns_motors = false;
static bool g_initialized_once = false;
static float g_last_applied_ratios[4] = {0, 0, 0, 0};
static float g_last_obs22[22] = {0};
static float g_last_act4[4] = {0};

extern "C" void sim_rlt_set_research_mode(bool teacher_force_shadow, bool skip_activation_reset) {
    g_teacher_force_shadow = teacher_force_shadow;
    g_skip_activation_reset = skip_activation_reset;
}

extern "C" void sim_rlt_notify_pre_step(bool neural_owns_motors, const float last_applied_motor_ratios[4]) {
    g_neural_owns_motors = neural_owns_motors;
    for (int i = 0; i < 4; i++) {
        g_last_applied_ratios[i] = last_applied_motor_ratios[i];
    }
}

extern "C" void sim_rlt_force_reset(void) {
    _upstream_rlt_l2f_reset();
    g_initialized_once = true;
}

extern "C" void rl_tools_inference_applications_l2f_reset(void) {
    if (g_initialized_once && g_skip_activation_reset) {
        // Shadow warm-up mode (strips T2): preserve warm GRU state & align action history to classic applied command
        using namespace rl_tools::inference::applications::l2f;
        for (int i = 0; i < 4; i++) {
            executor.action_history[0][i] = 2.0f * g_last_applied_ratios[i] - 1.0f;
        }
        return;
    }
    _upstream_rlt_l2f_reset();
    g_initialized_once = true;
}

extern "C" RLtoolsInferenceExecutorStatus rl_tools_inference_applications_l2f_control(
    RLtoolsInferenceTimestamp nanoseconds,
    RLtoolsInferenceApplicationsL2FObservation* c_observation,
    RLtoolsInferenceApplicationsL2FAction* c_action)
{
    RLtoolsInferenceApplicationsL2FObservation obs_copy = *c_observation;
    if (g_teacher_force_shadow && !g_neural_owns_motors) {
        for (int i = 0; i < 4; i++) {
            obs_copy.previous_action[i] = 2.0f * g_last_applied_ratios[i] - 1.0f;
        }
    }
    auto status = _upstream_rlt_l2f_control(nanoseconds, &obs_copy, c_action);
    using namespace rl_tools::inference::applications::l2f;
    for (int i = 0; i < 22; i++) {
        g_last_obs22[i] = rlt::get(device, executor.input, 0, i);
    }
    for (int i = 0; i < 4; i++) {
        g_last_act4[i] = c_action->action[i];
    }
    return status;
}

extern "C" void sim_rlt_get_gru(float out_gru[16]) {
    using namespace rl_tools::inference::applications::l2f;
    auto& gru_tensor = rlt::get<1>(executor.executor.policy_state.content_state.states).state;
    for (int i = 0; i < 16; i++) {
        out_gru[i] = rlt::get(device, gru_tensor, 0, i);
    }
}

extern "C" void sim_rlt_set_gru(const float in_gru[16]) {
    using namespace rl_tools::inference::applications::l2f;
    auto& gru1 = rlt::get<1>(executor.executor.policy_state.content_state.states).state;
    auto& gru2 = rlt::get<1>(executor.executor.policy_state_temp.content_state.states).state;
    for (int i = 0; i < 16; i++) {
        rlt::set(device, gru1, in_gru[i], 0, i);
        rlt::set(device, gru2, in_gru[i], 0, i);
    }
}

extern "C" void sim_rlt_get_last_io(float out_obs22[22], float out_act4[4]) {
    for (int i = 0; i < 22; i++) out_obs22[i] = g_last_obs22[i];
    for (int i = 0; i < 4; i++) out_act4[i] = g_last_act4[i];
}
