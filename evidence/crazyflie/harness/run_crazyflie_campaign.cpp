#include "cf_plant.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>
#include <string>
#include <algorithm>
#include <sys/stat.h>

struct SampleRow {
  double t_s;
  int neural_active;
  double pos[3];
  double target_pos[3];
  double vel[3];
  double target_vel[3];
  double speed_xy;
  double target_speed_xy;
  double tilt_deg;
  double roll_deg;
  double pitch_deg;
  double motor_applied[4];
  double motor_published[4];
};

struct RunMetrics {
  std::string case_id;
  std::string arm_name;
  double t_sw = 0.0;
  double entry_speed_xy = 0.0;
  double entry_tilt_deg = 0.0;
  double entry_z = 0.0;
  double first_motor_jump = 0.0;
  double peak_tilt_deg = 0.0;
  double t_peak_tilt = 0.0;
  double max_speed_xy = 0.0;
  double min_speed_xy = 1e9;
  double min_vz = 0.0;
  double max_alt_loss_cm = 0.0;      // max(0, entry_z - z(t)) * 100 post-switch
  double max_world_drop_cm = 0.0;    // max(0, z_ref - z(t)) * 100 post-switch
  double max_pos_err_xy = 0.0;
  bool crashed = false;
};

static void ensure_dir(const char *path) {
  mkdir(path, 0755);
}

static void save_trace_csv(const std::string &filepath, const std::vector<SampleRow> &rows) {
  FILE *f = std::fopen(filepath.c_str(), "w");
  if (!f) return;
  std::fprintf(f, "t_s,neural_active,x,y,z,tx,ty,tz,vx,vy,vz,tvx,tvy,tvz,speed_xy,target_speed_xy,tilt_deg,roll_deg,pitch_deg,m1,m2,m3,m4,pub_m1,pub_m2,pub_m3,pub_m4\n");
  for (const auto &r : rows) {
    std::fprintf(f, "%.4f,%d,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.3f,%.3f,%.3f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n",
                 r.t_s, r.neural_active,
                 r.pos[0], r.pos[1], r.pos[2],
                 r.target_pos[0], r.target_pos[1], r.target_pos[2],
                 r.vel[0], r.vel[1], r.vel[2],
                 r.target_vel[0], r.target_vel[1], r.target_vel[2],
                 r.speed_xy, r.target_speed_xy,
                 r.tilt_deg, r.roll_deg, r.pitch_deg,
                 r.motor_applied[0], r.motor_applied[1], r.motor_applied[2], r.motor_applied[3],
                 r.motor_published[0], r.motor_published[1], r.motor_published[2], r.motor_published[3]);
  }
  std::fclose(f);
}

struct TrajRef {
  double pos[3] = {0, 0, 2.0};
  double vel[3] = {0, 0, 0};
  double acc[3] = {0, 0, 0};
  double yaw_deg = 0.0;
};

enum class TrajKind {
  T1_JTURN_BRAKE,
  T2_STRAIGHT_CRUISE_STOP,
  T2_RIGHT_TURN_BRAKE,
  T3_STRAIGHT_CRUISE,
  T3_LEVEL_UTURN,
  T4_BANKED_CRUISE,
  T4_TURN_EXIT
};

static TrajRef eval_trajectory(TrajKind kind, double t, double V, double R, double z0 = 2.0) {
  TrajRef tr{};
  tr.pos[2] = z0;

  switch (kind) {
    case TrajKind::T1_JTURN_BRAKE: {
      // Hover 0..2.0s -> accel along +x (2.0..3.4s) -> tight left 180-deg turn R with sharp braking to hover
      const double t0 = 2.0, dur_acc = 1.4, t_turn = t0 + dur_acc;
      if (t <= t0) return tr;
      if (t <= t_turn) {
        double tau = t - t0;
        tr.vel[0] = 0.5 * V * (1.0 - std::cos(M_PI * tau / dur_acc));
        tr.acc[0] = 0.5 * V * (M_PI / dur_acc) * std::sin(M_PI * tau / dur_acc);
        tr.pos[0] = 0.5 * V * (tau - (dur_acc / M_PI) * std::sin(M_PI * tau / dur_acc));
        return tr;
      }
      double x0 = 0.5 * V * dur_acc;
      double Lc = M_PI * R * 0.55;
      double dc = Lc / V, db = 0.95;
      double tau = t - t_turn;
      double s = 0, v = 0, at = 0;
      if (tau <= dc) { v = V; s = V * tau; }
      else if (tau <= dc + db) {
        double tb = tau - dc;
        v = 0.5 * V * (1.0 + std::cos(M_PI * tb / db));
        at = -0.5 * V * (M_PI / db) * std::sin(M_PI * tb / db);
        s = Lc + 0.5 * V * (tb + (db / M_PI) * std::sin(M_PI * tb / db));
      } else { v = 0; s = Lc + 0.5 * V * db; }
      double Lsemi = M_PI * R;
      if (s <= Lsemi) {
        double phi = s / R;
        tr.pos[0] = x0 + R * std::sin(phi);
        tr.pos[1] = R * (1.0 - std::cos(phi));
        tr.vel[0] = v * std::cos(phi);
        tr.vel[1] = v * std::sin(phi);
        tr.acc[0] = at * std::cos(phi) - (v * v / R) * std::sin(phi);
        tr.acc[1] = at * std::sin(phi) + (v * v / R) * std::cos(phi);
      } else {
        tr.pos[0] = x0 - (s - Lsemi);
        tr.pos[1] = 2.0 * R;
        tr.vel[0] = -v;
        tr.acc[0] = -at;
      }
      return tr;
    }

    case TrajKind::T2_STRAIGHT_CRUISE_STOP: {
      // Hover 0..2.2s -> smooth accel to V (2.2..3.2s) -> steady cruise (3.2..5.2s) -> decelerate to hover (5.2..6.2s)
      if (t <= 2.2) return tr;
      double tau = t - 2.2;
      if (tau < 1.0) {
        tr.vel[0] = 0.5 * V * (1.0 - std::cos(M_PI * tau / 1.0));
        tr.acc[0] = 0.5 * V * M_PI * std::sin(M_PI * tau / 1.0);
        tr.pos[0] = 0.5 * V * (tau - (1.0 / M_PI) * std::sin(M_PI * tau / 1.0));
      } else if (tau < 3.0) {
        tr.vel[0] = V;
        tr.pos[0] = 0.5 * V + V * (tau - 1.0);
      } else if (tau < 4.0) {
        double tb = tau - 3.0;
        tr.vel[0] = 0.5 * V * (1.0 + std::cos(M_PI * tb / 1.0));
        tr.acc[0] = -0.5 * V * M_PI * std::sin(M_PI * tb / 1.0);
        tr.pos[0] = 2.5 * V + 0.5 * V * (tb + (1.0 / M_PI) * std::sin(M_PI * tb / 1.0));
      } else {
        tr.pos[0] = 3.0 * V;
      }
      return tr;
    }

    case TrajKind::T2_RIGHT_TURN_BRAKE: {
      // Hover 0..2.2s -> accel along +x (2.2..3.4s) -> tight right turn (ty <= 0) + brake to hover
      if (t <= 2.2) return tr;
      if (t <= 3.4) {
        double tau = t - 2.2, dur = 1.2;
        tr.vel[0] = 0.5 * V * (1.0 - std::cos(M_PI * tau / dur));
        tr.acc[0] = 0.5 * V * (M_PI / dur) * std::sin(M_PI * tau / dur);
        tr.pos[0] = 0.5 * V * (tau - (dur / M_PI) * std::sin(M_PI * tau / dur));
        return tr;
      }
      double x0 = 0.5 * V * 1.2, tau = t - 3.4;
      double Lc = M_PI * R * 0.60, dc = Lc / V, db = 0.90;
      double s = 0, v = 0, at = 0;
      if (tau <= dc) { v = V; s = V * tau; }
      else if (tau <= dc + db) {
        double tb = tau - dc;
        v = 0.5 * V * (1.0 + std::cos(M_PI * tb / db));
        at = -0.5 * V * (M_PI / db) * std::sin(M_PI * tb / db);
        s = Lc + 0.5 * V * (tb + (db / M_PI) * std::sin(M_PI * tb / db));
      } else { v = 0; s = Lc + 0.5 * V * db; }
      double Lsemi = M_PI * R;
      if (s <= Lsemi) {
        double phi = s / R;
        tr.pos[0] = x0 + R * std::sin(phi);
        tr.pos[1] = -R * (1.0 - std::cos(phi));
        tr.vel[0] = v * std::cos(phi);
        tr.vel[1] = -v * std::sin(phi);
        tr.acc[0] = at * std::cos(phi) - (v * v / R) * std::sin(phi);
        tr.acc[1] = -at * std::sin(phi) - (v * v / R) * std::cos(phi);
      } else {
        tr.pos[0] = x0 - (s - Lsemi);
        tr.pos[1] = -2.0 * R;
        tr.vel[0] = -v;
        tr.acc[0] = -at;
      }
      return tr;
    }

    case TrajKind::T3_STRAIGHT_CRUISE: {
      // Hover 0..2.0s -> smooth accel to V (2.0..3.2s) -> steady constant-velocity cruise along +x
      if (t <= 2.0) return tr;
      double tau = t - 2.0;
      if (tau < 1.2) {
        tr.vel[0] = 0.5 * V * (1.0 - std::cos(M_PI * tau / 1.2));
        tr.acc[0] = 0.5 * V * (M_PI / 1.2) * std::sin(M_PI * tau / 1.2);
        tr.pos[0] = 0.5 * V * (tau - (1.2 / M_PI) * std::sin(M_PI * tau / 1.2));
      } else {
        tr.vel[0] = V;
        tr.pos[0] = 0.6 * V + V * (tau - 1.2);
      }
      return tr;
    }

    case TrajKind::T3_LEVEL_UTURN: {
      // Hover 0..2.5s -> accel to V (2.5..3.8s) -> constant-altitude 180-deg tight U-turn of radius R -> straight return
      if (t <= 2.5) return tr;
      if (t <= 3.8) {
        double tau = t - 2.5, dur = 1.3;
        tr.vel[0] = 0.5 * V * (1.0 - std::cos(M_PI * tau / dur));
        tr.acc[0] = 0.5 * V * (M_PI / dur) * std::sin(M_PI * tau / dur);
        tr.pos[0] = 0.5 * V * (tau - (dur / M_PI) * std::sin(M_PI * tau / dur));
        return tr;
      }
      double x0 = 0.5 * V * 1.3;
      double tau = t - 3.8;
      double s = V * tau;
      double L = M_PI * R;
      if (s <= L) {
        double phi = s / R;
        tr.pos[0] = x0 + R * std::sin(phi);
        tr.pos[1] = R * (1.0 - std::cos(phi));
        tr.vel[0] = V * std::cos(phi);
        tr.vel[1] = V * std::sin(phi);
        tr.acc[0] = -(V * V / R) * std::sin(phi);
        tr.acc[1] =  (V * V / R) * std::cos(phi);
      } else {
        double ds = s - L;
        double d_rem = ds / V;
        if (d_rem < 1.2) {
          double v = 0.5 * V * (1.0 + std::cos(M_PI * d_rem / 1.2));
          double at = -0.5 * V * (M_PI / 1.2) * std::sin(M_PI * d_rem / 1.2);
          double s_br = 0.5 * V * (d_rem + (1.2 / M_PI) * std::sin(M_PI * d_rem / 1.2));
          tr.pos[0] = x0 - s_br; tr.pos[1] = 2.0 * R;
          tr.vel[0] = -v; tr.acc[0] = -at;
        } else {
          tr.pos[0] = x0 - 0.6 * V; tr.pos[1] = 2.0 * R;
        }
      }
      return tr;
    }

    case TrajKind::T4_BANKED_CRUISE: {
      // Smooth banked curve at moderate V, R so 0ms warmup is completely gentle (~20 deg tilt), testing upstream 500ms warmup bug!
      if (t <= 2.2) return tr;
      if (t <= 3.4) {
        double tau = t - 2.2, dur = 1.2;
        tr.vel[0] = 0.5 * V * (1.0 - std::cos(M_PI * tau / dur));
        tr.acc[0] = 0.5 * V * (M_PI / dur) * std::sin(M_PI * tau / dur);
        tr.pos[0] = 0.5 * V * (tau - (dur / M_PI) * std::sin(M_PI * tau / dur));
        return tr;
      }
      double x0 = 0.5 * V * 1.2, tau = t - 3.4;
      double s = V * tau, L = M_PI * R;
      if (s <= L) {
        double phi = s / R;
        tr.pos[0] = x0 + R * std::sin(phi);
        tr.pos[1] = R * (1.0 - std::cos(phi));
        tr.vel[0] = V * std::cos(phi);
        tr.vel[1] = V * std::sin(phi);
        tr.acc[0] = -(V * V / R) * std::sin(phi);
        tr.acc[1] =  (V * V / R) * std::cos(phi);
      } else {
        tr.pos[0] = x0 - (s - L);
        tr.pos[1] = 2.0 * R;
        tr.vel[0] = -V;
      }
      return tr;
    }

    case TrajKind::T4_TURN_EXIT: {
      // Exact match to PX4 t4-turn-exit: drone actively rolls into turn (t=3.495..3.560s, reaching ~15 deg bank + high roll rate),
      // then exits onto straight +x line (vy_ref = 0) at t_sw = 3.560s so NN immediately commands counter-roll to level out!
      const double t_roll = 3.495, t_exit = 3.560, ay_turn = 11.5;
      if (t <= 2.5) return tr;
      double tau = t - 2.5;
      double vx_c = std::min(1.0, tau / 0.8) * V;
      double x_c = (tau < 0.8) ? (0.5 * V * tau * tau / 0.8) : (0.4 * V + V * (tau - 0.8));
      tr.pos[0] = x_c;
      tr.vel[0] = vx_c;
      if (t >= t_roll && t < t_exit) {
        double dt = t - t_roll;
        tr.acc[1] = ay_turn;
        tr.vel[1] = ay_turn * dt;
        tr.pos[1] = 0.5 * ay_turn * dt * dt;
      } else if (t >= t_exit) {
        double dt_sw = t_exit - t_roll;
        tr.pos[1] = 0.5 * ay_turn * dt_sw * dt_sw;
        tr.vel[1] = 0.0;
        tr.acc[1] = 0.0;
      }
      return tr;
    }
  }
  return tr;
}

struct SimConfig {
  std::string case_id;
  std::string arm_name;
  TrajKind traj_kind = TrajKind::T1_JTURN_BRAKE;
  double V = 1.65;
  double R = 0.55;
  double z0 = 2.0;
  double t_sw = 3.85;
  double t_end = 6.80;

  // Classic controller selection: false = PID (for T1 PID-to-RL), true = Mellinger full-state (zero pre-switch lag!)
  bool use_mellinger = true;
  bool do_handover = true;

  // Environmental & physical parameters (T1 / T2)
  bool brushless_cf21bl = false;
  double mass_scale = 1.0;
  double wx = 0.0, wy = 0.0;
  double com_x_mm = 0.0; // produces pitch torque
  double com_y_mm = 0.0; // produces roll torque

  // T2 history state mode:
  // 0 = Warm-Shadow (teacher-forced actual classic motor cmds, skip activation reset)
  // 1 = Upstream Cold-Reset (rl_tools_controller.c:439 l2f_reset() on packet activation)
  // 2 = Upstream rlt.orig=-0.8 Poison (rl_tools_controller.c:668-673)
  // 3 = True Zero-GRU + HOVERING_THROTTLE=0.66 at t_sw
  int t2_mode = 0;

  // T3 setpoint continuity mode:
  // ref_gap_ms > 0: hold captured position at t_sw with zero velocity for ref_gap_ms (rl_tools_controller.c:429,518)
  // drop_vel_ff = true: historical deca3ab1 bug (target_vel hardcoded to 0 in modeAbs)
  int ref_gap_ms = 0;
  bool drop_vel_ff = false;

  // T4 authority delivery mode:
  // upstream_warmup_ms > 0: upstream use_pre_set_warmup=1 forcing 25% throttle for upstream_warmup_ms (rl_tools_controller.c:240,697)
  // stale_hold_ms > 0: downstream actuator holds last classic motor ratios for stale_hold_ms (PX4 t4-turn-exit counterpart)
  int upstream_warmup_ms = 0;
  int stale_hold_ms = 0;

  std::string csv_path;
};

static RunMetrics run_simulation(const SimConfig &cfg) {
  sim_set_time_us(1000000ULL);
  sim_reset_motors();
  sim_set_delivery_hold_Active(false);
  controllerMellingerFirmwareInit();
  controllerPidInit();
  controllerOutOfTreeInit();
  sim_rlt_force_reset();

  sim_set_param_int("rlt.wn", 0);
  sim_set_param_float("rlt.target_z", 0.0f);
  sim_set_param_int("rlt.motor_warmup", cfg.upstream_warmup_ms > 0 ? 1 : 0);

  // Classic PID & Mellinger parameters matched to 30.6g Crazyflie 2.1 physical model
  sim_set_param_float("posCtlPid.rLimit", 30.0f);
  sim_set_param_float("posCtlPid.pLimit", 30.0f);
  sim_set_param_int("posCtlPid.thrustBase", 52850);

  sim_set_param_float("ctrlMel.mass", (float)(0.0306 * cfg.mass_scale));
  sim_set_param_float("ctrlMel.massThrust", 176000.0f);
  sim_set_param_float("ctrlMel.kp_xy", 0.50f);
  sim_set_param_float("ctrlMel.kd_xy", 0.24f);
  sim_set_param_float("ctrlMel.ki_xy", 0.10f);
  sim_set_param_float("ctrlMel.i_range_xy", 2.0f);
  sim_set_param_float("ctrlMel.kp_z", 1.55f);
  sim_set_param_float("ctrlMel.kd_z", 0.55f);
  sim_set_param_float("ctrlMel.ki_z", 0.45f);
  sim_set_param_float("ctrlMel.i_range_z", 2.5f);
  sim_set_param_float("ctrlMel.ki_m_xy", 6500.0f);
  sim_set_param_float("ctrlMel.i_range_m_xy", 3.0f);

  if (!cfg.use_mellinger || cfg.upstream_warmup_ms > 0 || cfg.t2_mode == 1) {
    sim_set_param_int("rlt.gate", 0);
    sim_set_param_int("rlt.orig", 0);
    if (cfg.t2_mode == 0) {
      sim_rlt_set_research_mode(true, true);
    } else {
      sim_rlt_set_research_mode(false, false);
    }
  } else if (cfg.t2_mode == 2) {
    sim_set_param_int("rlt.gate", 1);
    sim_set_param_int("rlt.orig", 1); // L668-673 poisons action_output = -0.8!
    sim_rlt_set_research_mode(false, true);
  } else {
    sim_set_param_int("rlt.gate", 1);
    sim_set_param_int("rlt.orig", 1);
    sim_rlt_set_research_mode(true, true);
  }

  CrazyfliePlant plant;
  plant.env.brushless_cf21bl = cfg.brushless_cf21bl;
  plant.env.mass_scale = cfg.mass_scale;
  plant.reset_hover(0.0, 0.0, cfg.z0, 0.0);
  float hov = (float)plant.hover_throttle_rel();

  RunMetrics met{};
  met.case_id = cfg.case_id;
  met.arm_name = cfg.arm_name;
  met.t_sw = cfg.t_sw;

  uint64_t t0_us = 1000000ULL;
  uint32_t sw_step = (uint32_t)std::round(cfg.t_sw * 1000.0);
  uint32_t end_step = (uint32_t)std::round(cfg.t_end * 1000.0);
  double cap_pos[3] = {0, 0, cfg.z0};
  control_t mctrl{};
  std::vector<SampleRow> trace;
  if (!cfg.csv_path.empty()) trace.reserve(end_step / 2 + 8);

  for (uint32_t step = 1; step <= end_step; step++) {
    uint64_t now_us = t0_us + (uint64_t)step * 1000ULL;
    sim_set_time_us(now_us);
    double t_s = step * 0.001;

    // Smooth disturbance ramp over t = 0..1.0s
    double ramp = std::min(1.0, t_s / 1.0);
    ramp = ramp * ramp * (3.0 - 2.0 * ramp);
    plant.env.wind_vel[0] = ramp * cfg.wx;
    plant.env.wind_vel[1] = ramp * cfg.wy;
    double mg = CrazyfliePlant::kDyn.mass * plant.env.mass_scale * 9.81;
    plant.env.ext_torque[0] = ramp * mg * (cfg.com_y_mm * 1e-3);
    plant.env.ext_torque[1] = ramp * mg * (cfg.com_x_mm * 1e-3);

    // Packet & mode triggers
    if (!cfg.use_mellinger || cfg.upstream_warmup_ms > 0 || cfg.t2_mode == 1) {
      if (cfg.do_handover && step >= sw_step && ((step - sw_step) % 10 == 0)) {
        rl_tools_controller_packet_received();
      }
      // Support custom partial warmup duration (default upstream WARMUP_TIME is 500ms)
      if (cfg.upstream_warmup_ms > 0 && cfg.upstream_warmup_ms < 500 && step == sw_step + (uint32_t)cfg.upstream_warmup_ms) {
        sim_set_param_int("rlt.motor_warmup", 0);
        rl_tools_controller_packet_received();
      }
    } else {
      if (step % 10 == 1) rl_tools_controller_packet_received();
      if (cfg.do_handover && step == sw_step) {
        sim_set_param_int("rlt.orig", 0);
        if (cfg.t2_mode == 3) {
          sim_rlt_force_reset();
        }
      }
    }

    TrajRef tr_true = eval_trajectory(cfg.traj_kind, t_s, cfg.V, cfg.R, cfg.z0);
    if (step == sw_step) {
      cap_pos[0] = plant.s.pos[0];
      cap_pos[1] = plant.s.pos[1];
      cap_pos[2] = plant.s.pos[2];
    }

    state_t fw_state;
    sensorData_t fw_sensors;
    plant.fill_firmware_structs((uint32_t)(now_us / 1000ULL), fw_state, fw_sensors);

    // Build setpoint seen by controller
    setpoint_t sp{};
    sp.timestamp = (uint32_t)(now_us / 1000ULL);
    sp.mode.x = modeAbs; sp.mode.y = modeAbs; sp.mode.z = modeAbs; sp.mode.yaw = modeAbs;
    if (cfg.do_handover && cfg.ref_gap_ms > 0 && step >= sw_step && step < sw_step + (uint32_t)cfg.ref_gap_ms) {
      // Upstream zero-velocity captured origin hold during setpoint continuity gap
      sp.position.x = (float)cap_pos[0];
      sp.position.y = (float)cap_pos[1];
      sp.position.z = (float)cap_pos[2];
      sp.velocity.x = 0.0f; sp.velocity.y = 0.0f; sp.velocity.z = 0.0f;
    } else {
      sp.position.x = (float)tr_true.pos[0];
      sp.position.y = (float)tr_true.pos[1];
      sp.position.z = (float)tr_true.pos[2];
      if (!(cfg.do_handover && step >= sw_step && cfg.drop_vel_ff)) {
        sp.velocity.x = (float)tr_true.vel[0];
        sp.velocity.y = (float)tr_true.vel[1];
        sp.velocity.z = (float)tr_true.vel[2];
      }
      sp.acceleration.x = (float)tr_true.acc[0];
      sp.acceleration.y = (float)tr_true.acc[1];
      sp.acceleration.z = (float)tr_true.acc[2];
    }

    float prev_m[4];
    if (step == 1) { for (int i = 0; i < 4; i++) prev_m[i] = hov; }
    else sim_get_motor_ratios(prev_m);

    bool neural_owns = cfg.do_handover && (step > sw_step) && (cfg.upstream_warmup_ms == 0 || step > sw_step + (uint32_t)cfg.upstream_warmup_ms);
    sim_rlt_notify_pre_step(neural_owns, prev_m);

    // T4 downstream actuator latch (holds last classic motor sample across [sw_step, sw_step + stale_hold_ms))
    bool hold_latch = cfg.do_handover && (cfg.stale_hold_ms > 0) && (step >= sw_step) && (step < sw_step + (uint32_t)cfg.stale_hold_ms);
    sim_set_delivery_hold_Active(hold_latch);

    control_t ctrl{};
    setpoint_t sp_rlt = sp;
    controllerOutOfTree(&ctrl, &sp_rlt, &fw_sensors, &fw_state, step);

    // Guarantee bit-identical classic Mellinger execution prior to sw_step (for !use_mellinger, rl_tools_controller.c:711 already executed controllerPid once!)
    if (cfg.use_mellinger && (!cfg.do_handover || step < sw_step)) {
      sim_set_delivery_hold_Active(false);
      controllerMellingerFirmware(&mctrl, &sp, &fw_sensors, &fw_state, step);
      motors_thrust_uncapped_t unc{};
      motors_thrust_pwm_t pwm{};
      powerDistribution(&mctrl, &unc);
      powerDistributionCap(&unc, &pwm);
      for (int i = 0; i < 4; i++) motorsSetRatio(i, pwm.list[i]);
    }

    float m_app[4], m_pub[4];
    sim_get_motor_ratios(m_app);
    sim_get_published_motor_ratios(m_pub);

    if (step == sw_step) {
      met.entry_speed_xy = plant.speed_horiz();
      met.entry_tilt_deg = plant.tilt_deg();
      met.entry_z = plant.s.pos[2];
      for (int i = 0; i < 4; i++) {
        met.first_motor_jump = std::max(met.first_motor_jump, (double)std::fabs(m_pub[i] - prev_m[i]));
      }
    }

    if (!cfg.csv_path.empty() && (step % 2 == 0 || step == sw_step)) {
      SampleRow row{};
      row.t_s = t_s;
      row.neural_active = (cfg.do_handover && step >= sw_step) ? 1 : 0;
      for (int i = 0; i < 3; i++) {
        row.pos[i] = plant.s.pos[i];
        row.target_pos[i] = sp.position.x * (i==0) + sp.position.y * (i==1) + sp.position.z * (i==2);
        row.vel[i] = plant.s.vel[i];
        row.target_vel[i] = sp.velocity.x * (i==0) + sp.velocity.y * (i==1) + sp.velocity.z * (i==2);
      }
      row.speed_xy = plant.speed_horiz();
      row.target_speed_xy = std::sqrt(tr_true.vel[0]*tr_true.vel[0] + tr_true.vel[1]*tr_true.vel[1]);
      row.tilt_deg = plant.tilt_deg();
      row.roll_deg = fw_state.attitude.roll;
      row.pitch_deg = -fw_state.attitude.pitch; // physical FLU pitch
      for (int i = 0; i < 4; i++) {
        row.motor_applied[i] = m_app[i];
        row.motor_published[i] = m_pub[i];
      }
      trace.push_back(row);
    }

    plant.step_rk4(0.001, m_app);

    if (step >= sw_step && step <= sw_step + 2400) {
      double tilt = plant.tilt_deg();
      if (tilt > met.peak_tilt_deg) {
        met.peak_tilt_deg = tilt;
        met.t_peak_tilt = t_s;
      }
      double vxy = plant.speed_horiz();
      met.max_speed_xy = std::max(met.max_speed_xy, vxy);
      met.min_speed_xy = std::min(met.min_speed_xy, vxy);
      met.min_vz = std::min(met.min_vz, plant.s.vel[2]);
      met.max_alt_loss_cm = std::max(met.max_alt_loss_cm, (met.entry_z - plant.s.pos[2]) * 100.0);
      met.max_world_drop_cm = std::max(met.max_world_drop_cm, (tr_true.pos[2] - plant.s.pos[2]) * 100.0);
      double dx = plant.s.pos[0] - tr_true.pos[0], dy = plant.s.pos[1] - tr_true.pos[1];
      met.max_pos_err_xy = std::max(met.max_pos_err_xy, std::sqrt(dx*dx + dy*dy));
      if (plant.s.pos[2] <= 0.05 || tilt > 85.0) {
        met.crashed = true;
        break;
      }
    }
  }

  sim_set_delivery_hold_Active(false);
  if (!cfg.csv_path.empty()) {
    save_trace_csv(cfg.csv_path, trace);
  }
  return met;
}

static void print_row(const RunMetrics &m) {
  std::printf("  %-28s | entry(%.2fm/s, %4.1f°) | du=%.3f | tilt=%5.1f° (@%.2fs) | v=[%.2f..%.2f] vz=%+.2f | dZ=%5.1fcm | err=%.2fm%s\n",
              m.arm_name.c_str(), m.entry_speed_xy, m.entry_tilt_deg, m.first_motor_jump,
              m.peak_tilt_deg, m.t_peak_tilt, m.min_speed_xy, m.max_speed_xy, m.min_vz,
              m.max_alt_loss_cm, m.max_pos_err_xy, m.crashed ? " [CRASH]" : "");
}

int main(int argc, char **argv) {
  const std::string out_dir = (argc > 1 && argv[1][0] != '\0') ? std::string(argv[1]) : ".";
  const std::string tr_dir = out_dir + "/traces";
  ensure_dir(out_dir.c_str());
  ensure_dir(tr_dir.c_str());

  std::vector<RunMetrics> all;
  auto record = [&](SimConfig c) {
    RunMetrics m = run_simulation(c);
    all.push_back(m);
    print_row(m);
    return m;
  };

  // =========================================================================
  // T1: Physical & Environmental Margin Depletion (t1-turn + Tailwind sweep)
  // =========================================================================
  std::printf("\n=== [T1] Tight J-Turn + Braking (Ideal Warm-Shadow + ContRef + 0ms Delivery) ===\n");
  for (double wx : {0.0, 0.8, 1.4, 1.8}) {
    for (int arm = 0; arm < 2; arm++) {
      SimConfig c{};
      char id[64], nm[64];
      std::snprintf(id, sizeof(id), "t1_turn_wx%.1f", wx);
      std::snprintf(nm, sizeof(nm), "%s (wx=%.1f)", arm == 0 ? "Classic-Keep" : "NN-Ideal-Takeover", wx);
      c.case_id = id; c.arm_name = nm;
      c.traj_kind = TrajKind::T1_JTURN_BRAKE;
      c.use_mellinger = false; // PID-to-RLtools matching upstream mid-air stack (rlt.orig=1)
      c.V = 1.70; c.R = 0.55; c.z0 = 2.0; c.t_sw = 3.85; c.t_end = 6.80;
      c.wx = wx;
      c.do_handover = (arm == 1);
      if (wx == 0.0 || wx == 1.4) {
        c.csv_path = tr_dir + "/" + id + (arm == 0 ? "_classic.csv" : "_neural.csv");
      }
      record(c);
    }
  }
  // Benign margin control for T1 (moderate speed V=1.10 m/s, wider turn R=0.85 m -> ample thrust/attitude margin)
  {
    SimConfig c{};
    c.case_id = "t1_benign_margin"; c.arm_name = "NN-Ideal (Benign V=1.1,R=0.85)";
    c.traj_kind = TrajKind::T1_JTURN_BRAKE;
    c.use_mellinger = false; c.V = 1.10; c.R = 0.85; c.z0 = 2.0; c.t_sw = 3.85; c.t_end = 6.80;
    c.do_handover = true;
    c.csv_path = tr_dir + "/t1_benign_neural.csv";
    record(c);
  }

  // =========================================================================
  // T2: Controller History State Continuity Error (t2-straight & t2-turn)
  // =========================================================================
  std::printf("\n=== [T2-A] Straight Cruise-to-Stop with Shifted Battery CoM + Headwind ===\n");
  for (double com : {0.0, 3.8, 4.8, 5.3}) {
    for (int arm = 0; arm < 4; arm++) {
      SimConfig c{};
      char id[64], nm[64];
      std::snprintf(id, sizeof(id), "t2_straight_com%.1f", com);
      const char *anames[4] = {"Classic-Keep", "NN-Warm-Shadow", "NN-Cold-Reset(l2f_reset)", "NN-Orig-Poison(-0.8)"};
      std::snprintf(nm, sizeof(nm), "%s (com=%.1fmm)", anames[arm], com);
      c.case_id = id; c.arm_name = nm;
      c.traj_kind = TrajKind::T2_STRAIGHT_CRUISE_STOP;
      c.use_mellinger = true;
      c.V = 0.70; c.R = 0.65; c.z0 = 2.2; c.t_sw = 4.00; c.t_end = 6.80;
      c.mass_scale = 1.06; c.wx = -0.9;
      c.com_y_mm = +com;          // +roll CoM bias
      c.com_x_mm = -0.75 * com;   // -pitch CoM bias
      c.do_handover = (arm != 0);
      c.t2_mode = (arm == 0) ? 0 : (arm - 1);
      if (std::fabs(com - 5.3) < 1e-3 || std::fabs(com - 4.8) < 1e-3) {
        const char *suf[4] = {"_classic.csv", "_warm.csv", "_cold.csv", "_poison.csv"};
        c.csv_path = tr_dir + "/" + id + suf[arm];
      }
      record(c);
    }
  }

  std::printf("\n=== [T2-B] Banked Right Turn + Brake (1-to-1 with PX4 t2-turn) ===\n");
  for (double com : {0.0, 3.8, 4.8, 5.1}) {
    for (int arm = 0; arm < 4; arm++) {
      SimConfig c{};
      char id[64], nm[64];
      std::snprintf(id, sizeof(id), "t2_turn_com%.1f", com);
      const char *anames[4] = {"Classic-Keep", "NN-Warm-Shadow", "NN-ZeroReset-GRU", "NN-Orig-Poison(-0.8)"};
      std::snprintf(nm, sizeof(nm), "%s (com=%.1fmm)", anames[arm], com);
      c.case_id = id; c.arm_name = nm;
      c.traj_kind = TrajKind::T2_RIGHT_TURN_BRAKE;
      c.use_mellinger = true;
      c.V = 1.45; c.R = 0.62; c.z0 = 2.2; c.t_sw = 3.55; c.t_end = 6.60;
      c.mass_scale = 1.05; c.wx = -0.8;
      c.com_y_mm = +com;
      c.com_x_mm = -0.75 * com;
      c.do_handover = (arm != 0);
      // arm 2 tests clean l2f_reset() (mode 3) without open-loop pre-saturation, arm 3 tests upstream rlt.orig=-0.8 poison (mode 2)
      c.t2_mode = (arm == 0 || arm == 1) ? 0 : (arm == 2 ? 3 : 2);
      if (std::fabs(com - 4.8) < 1e-3 || std::fabs(com - 5.1) < 1e-3) {
        const char *suf[4] = {"_classic.csv", "_warm.csv", "_cold.csv", "_poison.csv"};
        c.csv_path = tr_dir + "/" + id + suf[arm];
      }
      record(c);
    }
  }

  // =========================================================================
  // T3: Setpoint Reference Continuity Anomaly (t3-straight & t3-turn)
  // =========================================================================
  std::printf("\n=== [T3-A] Straight 1.20 m/s Cruise Reference Gap (Brake-then-Chase) ===\n");
  {
    SimConfig ck{};
    ck.case_id = "t3_straight"; ck.arm_name = "Classic-Keep";
    ck.traj_kind = TrajKind::T3_STRAIGHT_CRUISE;
    ck.use_mellinger = true; ck.V = 1.20; ck.z0 = 2.0; ck.t_sw = 3.80; ck.t_end = 6.60;
    ck.do_handover = false;
    ck.csv_path = tr_dir + "/t3_straight_classic.csv";
    record(ck);

    for (int gap : {0, 80, 180, 260}) {
      SimConfig c = ck;
      char nm[64], fn[64];
      std::snprintf(nm, sizeof(nm), "NN-Gap-%dms", gap);
      std::snprintf(fn, sizeof(fn), "/t3_straight_gap%dms.csv", gap);
      c.arm_name = nm; c.do_handover = true; c.ref_gap_ms = gap;
      c.csv_path = tr_dir + fn;
      record(c);
    }
  }

  std::printf("\n=== [T3-B] Constant-Altitude Tight U-Turn Reference Gap (1-to-1 with PX4 t3-turn) ===\n");
  {
    SimConfig ck{};
    ck.case_id = "t3_turn"; ck.arm_name = "Classic-Keep";
    ck.traj_kind = TrajKind::T3_LEVEL_UTURN;
    ck.use_mellinger = true; ck.V = 1.62; ck.R = 0.58; ck.z0 = 2.0; ck.t_sw = 3.92; ck.t_end = 6.80;
    ck.do_handover = false;
    ck.csv_path = tr_dir + "/t3_turn_classic.csv";
    record(ck);

    for (int gap : {0, 80, 168, 220}) {
      SimConfig c = ck;
      char nm[64], fn[64];
      std::snprintf(nm, sizeof(nm), "NN-Gap-%dms", gap);
      std::snprintf(fn, sizeof(fn), "/t3_turn_gap%dms.csv", gap);
      c.arm_name = nm; c.do_handover = true; c.ref_gap_ms = gap;
      c.csv_path = tr_dir + fn;
      record(c);
    }
    // Historical commit deca3ab1 bug: modeAbs hardcoded target_vel = 0 permanently
    SimConfig ch = ck;
    ch.arm_name = "NN-Historical-ZeroVelFF(deca3ab)";
    ch.do_handover = true; ch.drop_vel_ff = true;
    ch.csv_path = tr_dir + "/t3_turn_zerovelff.csv";
    record(ch);
  }

  // =========================================================================
  // T4: Authority Delivery Anomaly (t4-warmup & t4-turn-exit)
  // =========================================================================
  std::printf("\n=== [T4-A] Upstream Default rlt.motor_warmup=1 Mid-Air Handover Vacuum ===\n");
  {
    SimConfig ck{};
    ck.case_id = "t4_warmup"; ck.arm_name = "Classic-Keep";
    ck.traj_kind = TrajKind::T4_BANKED_CRUISE;
    ck.use_mellinger = true; ck.V = 1.42; ck.R = 0.64; ck.z0 = 2.0; ck.t_sw = 3.70; ck.t_end = 6.60;
    ck.do_handover = false;
    ck.csv_path = tr_dir + "/t4_warmup_classic.csv";
    record(ck);

    for (int wu : {0, 120, 220, 350, 500}) {
      SimConfig c = ck;
      char nm[64], fn[64];
      std::snprintf(nm, sizeof(nm), "NN-Warmup-%dms%s", wu, wu == 500 ? " (Upstream Default)" : "");
      std::snprintf(fn, sizeof(fn), "/t4_warmup_%dms.csv", wu);
      c.arm_name = nm; c.do_handover = true; c.upstream_warmup_ms = wu;
      c.csv_path = tr_dir + fn;
      record(c);
    }
  }

  std::printf("\n=== [T4-B] Turn-Exit Stale Classic Differential Motor Hold (1-to-1 with PX4 t4-turn-exit) ===\n");
  {
    SimConfig ck{};
    ck.case_id = "t4_turn_exit"; ck.arm_name = "Classic-Keep";
    ck.traj_kind = TrajKind::T4_TURN_EXIT;
    // Stronger classic Mellinger attitude response during sharp roll-in before t_sw = 3.560s
    ck.use_mellinger = true; ck.V = 1.25; ck.R = 0.60; ck.z0 = 2.0; ck.t_sw = 3.560; ck.t_end = 6.20;
    ck.do_handover = false;
    ck.csv_path = tr_dir + "/t4_turn_exit_classic.csv";
    record(ck);

    for (int hold : {0, 16, 24, 40, 60}) {
      SimConfig c = ck;
      char nm[64], fn[64];
      std::snprintf(nm, sizeof(nm), "NN-StaleHold-%dms", hold);
      std::snprintf(fn, sizeof(fn), "/t4_turn_exit_hold%dms.csv", hold);
      c.arm_name = nm; c.do_handover = true; c.stale_hold_ms = hold;
      c.csv_path = tr_dir + fn;
      record(c);
    }
  }

  // =========================================================================
  // 4-Step Counterfactual Factor Diagnoser (Raw Upstream Stack -> Classic-Keep)
  // =========================================================================
  std::printf("\n=== [ATTRIBUTION] 4-Step Counterfactual Factor Diagnoser on Raw Upstream Mid-Air Takeover ===\n");
  {
    SimConfig base{};
    base.case_id = "cf_attribution";
    base.traj_kind = TrajKind::T2_RIGHT_TURN_BRAKE;
    base.use_mellinger = true; base.V = 1.45; base.R = 0.62; base.z0 = 2.2; base.t_sw = 3.55; base.t_end = 6.60;
    base.mass_scale = 1.05; base.wx = -0.8; base.com_y_mm = 4.6; base.com_x_mm = -3.45;

    // Step 0: Raw upstream takeover (has T4 warmup 220ms + T3 gap 168ms + T2 history bug + T1 maneuver load)
    SimConfig s0 = base; s0.arm_name = "0. Raw-Takeover (T1+T2+T3+T4)";
    s0.do_handover = true; s0.upstream_warmup_ms = 220; s0.ref_gap_ms = 168; s0.t2_mode = 1;
    s0.csv_path = tr_dir + "/cf_attr_step0.csv";
    record(s0);

    // Step 1: Strip T4 (0ms instant delivery)
    SimConfig s1 = base; s1.arm_name = "1. Strip-T4 (T1+T2+T3)";
    s1.do_handover = true; s1.upstream_warmup_ms = 0; s1.ref_gap_ms = 168; s1.t2_mode = 2;
    s1.csv_path = tr_dir + "/cf_attr_step1.csv";
    record(s1);

    // Step 2: Strip T4 + T3 (continuous trajectory reference)
    SimConfig s2 = base; s2.arm_name = "2. Strip-T4-T3 (T1+T2)";
    s2.do_handover = true; s2.upstream_warmup_ms = 0; s2.ref_gap_ms = 0; s2.t2_mode = 2;
    s2.csv_path = tr_dir + "/cf_attr_step2.csv";
    record(s2);

    // Step 3: Strip T4 + T3 + T2 (Warm-Shadow GRU + aligned action -> pure T1 residual)
    SimConfig s3 = base; s3.arm_name = "3. Strip-T4-T3-T2 (Pure T1)";
    s3.do_handover = true; s3.upstream_warmup_ms = 0; s3.ref_gap_ms = 0; s3.t2_mode = 0;
    s3.csv_path = tr_dir + "/cf_attr_step3.csv";
    record(s3);

    // Step 4: Classic-Keep oracle
    SimConfig s4 = base; s4.arm_name = "4. Classic-Keep Oracle";
    s4.do_handover = false;
    s4.csv_path = tr_dir + "/cf_attr_step4.csv";
    record(s4);
  }

  // Export structured JSON summary
  std::string json_path = out_dir + "/summary.json";
  FILE *jf = std::fopen(json_path.c_str(), "w");
  if (jf) {
    std::fprintf(jf, "[\n");
    for (size_t i = 0; i < all.size(); i++) {
      const auto &m = all[i];
      std::fprintf(jf,
        "  {\"case_id\": \"%s\", \"arm_name\": \"%s\", \"t_sw\": %.3f, "
        "\"entry_speed_xy\": %.4f, \"entry_tilt_deg\": %.3f, \"entry_z\": %.4f, "
        "\"first_motor_jump\": %.4f, \"peak_tilt_deg\": %.3f, \"t_peak_tilt\": %.3f, "
        "\"min_speed_xy\": %.4f, \"max_speed_xy\": %.4f, \"min_vz\": %.4f, "
        "\"max_alt_loss_cm\": %.3f, \"max_world_drop_cm\": %.3f, \"max_pos_err_xy\": %.4f, \"crashed\": %s}%s\n",
        m.case_id.c_str(), m.arm_name.c_str(), m.t_sw,
        m.entry_speed_xy, m.entry_tilt_deg, m.entry_z,
        m.first_motor_jump, m.peak_tilt_deg, m.t_peak_tilt,
        m.min_speed_xy, m.max_speed_xy, m.min_vz,
        m.max_alt_loss_cm, m.max_world_drop_cm, m.max_pos_err_xy,
        m.crashed ? "true" : "false",
        (i + 1 < all.size()) ? "," : "");
    }
    std::fprintf(jf, "]\n");
    std::fclose(jf);
  }
  std::printf("\nSaved %zu runs to %s\n", all.size(), json_path.c_str());
  return 0;
}
