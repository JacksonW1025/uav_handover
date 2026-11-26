#!/usr/bin/env python3
"""Generate clean-room Gazebo Harmonic world and x500 model SDFs for MCNN handover SITL."""

from pathlib import Path
import xml.etree.ElementTree as ET


def generate_world_sdf(
    px4_dir: Path,
    out_path: Path,
    world_name: str = "mcnn_world",
    wind_enu: tuple[float, float, float] = (0.0, 0.0, 0.0),
    include_model_dir: str | None = None,
    include_model_instance: str | None = None,
    spawn_pose: tuple[float, float, float, float, float, float] = (0.0, 0.0, 0.24, 0.0, 0.0, 0.0),
) -> Path:
    src_world = px4_dir / "Tools/simulation/gz/worlds/default.sdf"
    text = src_world.read_text(encoding="utf-8")
    text = text.replace('<world name="default">', f'<world name="{world_name}">', 1)
    inject = []
    if any(abs(v) > 1e-9 for v in wind_enu):
        wx, wy, wz = wind_enu
        inject.append(
            f"    <wind>\n"
            f"      <linear_velocity>{wx:.4f} {wy:.4f} {wz:.4f}</linear_velocity>\n"
            f"    </wind>\n"
        )
    if include_model_dir and include_model_instance:
        x, y, z, r, p, yw = spawn_pose
        inject.append(
            f"    <include>\n"
            f"      <uri>model://{include_model_dir}</uri>\n"
            f"      <name>{include_model_instance}</name>\n"
            f"      <pose>{x:.4f} {y:.4f} {z:.4f} {r:.6f} {p:.6f} {yw:.6f}</pose>\n"
            f"    </include>\n"
        )
    if inject:
        text = text.replace("  </world>", "".join(inject) + "  </world>", 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def generate_x500_model_dir(
    px4_dir: Path,
    out_models_root: Path,
    model_dir_name: str = "x500_mcnn",
    model_instance_name: str = "x500_mcnn_0",
    use_relay_plugin: bool = True,
    hold_duration_ms: float = 0.0,
    relay_step_log: Path | None = None,
    relay_rx_log: Path | None = None,
    wind_enu: tuple[float, float, float] = (0.0, 0.0, 0.0),
    wind_drag_quad: float = 0.0,
    wind_drag_lin: float = 0.0,
    payload_mass_kg: float = 0.0,
    payload_offset_xyz: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Path:
    src_x500 = px4_dir / "Tools/simulation/gz/models/x500/model.sdf"
    sdf_text = src_x500.read_text(encoding="utf-8")
    sdf_text = sdf_text.replace("<model name='x500'>", f"<model name='{model_dir_name}'>", 1)

    if use_relay_plugin:
        sdf_text = sdf_text.replace(
            "<commandSubTopic>command/motor_speed</commandSubTopic>",
            "<commandSubTopic>command/motor_speed_applied</commandSubTopic>",
        )

    extra_blocks = []

    if payload_mass_kg > 1e-6:
        px, py, pz = payload_offset_xyz
        # Compact rigid test payload attached to base_link (small 6cm cube inertia).
        ixx = payload_mass_kg * (0.06**2 + 0.06**2) / 12.0
        extra_blocks.append(
            f"""    <link name="payload_offset_link">
      <pose>{px:.5f} {py:.5f} {pz:.5f} 0 0 0</pose>
      <inertial>
        <mass>{payload_mass_kg:.5f}</mass>
        <inertia>
          <ixx>{ixx:.8f}</ixx><ixy>0</ixy><ixz>0</ixz>
          <iyy>{ixx:.8f}</iyy><iyz>0</iyz>
          <izz>{ixx:.8f}</izz>
        </inertia>
      </inertial>
    </link>
    <joint name="payload_offset_joint" type="fixed">
      <parent>base_link</parent>
      <child>payload_offset_link</child>
    </joint>"""
        )

    if use_relay_plugin:
        wx, wy, wz = wind_enu
        step_log_str = str(relay_step_log) if relay_step_log else ""
        rx_log_str = str(relay_rx_log) if relay_rx_log else ""
        extra_blocks.append(
            f"""    <plugin filename="libMcnnMotorRelayPlugin.so"
      name="mcnn_cleanroom::McnnMotorRelayPlugin">
      <model_name>{model_instance_name}</model_name>
      <input_topic>/{model_instance_name}/command/motor_speed</input_topic>
      <output_topic>/{model_instance_name}/command/motor_speed_applied</output_topic>
      <hold_duration_ms>{hold_duration_ms:.3f}</hold_duration_ms>
      <log_path>{step_log_str}</log_path>
      <rx_log_path>{rx_log_str}</rx_log_path>
      <wind_vx>{wx:.6f}</wind_vx>
      <wind_vy>{wy:.6f}</wind_vy>
      <wind_vz>{wz:.6f}</wind_vz>
      <wind_drag_quad>{wind_drag_quad:.6f}</wind_drag_quad>
      <wind_drag_lin>{wind_drag_lin:.6f}</wind_drag_lin>
    </plugin>"""
        )

    if extra_blocks:
        sdf_text = sdf_text.replace("  </model>", "\n".join(extra_blocks) + "\n  </model>", 1)

    model_dir = out_models_root / model_dir_name
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.sdf").write_text(sdf_text, encoding="utf-8")
    (model_dir / "model.config").write_text(
        f"""<?xml version="1.0"?>
<model>
  <name>{model_dir_name}</name>
  <version>1.0</version>
  <sdf version="1.9">model.sdf</sdf>
  <description>Clean-room x500 variant for PX4 mc_nn_control handover experiments</description>
</model>
""",
        encoding="utf-8",
    )
    return model_dir
