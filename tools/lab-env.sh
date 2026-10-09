#!/usr/bin/env bash
# 用法：source uav_lab/env.sh [classic|raptor]
# 仅设置当前 shell 的环境；不构建、不启动服务。
_handover_variant="${1:-classic}"
case "$_handover_variant" in
  classic|raptor) ;;
  *) printf 'Usage: source uav_lab/env.sh [classic|raptor]\n' >&2; return 2 ;;
esac
_handover_restore_nounset=0
if [[ $- == *u* ]]; then _handover_restore_nounset=1; set +u; fi
export HANDOVER_LAB_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../uav_lab" && pwd)"
export HANDOVER_VARIANT="$_handover_variant"
export PX4_SOURCE_DIR="$HANDOVER_LAB_ROOT/.local/checkouts/px4-$_handover_variant"
export PX4_SNAPSHOT_DIR="$HANDOVER_LAB_ROOT/sources/px4-$_handover_variant"
export PX4_RUNTIME_DIR="$HANDOVER_LAB_ROOT/.local/runtime/px4-$_handover_variant"
_handover_target=px4_sitl_default
if [[ "$_handover_variant" == raptor ]]; then _handover_target=px4_sitl_raptor; fi
_handover_build="$PX4_SOURCE_DIR/build/$_handover_target"
if [[ -x "$_handover_build/bin/px4" ]]; then export PX4_RUNTIME_DIR="$_handover_build"; fi
export PX4_MSGS_DIR="$HANDOVER_LAB_ROOT/sources/px4-msgs-$_handover_variant"
export XRCE_AGENT_SOURCE_DIR="$HANDOVER_LAB_ROOT/.local/checkouts/xrce-agent"
export RAPTOR_POLICY_DIR="$HANDOVER_LAB_ROOT/sources/px4-raptor/src/modules/mc_raptor/blob"
# 隔离继承的 overlay/Conda/其他实验仓库环境；系统 ROS/CUDA 继续使用本机安装。
unset AMENT_PREFIX_PATH COLCON_PREFIX_PATH CMAKE_PREFIX_PATH PYTHONPATH
unset ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION RMW_IMPLEMENTATION
unset CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_PROMPT_MODIFIER CONDA_SHLVL
unset VIRTUAL_ENV PYTHONHOME PYTHONUSERBASE
export PYTHONNOUSERSITE=1
unset GZ_CONFIG_PATH GZ_SIM_RESOURCE_PATH GZ_SIM_SYSTEM_PLUGIN_PATH GZ_SIM_SERVER_CONFIG_PATH
unset IGN_GAZEBO_RESOURCE_PATH IGN_GAZEBO_SYSTEM_PLUGIN_PATH
export PATH="$HANDOVER_LAB_ROOT/scripts:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/usr/local/cuda/bin"
_handover_plugins="$PX4_RUNTIME_DIR/plugins"
if [[ -d "$PX4_RUNTIME_DIR/src/modules/simulation/gz_plugins" ]]; then
  _handover_plugins="$PX4_RUNTIME_DIR/src/modules/simulation/gz_plugins:$PX4_RUNTIME_DIR/src/modules/simulation/gz_plugins/optical_flow"
fi
export LD_LIBRARY_PATH="$_handover_plugins:$HANDOVER_LAB_ROOT/.local/runtime/xrce-agent/lib"
if [[ -r /opt/ros/jazzy/setup.bash ]]; then
  source /opt/ros/jazzy/setup.bash
fi
_handover_overlay="$HANDOVER_LAB_ROOT/workspaces/$_handover_variant/install/setup.bash"
if [[ -r "$_handover_overlay" ]]; then source "$_handover_overlay"; fi
if [[ -x "$HANDOVER_LAB_ROOT/.local/venv/bin/python" ]]; then
  export VIRTUAL_ENV="$HANDOVER_LAB_ROOT/.local/venv"
  export PATH="$VIRTUAL_ENV/bin:$PATH"
fi
export GZ_SIM_RESOURCE_PATH="$PX4_SNAPSHOT_DIR/Tools/simulation/gz/models:$PX4_SNAPSHOT_DIR/Tools/simulation/gz/worlds:/opt/ros/jazzy/share"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$_handover_plugins"
export GZ_SIM_SERVER_CONFIG_PATH="$PX4_SNAPSHOT_DIR/Tools/simulation/gz/server.config"
if [[ -r /usr/share/glvnd/egl_vendor.d/10_nvidia.json ]]; then
  export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
fi
unset _handover_variant _handover_overlay _handover_target _handover_build _handover_plugins
if [[ "$_handover_restore_nounset" == 1 ]]; then
  unset _handover_restore_nounset
  set -u
else
  unset _handover_restore_nounset
fi
