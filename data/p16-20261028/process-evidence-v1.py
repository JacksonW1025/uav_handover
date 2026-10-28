"""Independent ledger-to-actual-process and actual Gazebo seed audit; no launch."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,'tools')
from p16.common import B,write,now
ledger=[json.loads(l) for l in (B/'attempts.jsonl').read_text().splitlines()];ss=[x for x in ledger if x['event']=='START_INTENT'];rows=[]
for s in ss:
 t=B/'runs'/s['id'];row=json.load(open(t/'row.json'));ev=[json.loads(l) for l in (t/'run/events.jsonl').read_text().splitlines()];start={name:[e for e in ev if e['event']=='process_started' and e['name']==name] for name in ['px4','gazebo']};ends={name:[e for e in ev if e['event']=='process_stopped' and e['name']==name] for name in start};assert all(len(x)==1 for x in start.values());assert all(len(x)==1 for x in ends.values());cmd=start['gazebo'][0]['command'];seed=cmd[cmd.index('--seed')+1];assert int(seed)==row['seed'];assert ends['px4'][0]['exit_code']==0
 rows.append(dict(id=s['id'],stage=s['stage'],seed=row['seed'],real_gazebo_seed_argument=int(seed),PX4_starts=1,Gazebo_starts=1,PX4_exit=ends['px4'][0]['exit_code'],Gazebo_exit=ends['gazebo'][0]['exit_code'],PX4_PID=start['px4'][0]['pid'],Gazebo_PID=start['gazebo'][0]['pid'],PX4_stop_ns=ends['px4'][0]['monotonic_ns'],Gazebo_stop_ns=ends['gazebo'][0]['monotonic_ns']))
write(B/'process-evidence-v1.json',dict(time=now(),rows=rows,actual_PX4_starts=sum(x['PX4_starts'] for x in rows),actual_Gazebo_starts=sum(x['Gazebo_starts'] for x in rows),all_gazebo_seed_arguments_verified=True,seed_scope='actualGazebo --seed verified, no universalPX4/allrandomstate reproducibility claim',new_START=0))
print('ACTUAL_PROCESS_STARTS',len(rows))
