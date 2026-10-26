"""P12 version of the real-source oracle with the new observation-only members.

Historical P10 stub generators stay frozen. Actual read, strict guard and target
method bytes are extracted by their existing reader; only the dependency stub
gains P12 fields/header and the observed-read latch.
"""
from pathlib import Path
import tempfile,subprocess
from p10a3 import source as old


class Oracle(old.Oracle):
    def __init__(self,repair=False,enabled=True):
        self.temp=tempfile.TemporaryDirectory(prefix='p12-native-oracle-');self.context=None
        code=old.cpp_source(old.snapshot())
        code=code.replace('#include "research/state/TargetProfile.hpp"',
            '#include "research/state/TargetProfile.hpp"\n#include "research/state/P12Controls.hpp"')
        code=code.replace(' int capture=0,rec_start=0;',
            ' bool _p12_enabled='+('true' if enabled else 'false')+',_p12_seen=false,_p12_repair='+('true' if repair else 'false')+';\n int capture=0,rec_start=0;')
        code=code.replace('  previous_active=next_active;',
            '  if(status.subscription_update_trajectory_setpoint && timestamp_last_trajectory_setpoint_set && timestamp_last_trajectory_setpoint==current_time) _p12_seen=true;\n  previous_active=next_active;')
        self.source=code;p=Path(self.temp.name);(p/'oracle.cpp').write_text(code)
        subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-I',str(old.ROOT),str(p/'oracle.cpp'),'-o',str(p/'oracle')],check=True,capture_output=True,text=True)
        self.process=subprocess.Popen([str(p/'oracle')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
