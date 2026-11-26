# MCNN SITL build and replay

The run-specific details are in [provenance.json](../provenance.json). Use an isolated PX4 checkout pinned to `5de8e5c1372fa3b21e3c42701a14ee9ec1b27248`. Check the gitlinks against [px4-submodules.txt](px4-submodules.txt). Apply [board-enable.patch](board-enable.patch), then build `px4_sitl_default` with TFLM. On Thor set both CMake Python executables to the PX4 lab Python 3.12 venv. If the existing ROS environment shadows Cyclone DDS, prepend the new build's `msg/idlc/lib` to `LD_LIBRARY_PATH` for the compilation.

Keep a copy of the official binary. To generate the paired evidence, apply [instrumentation.patch](instrumentation.patch) and rebuild. The C++ changes do not modify the controller law or safety checks. The motor plugin records consumer state and is the existing RAPTOR experiment's Gazebo Harmonic observer from the standalone Lab build, copied rather than relinked into PX4. Its source is included in [gazebo_motor_plugin](gazebo_motor_plugin); its build uses Gazebo sim8, transport13, and msgs10. In a new local run bundle, build the repository's existing [relay.cpp](../../t4/hover/relay.cpp) against `gz-transport13` and `gz-msgs10` as `sim-motor-relay` and place the observer library next to it. Use the stock x500 model in `models/x500`, applying [motor-sdf.patch](motor-sdf.patch) to its SDF copy. The patch selects the instrumented motor plugin and changes only the motor command topic; motor parameters and dynamics remain unchanged. The runner resolves `models`, the relay and the plugin relative to its own location. Supply the local ROS Jazzy `px4_msgs` Python and library paths and the local MicroXRCEAgent library path; the runner expects the XRCE Agent in the same Lab layout as on Thor.

```bash
python3 hover-calibration.py "$PX4" "$OUTPUT/hover" 1.05
python3 paired-t1-t2.py "$PX4" "$OUTPUT/t1-classical" t1_c
python3 paired-t1-t2.py "$PX4" "$OUTPUT/t1-neural" t1_n
python3 paired-t1-t2.py "$PX4" "$OUTPUT/t2-classical" t2_c
python3 paired-t1-t2.py "$PX4" "$OUTPUT/t2-neural" t2_n
python3 paired-t3.py "$PX4" "$OUTPUT/t3-stale" t3_stale
python3 paired-t3.py "$PX4" "$OUTPUT/t3-fresh" t3_fresh
python3 paired-t4.py "$PX4" "$OUTPUT/t4-direct" t4_release
python3 paired-t4.py "$PX4" "$OUTPUT/t4-hold" t4_hold
```

Use disjoint destinations, run one arm at a time and keep simulator isolation. For offline recomputation on any checkout use [verify.py](../verify.py); only raw re-extraction needs Thor paths and PyULog.
