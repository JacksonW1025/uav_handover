import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import numpy as np
from output_chain import ROW,neural_intervals,summarize,counter_delta,read_trace

def rows(sim,new,received):
    r=np.zeros(len(sim),ROW);r['sim_us']=sim;r['new_sample_us']=new;r['received']=received
    applied=0
    for i,s in enumerate(new):
        if s:applied=s;r['flags'][i]=1
        r['applied_sample_us'][i]=applied
    return r

def test_hold_overwrite_and_age():
    sim=np.arange(0,40000,4000)
    new=np.array([0,0,4000,0,12000,16000,0,0,0,32000])
    rec=np.array([0,0,1,0,2,1,0,0,0,1])
    s=summarize({0:rows(sim,new,rec)},[(0,40000)])['motors']['0']['neural']
    assert s['steps_with_new_command']==4 and s['hold_steps']==6
    assert s['commands_overwritten_in_gazebo']==1
    # held 16000 sample ages to 16 ms at sim 32000: three consecutive steps over 4 ms
    assert s['applied_age_us']['max']==16000 and s['longest_over_target_steps']==3

def test_intervals_and_counter_bracketing():
    tr=[{'px4_us':10,'from':2,'to':1},{'px4_us':20,'from':1,'to':2},{'px4_us':30,'from':2,'to':1}]
    assert neural_intervals(tr,50)==[(10,20),(30,50)]
    t=np.array([0,9,15,21,29,40,60]);total=np.array([0,1,3,3,4,6,9])
    assert counter_delta(t,total,[(10,20)])==2
    assert counter_delta(t,total,[(10,20),(30,50)])==2+5
    assert counter_delta(t,total,[(10,70)]) is None

def test_trace_header_and_partial_tail(tmp_path):
    r=rows(np.array([0,4000]),np.array([0,4000]),np.array([0,1]))
    p=tmp_path/'motor-2.bin'
    p.write_bytes(b'HOMTRC01'+np.array([ROW.itemsize,2],'<u4').tobytes()+r.tobytes()+b'\x00'*5)
    motor,back,tail=read_trace(p)
    assert motor==2 and len(back)==2 and tail==5 and back['applied_sample_us'][1]==4000
