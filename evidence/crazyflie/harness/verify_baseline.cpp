#include "cf_plant.hpp"
#include <cstdio>

static setpoint_t make_pos_vel_acc_sp(uint32_t tick_ms, double x, double y, double z,
                                      double vx, double vy, double vz,
                                      double ax = 0.0, double ay = 0.0, double az = 0.0,
                                      double yaw_deg = 0.0) {
  setpoint_t sp;
  std::memset(&sp, 0, sizeof(sp));
  sp.timestamp = tick_ms;
  sp.mode.x = modeAbs;
  sp.mode.y = modeAbs;
  sp.mode.z = modeAbs;
  sp.mode.yaw = modeAbs;
  sp.position.x = (float)x;
  sp.position.y = (float)y;
  sp.position.z = (float)z;
  sp.velocity.x = (float)vx;
  sp.velocity.y = (float)vy;
  sp.velocity.z = (float)vz;
  sp.acceleration.x = (float)ax;
  sp.acceleration.y = (float)ay;
  sp.acceleration.z = (float)az;
  sp.attitude.yaw = (float)yaw_deg;
  return sp;
}

void run_hover_warmup_vs_cold(bool warm_gru, const char *label) {
  sim_set_time_us(1000000ULL);
  sim_reset_motors();
  controllerOutOfTreeInit();
  sim_rlt_force_reset();

  sim_set_param_int("rlt.gate", 0);
  sim_set_param_int("rlt.motor_warmup", 0);
  sim_set_param_int("rlt.wn", 0);
  sim_set_param_float("rlt.target_z", 0.0f);
  sim_rlt_set_research_mode(warm_gru, warm_gru);

  CrazyfliePlant plant;
  plant.env.wind_vel[0] = -1.2; // 1.2 m/s headwind along -x
  plant.reset_hover(0.0, 0.0, 1.5, 0.0);
  float hov = (float)plant.hover_throttle_rel();

  uint64_t t0_us = 1000000ULL;
  double entry_z = 0.0, min_z_after = 1e9, max_tilt_after = 0.0, max_speed_after = 0.0, min_vz_after = 1e9;
  float m_before[4] = {0}, m_first_nn[4] = {0};
  bool captured_first = false;

  for (uint32_t step = 1; step <= 9000; step++) {
    uint64_t now_us = t0_us + (uint64_t)step * 1000ULL;
    sim_set_time_us(now_us);
    double t_s = step * 0.001;

    // Switch at t = 6.000 s after PID has completely settled in 1.2 m/s wind
    if (step >= 6000 && (step % 10 == 0)) {
      rl_tools_controller_packet_received();
    }

    state_t fw_state;
    sensorData_t fw_sensors;
    plant.fill_firmware_structs((uint32_t)(now_us / 1000ULL), fw_state, fw_sensors);
    setpoint_t sp = make_pos_vel_acc_sp((uint32_t)(now_us / 1000ULL), 0.0, 0.0, 1.5, 0.0, 0.0, 0.0);
    control_t ctrl;
    std::memset(&ctrl, 0, sizeof(ctrl));

    float prev_m[4];
    if (step == 1) { for (int i = 0; i < 4; i++) prev_m[i] = hov; }
    else sim_get_motor_ratios(prev_m);

    bool sm_prev = sim_get_log_int("rltrp.sm", nullptr) != 0;
    sim_rlt_notify_pre_step(sm_prev, prev_m);

    if (step == 5999) {
      for (int i = 0; i < 4; i++) m_before[i] = prev_m[i];
    }

    controllerOutOfTree(&ctrl, &sp, &fw_sensors, &fw_state, step);

    float m[4];
    sim_get_motor_ratios(m);
    bool sm_now = sim_get_log_int("rltrp.sm", nullptr) != 0;

    if (sm_now && !captured_first) {
      captured_first = true;
      entry_z = plant.s.pos[2];
      for (int i = 0; i < 4; i++) m_first_nn[i] = m[i];
      printf("[%s] Entry @ t=%.3fs: pos=(%.3f,%.3f,%.3f) vel=(%.3f,%.3f,%.3f) tilt=%.2f deg\n",
             label, t_s, plant.s.pos[0], plant.s.pos[1], plant.s.pos[2],
             plant.s.vel[0], plant.s.vel[1], plant.s.vel[2], plant.tilt_deg());
      printf("  m_before=[%.3f,%.3f,%.3f,%.3f] -> m_first_nn=[%.3f,%.3f,%.3f,%.3f]\n",
             m_before[0], m_before[1], m_before[2], m_before[3],
             m_first_nn[0], m_first_nn[1], m_first_nn[2], m_first_nn[3]);
    }

    plant.step_rk4(0.001, m);

    if (step >= 6000) {
      min_z_after = std::min(min_z_after, plant.s.pos[2]);
      min_vz_after = std::min(min_vz_after, plant.s.vel[2]);
      max_tilt_after = std::max(max_tilt_after, plant.tilt_deg());
      max_speed_after = std::max(max_speed_after, plant.speed_3d());
    }
  }
  printf("  => Post-handover: max_alt_loss=%.2f cm, min_vz=%.3f m/s, max_speed=%.3f m/s, max_tilt=%.2f deg\n\n",
         (entry_z - min_z_after) * 100.0, min_vz_after, max_speed_after, max_tilt_after);
}

int main() {
  sim_set_time_us(1000000ULL);
  controllerOutOfTreeInit();
  if (!controllerOutOfTreeTest()) return 1;
  run_hover_warmup_vs_cold(true,  "WARM_SHADOW");
  run_hover_warmup_vs_cold(false, "COLD_RESET ");
  return 0;
}
