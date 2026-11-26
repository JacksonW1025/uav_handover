#!/usr/bin/env bash
set -euo pipefail

# Build the Crazyflie 2.1 native firmware + RLtools 1000 Hz lockstep harness.
# Set CF_DEPS_DIR to a directory containing the four pinned upstream checkouts:
#   crazyflie-firmware         @ d92f2b080fbcdd177d46b173cb826d2d3a879078
#   crazyflie-controller       @ 3e00e932eb74cceb92a859a4390a5742a7be27af
#   crazyflie-controller-blob  @ f546fa32ab57bc5fa37228e22a0a1fd53cc2fb08
#   rl-tools                   @ 6bb2fda96b765e5f1dce915da750022824b9eec5

H="$(cd "$(dirname "$0")" && pwd)"
DEPS="${CF_DEPS_DIR:-$H/.deps}"
FW="$DEPS/crazyflie-firmware"
CTRL="$DEPS/crazyflie-controller"
BLOB="$DEPS/crazyflie-controller-blob"
RLT="$DEPS/rl-tools/include"

for req in "$FW" "$CTRL" "$BLOB" "$RLT"; do
  if [[ ! -d "$req" ]]; then
    echo "Missing upstream checkout: $req" >&2
    echo "Set CF_DEPS_DIR or clone pinned upstream commits listed in ../manifest.json." >&2
    exit 1
  fi
done

BUILD_DIR="$H/build"
mkdir -p "$BUILD_DIR"

CFLAGS_COMMON=(
  -O3
  -fno-strict-aliasing
  -Wno-address-of-packed-member
  -Wno-absolute-value
  -Wno-unused-variable
  -Wno-unused-function
  -I"$H/stubs"
  -I"$H"
  -I"$CTRL"
  -I"$FW/src/modules/interface"
  -I"$FW/src/modules/interface/controller"
  -I"$FW/src/modules/interface/kalman_core"
  -I"$FW/src/modules/interface/outlierfilter"
  -I"$FW/src/hal/interface"
  -I"$FW/src/utils/interface"
  -I"$FW/src/utils/interface/lighthouse"
  -I"$FW/src/config"
  -I"$FW/src/drivers/interface"
  -I"$FW/src/platform/interface"
  -I"$RLT"
)

for src in \
  "$FW/src/utils/src/pid.c" \
  "$FW/src/utils/src/filter.c" \
  "$FW/src/utils/src/num.c" \
  "$FW/src/modules/src/power_distribution_quadrotor.c" \
  "$FW/src/modules/src/controller/attitude_pid_controller.c" \
  "$FW/src/modules/src/controller/position_controller_pid.c" \
  "$FW/src/modules/src/controller/controller_pid.c" \
  "$FW/src/modules/src/controller/controller_mellinger.c" \
  "$FW/src/modules/src/controller/position_controller_indi.c" \
  "$FW/src/modules/src/controller/controller_indi.c" \
  "$FW/src/modules/src/controller/controller_brescianini.c" \
  "$H/sim_hal.c"; do
  base=$(basename "$src" .c)
  clang -c "${CFLAGS_COMMON[@]}" "$src" -o "$BUILD_DIR/${base}.o"
done

clang -c "${CFLAGS_COMMON[@]}" -include "$H/stubs/cmsis_stub.h" "$CTRL/rl_tools_controller.c" -o "$BUILD_DIR/rl_tools_controller.o"
clang++ -std=c++17 -O3 -I"$H/stubs" -I"$H" -I"$BLOB" -I"$RLT" -c "$H/sim_executor.cpp" -o "$BUILD_DIR/sim_executor.o"
clang++ -std=c++17 -O3 "${CFLAGS_COMMON[@]}" "$H/verify_baseline.cpp" "$BUILD_DIR/"*.o -o "$BUILD_DIR/verify_baseline"
clang++ -std=c++17 -O3 "${CFLAGS_COMMON[@]}" "$H/run_crazyflie_campaign.cpp" "$BUILD_DIR/"*.o -o "$BUILD_DIR/run_crazyflie_campaign"
echo "Build succeeded: $BUILD_DIR/run_crazyflie_campaign"
