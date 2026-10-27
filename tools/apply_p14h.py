"""Independent passive P14H hook; maintained source, unique idempotent marker."""
from pathlib import Path
import shutil
R=Path(__file__).resolve().parents[1];P=R/'uav_lab/.local/checkouts/px4-raptor'
def apply():
 src=R/'research/state/P14HSnapshot.hpp';dst=P/'src/lib/handover_research/P14HSnapshot.hpp';shutil.copyfile(src,dst)
 p=P/'src/modules/ekf2/EKF2.cpp';s=p.read_text();inc='#ifdef __PX4_POSIX\n#include <lib/handover_research/P14HSnapshot.hpp>\n#endif\n'
 if 'P14HSnapshot.hpp' not in s:
  anchor='#include "EKF2.hpp"';assert anchor in s;s=s.replace(anchor,anchor+'\n'+inc,1)
 marker='// P14H_POST_EKF_SNAPSHOT'
 if marker not in s:
  anchor='\t\tif (_ekf.update()) {';assert anchor in s;s=s.replace(anchor,anchor+'\n#ifdef __PX4_POSIX\n            '+marker+'\n            p14h::snapshot(_ekf.state().vector(),_ekf.covariances(),imu_sample_new,hrt_absolute_time(),_ekf.time_delayed_us(),_ekf.control_status().value);\n#endif',1)
 p.write_text(s);assert s.count(marker)==1 and s.count('P14HSnapshot.hpp')==1
if __name__=='__main__':apply()
