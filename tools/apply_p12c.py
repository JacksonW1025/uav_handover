#!/usr/bin/env python3
"""P12 continuation sample-window overlay, after P12. Original insertion stays whole."""
from apply_p12 import PX,edit

def apply():
 p=PX/'src/modules/mc_raptor/module.yaml'
 if 'MC_RAPTOR_P12MS:' not in p.read_text():
  with p.open('a') as f:f.write('''
    - group: Handover P12 Continuation
      definitions:
        MC_RAPTOR_P12MS:
            description:
                short: Repair sample ms gate -1 legacy 0 inhibited positive threshold
            type: int32
            default: -1
            min: -1
            max: 2000000000
''')
 old='    if (_p12_enabled) mode=handover_research::p12_capture_mode(_p12_repair,activation,active,_p12_seen);'
 edit('src/modules/mc_raptor/mc_raptor.cpp',old,old+'''
    // P12_CONT_REPAIR_WINDOW: preserve the complete legacy overlay prefix.
    if (_p12_enabled) {
        static const param_t window_param=param_find("MC_RAPTOR_P12MS");
        int32_t not_before_ms=-1;param_get(window_param,&not_before_ms);
        if (!handover_research::p12_repair_window_open(_vehicle_angular_velocity.timestamp_sample,not_before_ms)) mode=0;
    }''')
if __name__=='__main__':apply()
