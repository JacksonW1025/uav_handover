#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <mutex>
#include <string>
#include <vector>

#include <gz/msgs/actuators.pb.h>
#include <gz/plugin/Register.hh>
#include <gz/sim/Entity.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/components/JointVelocity.hh>
#include <gz/sim/components/LinearVelocity.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/transport/Node.hh>

namespace mcnn_cleanroom
{

struct MotorPacket {
  int64_t rx_seq{0};
  int64_t rx_sim_us{0};
  int64_t px4_pub_us{0};
  int is_neural{0};
  int64_t mcnn_seq{0};
  double w[4]{0.0, 0.0, 0.0, 0.0};
  bool valid{false};
  bool applied{false};
};

class McnnMotorRelayPlugin
    : public gz::sim::System,
      public gz::sim::ISystemConfigure,
      public gz::sim::ISystemPreUpdate,
      public gz::sim::ISystemPostUpdate
{
public:
  McnnMotorRelayPlugin() = default;

  ~McnnMotorRelayPlugin() override
  {
    FlushLogs();
  }

  void Configure(const gz::sim::Entity &entity,
                 const std::shared_ptr<const sdf::Element> &sdf,
                 gz::sim::EntityComponentManager &ecm,
                 gz::sim::EventManager & /*eventMgr*/) override
  {
    model_ = gz::sim::Model(entity);
    model_name_ = model_.Name(ecm);
    if (sdf->HasElement("model_name")) {
      model_name_ = sdf->Get<std::string>("model_name");
    }

    input_topic_ = "/" + model_name_ + "/command/motor_speed";
    output_topic_ = "/" + model_name_ + "/command/motor_speed_applied";
    if (sdf->HasElement("input_topic")) {
      input_topic_ = sdf->Get<std::string>("input_topic");
    }
    if (sdf->HasElement("output_topic")) {
      output_topic_ = sdf->Get<std::string>("output_topic");
    }
    if (sdf->HasElement("hold_duration_ms")) {
      hold_duration_us_ = static_cast<int64_t>(
          std::llround(sdf->Get<double>("hold_duration_ms") * 1000.0));
    }
    if (sdf->HasElement("log_path")) {
      step_log_path_ = sdf->Get<std::string>("log_path");
    }
    if (sdf->HasElement("rx_log_path")) {
      rx_log_path_ = sdf->Get<std::string>("rx_log_path");
    }
    if (sdf->HasElement("wind_vx")) {
      wind_vx_ = sdf->Get<double>("wind_vx");
    }
    if (sdf->HasElement("wind_vy")) {
      wind_vy_ = sdf->Get<double>("wind_vy");
    }
    if (sdf->HasElement("wind_vz")) {
      wind_vz_ = sdf->Get<double>("wind_vz");
    }
    if (sdf->HasElement("wind_drag_quad")) {
      wind_drag_quad_ = sdf->Get<double>("wind_drag_quad");
    }
    if (sdf->HasElement("wind_drag_lin")) {
      wind_drag_lin_ = sdf->Get<double>("wind_drag_lin");
    }
    if (sdf->HasElement("wind_ramp_start_s")) {
      wind_ramp_start_s_ = sdf->Get<double>("wind_ramp_start_s");
    }
    if (sdf->HasElement("wind_ramp_dur_s")) {
      wind_ramp_dur_s_ = sdf->Get<double>("wind_ramp_dur_s");
    }

    base_link_entity_ = model_.LinkByName(ecm, "base_link");
    for (int i = 0; i < 4; ++i) {
      rotor_joints_[i] = model_.JointByName(ecm, "rotor_" + std::to_string(i) + "_joint");
    }

    if (!step_log_path_.empty()) {
      step_log_.open(step_log_path_, std::ios::out | std::ios::trunc);
      step_log_ << "sim_us,step_idx,hold_active,forwarded_seq,forwarded_is_neural,"
                   "forwarded_mcnn_seq,forwarded_px4_pub_us,overwritten_mcnn_count,"
                   "cmd_w0,cmd_w1,cmd_w2,cmd_w3,"
                   "joint_w0,joint_w1,joint_w2,joint_w3,"
                   "rx_latest_seq,rx_latest_is_neural,rx_latest_mcnn_seq,"
                   "rx_latest_w0,rx_latest_w1,rx_latest_w2,rx_latest_w3\n";
    }
    if (!rx_log_path_.empty()) {
      rx_log_.open(rx_log_path_, std::ios::out | std::ios::trunc);
      rx_log_ << "rx_seq,rx_sim_us,px4_pub_us,is_neural,mcnn_seq,w0,w1,w2,w3\n";
    }

    actuators_pub_ = node_.Advertise<gz::msgs::Actuators>(output_topic_);
    node_.Subscribe(input_topic_, &McnnMotorRelayPlugin::OnMotorMsg, this);
  }

  void PreUpdate(const gz::sim::UpdateInfo &info,
                 gz::sim::EntityComponentManager &ecm) override
  {
    if (info.paused) {
      return;
    }

    const int64_t sim_us =
        std::chrono::duration_cast<std::chrono::microseconds>(info.simTime).count();

    // Optional deterministic aerodynamic wind force on base_link (world ENU frame),
    // smoothly ramped after takeoff so pre-arm ground rest checks are unaffected.
    const double sim_s = static_cast<double>(sim_us) * 1e-6;
    double wind_scale = 0.0;
    if (sim_s >= wind_ramp_start_s_) {
      wind_scale = (wind_ramp_dur_s_ > 1e-6)
                       ? std::min(1.0, (sim_s - wind_ramp_start_s_) / wind_ramp_dur_s_)
                       : 1.0;
    }
    if (wind_scale > 0.0 && (wind_drag_quad_ > 0.0 || wind_drag_lin_ > 0.0) &&
        base_link_entity_ != gz::sim::kNullEntity) {
      gz::sim::Link link(base_link_entity_);
      auto vel_opt = link.WorldLinearVelocity(ecm);
      gz::math::Vector3d v_body(0.0, 0.0, 0.0);
      if (vel_opt.has_value()) {
        v_body = vel_opt.value();
      } else {
        link.EnableVelocityChecks(ecm, true);
      }
      const gz::math::Vector3d v_wind(wind_vx_, wind_vy_, wind_vz_);
      const gz::math::Vector3d v_rel = v_wind - v_body;
      const double speed = v_rel.Length();
      const gz::math::Vector3d force =
          v_rel * ((wind_drag_quad_ * speed + wind_drag_lin_) * wind_scale);
      link.AddWorldForce(ecm, force);
    }

    MotorPacket to_publish{};
    bool do_publish = false;

    {
      std::lock_guard<std::mutex> lock(mutex_);
      last_sim_us_ = sim_us;
      ++step_idx_;

      if (hold_active_ && sim_us >= hold_end_sim_us_) {
        hold_active_ = false;
        if (latest_rx_.valid) {
          forwarded_ = latest_rx_;
          forwarded_.applied = true;
          latest_rx_.applied = true;
          to_publish = forwarded_;
          do_publish = true;
        }
      } else if (!hold_active_ && latest_rx_.valid) {
        if (latest_rx_.rx_seq != forwarded_.rx_seq) {
          forwarded_ = latest_rx_;
          to_publish = forwarded_;
          do_publish = true;
        }
        forwarded_.applied = true;
        latest_rx_.applied = true;
      }
    }

    if (do_publish) {
      PublishActuators(to_publish.w);
    }
  }

  void PostUpdate(const gz::sim::UpdateInfo &info,
                  const gz::sim::EntityComponentManager &ecm) override
  {
    if (info.paused) {
      return;
    }

    const int64_t sim_us =
        std::chrono::duration_cast<std::chrono::microseconds>(info.simTime).count();

    double jw[4] = {0.0, 0.0, 0.0, 0.0};
    for (int i = 0; i < 4; ++i) {
      if (rotor_joints_[i] != gz::sim::kNullEntity) {
        auto comp = ecm.Component<gz::sim::components::JointVelocity>(rotor_joints_[i]);
        if (comp != nullptr && !comp->Data().empty()) {
          jw[i] = comp->Data()[0];
        }
      }
    }

    std::lock_guard<std::mutex> lock(mutex_);
    if (step_log_.is_open()) {
      step_log_ << sim_us << "," << step_idx_ << "," << (hold_active_ ? 1 : 0) << ","
                << forwarded_.rx_seq << "," << forwarded_.is_neural << ","
                << forwarded_.mcnn_seq << "," << forwarded_.px4_pub_us << ","
                << overwritten_mcnn_count_ << ","
                << std::fixed << std::setprecision(4)
                << forwarded_.w[0] << "," << forwarded_.w[1] << ","
                << forwarded_.w[2] << "," << forwarded_.w[3] << ","
                << jw[0] << "," << jw[1] << "," << jw[2] << "," << jw[3] << ","
                << latest_rx_.rx_seq << "," << latest_rx_.is_neural << ","
                << latest_rx_.mcnn_seq << ","
                << latest_rx_.w[0] << "," << latest_rx_.w[1] << ","
                << latest_rx_.w[2] << "," << latest_rx_.w[3] << "\n";
      if ((step_idx_ % 250) == 0) {
        step_log_.flush();
        if (rx_log_.is_open()) {
          rx_log_.flush();
        }
      }
    }
  }

private:
  void OnMotorMsg(const gz::msgs::Actuators &msg)
  {
    MotorPacket pkt{};
    pkt.valid = true;
    const int n = std::min(4, msg.velocity_size());
    for (int i = 0; i < n; ++i) {
      pkt.w[i] = msg.velocity(i);
    }

    if (msg.has_header()) {
      for (int i = 0; i < msg.header().data_size(); ++i) {
        const auto &kv = msg.header().data(i);
        if (kv.value_size() == 0) {
          continue;
        }
        const std::string &k = kv.key();
        const std::string &v = kv.value(0);
        if (k == "px4_pub_us") {
          pkt.px4_pub_us = std::stoll(v);
        } else if (k == "is_neural") {
          pkt.is_neural = std::stoi(v);
        } else if (k == "mcnn_seq") {
          pkt.mcnn_seq = std::stoll(v);
        }
      }
    }

    MotorPacket to_publish{};
    bool do_publish = false;

    {
      std::lock_guard<std::mutex> lock(mutex_);
      pkt.rx_seq = ++rx_seq_;
      pkt.rx_sim_us = last_sim_us_;

      if (rx_log_.is_open()) {
        rx_log_ << pkt.rx_seq << "," << pkt.rx_sim_us << "," << pkt.px4_pub_us << ","
                << pkt.is_neural << "," << pkt.mcnn_seq << ","
                << std::fixed << std::setprecision(4)
                << pkt.w[0] << "," << pkt.w[1] << "," << pkt.w[2] << "," << pkt.w[3]
                << "\n";
      }

      if (latest_rx_.valid && latest_rx_.is_neural == 1 && !latest_rx_.applied) {
        ++overwritten_mcnn_count_;
      }

      if (pkt.is_neural == 0) {
        last_classic_ = pkt;
      }

      latest_rx_ = pkt;

      if (hold_duration_us_ == 0) {
        forwarded_ = pkt;
        to_publish = pkt;
        do_publish = true;
      } else {
        if (!hold_triggered_ && pkt.is_neural == 1) {
          hold_triggered_ = true;
          hold_active_ = true;
          hold_start_sim_us_ = last_sim_us_;
          hold_end_sim_us_ = last_sim_us_ + hold_duration_us_;
          if (last_classic_.valid) {
            forwarded_ = last_classic_;
            to_publish = last_classic_;
            do_publish = true;
          }
        } else if (!hold_active_) {
          forwarded_ = pkt;
          to_publish = pkt;
          do_publish = true;
        }
      }
    }

    if (do_publish) {
      PublishActuators(to_publish.w);
    }
  }

  void PublishActuators(const double w[4])
  {
    gz::msgs::Actuators out;
    for (int i = 0; i < 4; ++i) {
      out.add_velocity(w[i]);
    }
    actuators_pub_.Publish(out);
  }

  void FlushLogs()
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (step_log_.is_open()) {
      step_log_.flush();
      step_log_.close();
    }
    if (rx_log_.is_open()) {
      rx_log_.flush();
      rx_log_.close();
    }
  }

  gz::sim::Model model_{gz::sim::kNullEntity};
  gz::sim::Entity base_link_entity_{gz::sim::kNullEntity};
  gz::sim::Entity rotor_joints_[4]{gz::sim::kNullEntity, gz::sim::kNullEntity,
                                   gz::sim::kNullEntity, gz::sim::kNullEntity};
  std::string model_name_;
  std::string input_topic_;
  std::string output_topic_;
  std::string step_log_path_;
  std::string rx_log_path_;

  double wind_vx_{0.0};
  double wind_vy_{0.0};
  double wind_vz_{0.0};
  double wind_drag_quad_{0.0};
  double wind_drag_lin_{0.0};
  double wind_ramp_start_s_{12.0};
  double wind_ramp_dur_s_{1.0};

  int64_t hold_duration_us_{0};
  bool hold_triggered_{false};
  bool hold_active_{false};
  int64_t hold_start_sim_us_{0};
  int64_t hold_end_sim_us_{0};

  std::mutex mutex_;
  int64_t last_sim_us_{0};
  int64_t step_idx_{0};
  int64_t rx_seq_{0};
  int64_t overwritten_mcnn_count_{0};

  MotorPacket last_classic_{};
  MotorPacket latest_rx_{};
  MotorPacket forwarded_{};

  gz::transport::Node node_;
  gz::transport::Node::Publisher actuators_pub_;

  std::ofstream step_log_;
  std::ofstream rx_log_;
};

}  // namespace mcnn_cleanroom

GZ_ADD_PLUGIN(mcnn_cleanroom::McnnMotorRelayPlugin,
              gz::sim::System,
              mcnn_cleanroom::McnnMotorRelayPlugin::ISystemConfigure,
              mcnn_cleanroom::McnnMotorRelayPlugin::ISystemPreUpdate,
              mcnn_cleanroom::McnnMotorRelayPlugin::ISystemPostUpdate)

GZ_ADD_PLUGIN_ALIAS(mcnn_cleanroom::McnnMotorRelayPlugin,
                    "mcnn_cleanroom::McnnMotorRelayPlugin")
