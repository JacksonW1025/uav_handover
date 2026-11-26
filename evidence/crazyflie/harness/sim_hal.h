#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void sim_set_time_us(uint64_t t_us);
uint64_t sim_get_time_us(void);

bool sim_set_param_float(const char *group_dot_name, float val);
bool sim_set_param_int(const char *group_dot_name, int val);
float sim_get_param_float(const char *group_dot_name, bool *ok);
int sim_get_param_int(const char *group_dot_name, bool *ok);

float sim_get_log_float(const char *group_dot_name, bool *ok);
int sim_get_log_int(const char *group_dot_name, bool *ok);

void sim_reset_motors(void);
void sim_get_motor_ratios(float out_ratios[4]);
void sim_get_published_motor_ratios(float out_ratios[4]);

// Downstream actuation delivery delay simulation (for T4 turn-exit stale command continuation)
void sim_set_delivery_hold_Active(bool hold_current_motors);

// Research hooks in sim_executor.cpp
void sim_rlt_set_research_mode(bool teacher_force_shadow, bool skip_activation_reset);
void sim_rlt_notify_pre_step(bool neural_owns_motors, const float last_applied_motor_ratios[4]);
void sim_rlt_get_gru(float out_gru[16]);
void sim_rlt_set_gru(const float in_gru[16]);
void sim_rlt_force_reset(void);
void sim_rlt_get_last_io(float out_obs22[22], float out_act4[4]);

// Upstream rl_tools_controller.c entry points
void controllerOutOfTreeInit(void);
bool controllerOutOfTreeTest(void);
void rl_tools_controller_packet_received(void);

#ifdef __cplusplus
}
#endif
