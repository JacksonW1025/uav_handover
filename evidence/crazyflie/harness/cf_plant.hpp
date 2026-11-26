#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>
#define RL_TOOLS_NAMESPACE_WRAPPER plant_rlt
#include <rl_tools/operations/cpu.h>
#include <rl_tools/rl/environments/l2f/multirotor.h>
#undef RL_TOOLS_NAMESPACE_WRAPPER

extern "C" {
#include "stabilizer_types.h"
#include "stubs/motors.h"
#include "stubs/cmsis_stub.h"
#include "controller_pid.h"
#include "controller_mellinger.h"
#include "power_distribution.h"
#include "sim_hal.h"
void controllerOutOfTree(control_t *control, setpoint_t *setpoint,
                         const sensorData_t *sensors, const state_t *state,
                         const uint32_t tick);
}

struct CfPhysicsState {
  double pos[3] = {0.0, 0.0, 0.0};
  double quat[4] = {1.0, 0.0, 0.0, 0.0}; // qw, qx, qy, qz
  double vel[3] = {0.0, 0.0, 0.0};
  double omega[3] = {0.0, 0.0, 0.0};     // FLU body rad/s
  double rpm_rel[4] = {0.0, 0.0, 0.0, 0.0}; // relative RPM in [0, 1]
};

struct CfEnvDisturbance {
  double mass_scale = 1.0;          // e.g. 1.0 nominal (30.6g), >1.0 payload
  double rotor_efficiency[4] = {1.0, 1.0, 1.0, 1.0}; // per-rotor thrust efficiency (propeller/motor wear)
  bool brushless_cf21bl = false;    // false: cf2 brushed (55.5ms/249.4ms); true: cf21bl DShot active braking
  double linear_drag_xy = 0.012;    // N/(m/s) parasitic airframe + rotor H-drag
  double linear_drag_z = 0.018;
  double quad_drag = 0.004;         // N/(m/s)^2 aerodynamic drag
  double wind_vel[3] = {0.0, 0.0, 0.0}; // world wind velocity (m/s)
  double ext_force[3] = {0.0, 0.0, 0.0}; // extra world force (N)
  double ext_torque[3] = {0.0, 0.0, 0.0}; // extra body torque (N*m)
};

class CrazyfliePlant {
public:
  CfPhysicsState s;
  CfEnvDisturbance env;

  // Exact official RLtools Crazyflie 2.1 parameters from parameters/dynamics/crazyflie.h
  static constexpr auto kDyn = plant_rlt::rl_tools::rl::environments::l2f::parameters::dynamics::crazyflie<double, size_t>;

  void reset_hover(double x, double y, double z, double yaw_rad = 0.0) {
    s.pos[0] = x; s.pos[1] = y; s.pos[2] = z;
    s.quat[0] = std::cos(yaw_rad * 0.5);
    s.quat[1] = 0.0;
    s.quat[2] = 0.0;
    s.quat[3] = std::sin(yaw_rad * 0.5);
    s.vel[0] = s.vel[1] = s.vel[2] = 0.0;
    s.omega[0] = s.omega[1] = s.omega[2] = 0.0;
    // Exact hover equilibrium solve: mass*9.81/4 = c0 + c1*u + c2*u^2
    double m = kDyn.mass * env.mass_scale;
    double f_req = m * 9.81 / 4.0;
    double c0 = kDyn.rotor_thrust_coefficients[0][0];
    double c1 = kDyn.rotor_thrust_coefficients[0][1];
    double c2 = kDyn.rotor_thrust_coefficients[0][2];
    double disc = std::max(0.0, c1 * c1 - 4.0 * c2 * (c0 - f_req));
    double u_hov = (-c1 + std::sqrt(disc)) / (2.0 * c2);
    for (int i = 0; i < 4; i++) s.rpm_rel[i] = u_hov;
  }

  double hover_throttle_rel() const {
    double m = kDyn.mass * env.mass_scale;
    double f_req = m * 9.81 / 4.0;
    double c0 = kDyn.rotor_thrust_coefficients[0][0];
    double c1 = kDyn.rotor_thrust_coefficients[0][1];
    double c2 = kDyn.rotor_thrust_coefficients[0][2];
    double disc = std::max(0.0, c1 * c1 - 4.0 * c2 * (c0 - f_req));
    return (-c1 + std::sqrt(disc)) / (2.0 * c2);
  }

  void derivatives(const CfPhysicsState &st, const float motor_cmd[4], CfPhysicsState &ds) const {
    double thrust_body[3] = {0.0, 0.0, 0.0};
    double torque_body[3] = {env.ext_torque[0], env.ext_torque[1], env.ext_torque[2]};

    for (int i = 0; i < 4; i++) {
      double u = st.rpm_rel[i];
      double c0 = kDyn.rotor_thrust_coefficients[i][0];
      double c1 = kDyn.rotor_thrust_coefficients[i][1];
      double c2 = kDyn.rotor_thrust_coefficients[i][2];
      double f_mag = (c0 + c1 * u + c2 * u * u) * env.rotor_efficiency[i];
      if (u <= 1e-4) f_mag = 0.0;

      double rf[3] = {
        kDyn.rotor_thrust_directions[i][0] * f_mag,
        kDyn.rotor_thrust_directions[i][1] * f_mag,
        kDyn.rotor_thrust_directions[i][2] * f_mag
      };
      thrust_body[0] += rf[0];
      thrust_body[1] += rf[1];
      thrust_body[2] += rf[2];

      double kt = kDyn.rotor_torque_constants[i];
      torque_body[0] += kDyn.rotor_torque_directions[i][0] * (f_mag * kt);
      torque_body[1] += kDyn.rotor_torque_directions[i][1] * (f_mag * kt);
      torque_body[2] += kDyn.rotor_torque_directions[i][2] * (f_mag * kt);

      // r x F
      const auto &rp = kDyn.rotor_positions[i];
      torque_body[0] += rp[1] * rf[2] - rp[2] * rf[1];
      torque_body[1] += rp[2] * rf[0] - rp[0] * rf[2];
      torque_body[2] += rp[0] * rf[1] - rp[1] * rf[0];

      double cmd = std::max(0.0, std::min(1.0, (double)motor_cmd[i]));
      double tau = env.brushless_cf21bl
        ? ((cmd >= u) ? 0.020 : 0.025)
        : ((cmd >= u) ? kDyn.rotor_time_constants_rising[i] : kDyn.rotor_time_constants_falling[i]);
      ds.rpm_rel[i] = (cmd - u) / tau;
    }

    ds.pos[0] = st.vel[0];
    ds.pos[1] = st.vel[1];
    ds.pos[2] = st.vel[2];

    double qw = st.quat[0], qx = st.quat[1], qy = st.quat[2], qz = st.quat[3];
    double wx = st.omega[0], wy = st.omega[1], wz = st.omega[2];
    ds.quat[0] = 0.5 * (-qx * wx - qy * wy - qz * wz);
    ds.quat[1] = 0.5 * ( qw * wx + qy * wz - qz * wy);
    ds.quat[2] = 0.5 * ( qw * wy - qx * wz + qz * wx);
    ds.quat[3] = 0.5 * ( qw * wz + qx * wy - qy * wx);

    // Rotate body thrust to world
    double R00 = 1.0 - 2.0*(qy*qy + qz*qz), R01 = 2.0*(qx*qy - qw*qz), R02 = 2.0*(qx*qz + qw*qy);
    double R10 = 2.0*(qx*qy + qw*qz), R11 = 1.0 - 2.0*(qx*qx + qz*qz), R12 = 2.0*(qy*qz - qw*qx);
    double R20 = 2.0*(qx*qz - qw*qy), R21 = 2.0*(qy*qz + qw*qx), R22 = 1.0 - 2.0*(qx*qx + qy*qy);

    double fw[3] = {
      R00*thrust_body[0] + R01*thrust_body[1] + R02*thrust_body[2],
      R10*thrust_body[0] + R11*thrust_body[1] + R12*thrust_body[2],
      R20*thrust_body[0] + R21*thrust_body[1] + R22*thrust_body[2]
    };

    // Aerodynamic drag from relative air velocity (v - v_wind)
    double vrel[3] = {
      st.vel[0] - env.wind_vel[0],
      st.vel[1] - env.wind_vel[1],
      st.vel[2] - env.wind_vel[2]
    };
    double vnorm = std::sqrt(vrel[0]*vrel[0] + vrel[1]*vrel[1] + vrel[2]*vrel[2]);
    fw[0] += -env.linear_drag_xy * vrel[0] - env.quad_drag * vnorm * vrel[0] + env.ext_force[0];
    fw[1] += -env.linear_drag_xy * vrel[1] - env.quad_drag * vnorm * vrel[1] + env.ext_force[1];
    fw[2] += -env.linear_drag_z  * vrel[2] - env.quad_drag * vnorm * vrel[2] + env.ext_force[2];

    double m = kDyn.mass * env.mass_scale;
    ds.vel[0] = fw[0] / m + kDyn.gravity[0];
    ds.vel[1] = fw[1] / m + kDyn.gravity[1];
    ds.vel[2] = fw[2] / m + kDyn.gravity[2];

    // Euler rotational dynamics: J_inv * (torque - omega x (J * omega))
    double Jw[3] = {
      kDyn.J[0][0] * wx,
      kDyn.J[1][1] * wy,
      kDyn.J[2][2] * wz
    };
    double cross[3] = {
      wy * Jw[2] - wz * Jw[1],
      wz * Jw[0] - wx * Jw[2],
      wx * Jw[1] - wy * Jw[0]
    };
    ds.omega[0] = kDyn.J_inv[0][0] * (torque_body[0] - cross[0]);
    ds.omega[1] = kDyn.J_inv[1][1] * (torque_body[1] - cross[1]);
    ds.omega[2] = kDyn.J_inv[2][2] * (torque_body[2] - cross[2]);
  }

  static CfPhysicsState add_scaled(const CfPhysicsState &a, const CfPhysicsState &b, double h) {
    CfPhysicsState r;
    for (int i = 0; i < 3; i++) {
      r.pos[i] = a.pos[i] + h * b.pos[i];
      r.vel[i] = a.vel[i] + h * b.vel[i];
      r.omega[i] = a.omega[i] + h * b.omega[i];
    }
    for (int i = 0; i < 4; i++) {
      r.quat[i] = a.quat[i] + h * b.quat[i];
      r.rpm_rel[i] = a.rpm_rel[i] + h * b.rpm_rel[i];
    }
    return r;
  }

  void step_rk4(double dt, const float motor_cmd[4]) {
    CfPhysicsState k1, k2, k3, k4;
    derivatives(s, motor_cmd, k1);
    derivatives(add_scaled(s, k1, 0.5 * dt), motor_cmd, k2);
    derivatives(add_scaled(s, k2, 0.5 * dt), motor_cmd, k3);
    derivatives(add_scaled(s, k3, dt), motor_cmd, k4);

    for (int i = 0; i < 3; i++) {
      s.pos[i] += (dt / 6.0) * (k1.pos[i] + 2.0*k2.pos[i] + 2.0*k3.pos[i] + k4.pos[i]);
      s.vel[i] += (dt / 6.0) * (k1.vel[i] + 2.0*k2.vel[i] + 2.0*k3.vel[i] + k4.vel[i]);
      s.omega[i] += (dt / 6.0) * (k1.omega[i] + 2.0*k2.omega[i] + 2.0*k3.omega[i] + k4.omega[i]);
    }
    for (int i = 0; i < 4; i++) {
      s.quat[i] += (dt / 6.0) * (k1.quat[i] + 2.0*k2.quat[i] + 2.0*k3.quat[i] + k4.quat[i]);
      s.rpm_rel[i] = std::max(0.0, std::min(1.0,
        s.rpm_rel[i] + (dt / 6.0) * (k1.rpm_rel[i] + 2.0*k2.rpm_rel[i] + 2.0*k3.rpm_rel[i] + k4.rpm_rel[i])));
    }
    double qn = std::sqrt(s.quat[0]*s.quat[0] + s.quat[1]*s.quat[1] + s.quat[2]*s.quat[2] + s.quat[3]*s.quat[3]);
    for (int i = 0; i < 4; i++) s.quat[i] /= qn;
  }

  double tilt_deg() const {
    double qw = s.quat[0], qx = s.quat[1], qy = s.quat[2];
    double r22 = 1.0 - 2.0 * (qx * qx + qy * qy);
    r22 = std::max(-1.0, std::min(1.0, r22));
    return std::acos(r22) * (180.0 / M_PI);
  }

  double speed_horiz() const {
    return std::sqrt(s.vel[0]*s.vel[0] + s.vel[1]*s.vel[1]);
  }

  double speed_3d() const {
    return std::sqrt(s.vel[0]*s.vel[0] + s.vel[1]*s.vel[1] + s.vel[2]*s.vel[2]);
  }

  void fill_firmware_structs(uint32_t tick_ms, state_t &fw_state, sensorData_t &fw_sensors) const {
    std::memset(&fw_state, 0, sizeof(fw_state));
    std::memset(&fw_sensors, 0, sizeof(fw_sensors));

    double qw = s.quat[0], qx = s.quat[1], qy = s.quat[2], qz = s.quat[3];
    fw_state.position.timestamp = tick_ms;
    fw_state.position.x = (float)s.pos[0];
    fw_state.position.y = (float)s.pos[1];
    fw_state.position.z = (float)s.pos[2];

    fw_state.velocity.timestamp = tick_ms;
    fw_state.velocity.x = (float)s.vel[0];
    fw_state.velocity.y = (float)s.vel[1];
    fw_state.velocity.z = (float)s.vel[2];

    fw_state.attitudeQuaternion.w = (float)qw;
    fw_state.attitudeQuaternion.x = (float)qx;
    fw_state.attitudeQuaternion.y = (float)qy;
    fw_state.attitudeQuaternion.z = (float)qz;

    // Exact sensfusion6GetEulerRPY formulas from crazyflie-firmware/src/modules/src/sensfusion6.c
    double gx = 2.0 * (qx * qz - qw * qy);
    double gy = 2.0 * (qw * qx + qy * qz);
    double gz = qw * qw - qx * qx - qy * qy + qz * qz;
    gx = std::max(-1.0, std::min(1.0, gx));
    fw_state.attitude.timestamp = tick_ms;
    fw_state.attitude.yaw   = (float)(std::atan2(2.0*(qw*qz + qx*qy), qw*qw + qx*qx - qy*qy - qz*qz) * (180.0 / M_PI));
    fw_state.attitude.pitch = (float)(std::asin(gx) * (180.0 / M_PI)); // inverted legacy CF2 pitch
    fw_state.attitude.roll  = (float)(std::atan2(gy, gz) * (180.0 / M_PI));

    constexpr double RAD2DEG = 180.0 / M_PI;
    fw_sensors.gyro.x = (float)(s.omega[0] * RAD2DEG);
    fw_sensors.gyro.y = (float)(s.omega[1] * RAD2DEG);
    fw_sensors.gyro.z = (float)(s.omega[2] * RAD2DEG);
    fw_sensors.acc.z  = 1.0f;
  }
};
