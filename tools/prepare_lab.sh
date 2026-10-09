#!/usr/bin/env bash
# Uses the existing Lab; never replaces or downloads project resources.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
lab_root="$project_root/uav_lab"
for resource in .local/checkouts/px4-classic .local/checkouts/px4-raptor sources/px4-msgs-classic sources/px4-msgs-raptor sources/px4-ros2-interface; do
  test -d "$lab_root/$resource" || { printf 'Missing existing Lab resource: %s\n' "$resource" >&2; exit 1; }
done
if [[ ! -x "$lab_root/.local/venv/bin/python" ]]; then
  /usr/bin/python3 -m venv --system-site-packages "$lab_root/.local/venv"
fi
"$lab_root/.local/venv/bin/python" -m pip install -r requirements-research.txt
# Keep the Lab's public entrypoint a wrapper around the tracked implementation.
cat > "$lab_root/env.sh" <<'EOF'
#!/usr/bin/env bash
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)/tools/lab-env.sh" "${1:-classic}"
EOF
cat > "$lab_root/scripts/check_lab.py" <<'EOF'
#!/usr/bin/env python3
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[2]/'tools/check_lab.py'),run_name='__main__')
EOF
for variant in classic raptor; do
  (
    source tools/lab-env.sh "$variant"
    cd "$lab_root/workspaces/$variant"
    python -m colcon build --executor sequential --cmake-args -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE="$VIRTUAL_ENV/bin/python"
  )
done
# Applying the narrow research edits preserves the existing RouteObservability edits.
python_bin="$lab_root/.local/venv/bin/python"
"$python_bin" tools/apply_research.py
for variant in classic raptor; do
  (
    source tools/lab-env.sh "$variant"
    target=px4_sitl_default
    if [[ "$variant" == raptor ]]; then target=px4_sitl_raptor; fi
    make -C "$PX4_SOURCE_DIR" -j8 "$target"
  )
done
tools/experiment health --output "data/health-$(date +%Y%m%dT%H%M%S)"
