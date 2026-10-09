#!/usr/bin/env python3
"""Summarize the actual final commands and new SITL evidence into TEST-01..25."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/environment-20261009'
def read(path):
 p=ROOT/path
 return json.loads(p.read_text()) if p.exists() else {}
def main():
 tests=[]
 observed=read('data/environment-20261009/final-flight-exits.json').get('runs',{})
 def command(name):return read('data/environment-20261009/final-commands/'+name+'.json')
 def cmdtest(number,title,names):
  records=[command(n) for n in names];passed=all(r.get('exit_code')==0 for r in records)
  tests.append({'id':f'TEST-{number:02d}','title':title,'status':'PASS' if passed else 'NOT_RUN' if any(not r for r in records) else 'FAIL','commands':records,'reason':None if passed else 'See command output / absent evidence'})
 def run_test(number,title,runs,check=None):
  records=[]
  for run in runs:
   val=read(f'data/{run}/validation.json');meta=read(f'data/{run}/metadata.json');metrics=read(f'data/{run}/metrics.json')
   code=observed.get(run,{}).get('exit_code')
   passed=code==0 and val.get('status')=='PASS' and (check is None or check(val,meta,metrics))
   records.append({'run':run,'status':'PASS' if passed else 'NOT_RUN' if not val or code is None else 'FAIL','exit_code':code,
     'command':['tools/experiment',meta.get('experiment_type','unknown'),'--output',f'data/{run}'],
     'evidence':[f'data/{run}/validation.json',f'data/{run}/metrics.json',f'data/{run}/flight.ulg',f'data/{run}/events.jsonl',f'data/{run}/logs/commands.log'],
     'reason':val.get('reason')})
  passed=all(r['status']=='PASS' for r in records)
  tests.append({'id':f'TEST-{number:02d}','title':title,'status':'PASS' if passed else 'NOT_RUN' if any(r['status']=='NOT_RUN' for r in records) else 'FAIL','runs':records,'reason':None if passed else 'See per-run validation and metrics'})
 classic='final-classic-relative-03';neural='verified-raptor_hover';handover=neural
 cmdtest(1,'Lab 环境加载与路径隔离',['final-health-classic','final-health-raptor'])
 cmdtest(2,'Python 关键依赖、ABI 与 pip check',['final-health-classic','final-health-raptor'])
 cmdtest(3,'classic ROS overlay / Python / C++ pubsub',['final-ros-classic'])
 cmdtest(4,'raptor ROS overlay / Python / C++ 接口',['final-ros-raptor'])
 run_test(5,'经典 PX4 SITL 正常启动',[classic])
 run_test(6,'Gazebo x500、传感器和电机插件实际工作',[classic,neural])
 run_test(7,'经典控制短时悬停',[classic])
 run_test(8,'实际 PX4↔ROS 双向通信、Agent 重连',[classic,neural],lambda v,m,r:v['checks'].get('bidirectional_dds')=='PASS' and v['checks'].get('dds_reconnection')=='PASS')
 run_test(9,'生成并解析本轮新 ULog',[classic,neural])
 cmdtest(10,'真正启用 MC_RAPTOR / RL Tools 的构建',['final-build-raptor'])
 run_test(11,'RAPTOR 模块启动与动态模式注册',[neural])
 run_test(12,'冻结策略加载、自测、有限推理与时序',[neural],lambda v,m,r:r.get('inference_timing_status')=='PASS')
 run_test(13,'机体/电机映射在当前冻结平台验证',[neural],lambda v,m,r:all(x['status']=='PASS' for x in r.get('ownership_windows',{}).values()))
 tests[-1]['scope']='SDF/编号/坐标源码审查与 x500 实际短时控制；训练完整动力学元数据缺失，不证明与训练机体等同。详见 docs/THOR_PLATFORM_MAPPING.md。'
 run_test(14,'神经独立控制窗口稳定悬停',[neural])
 run_test(15,'C→N 模式、实际执行器归属和悬停',[neural])
 run_test(16,'N→C 实际恢复经典执行器输出',[neural])
 run_test(17,'完整 C→N→C',[neural,'verified-repeated_handover'])
 run_test(18,'三类状态 READ / RESET / SNAPSHOT / HOLD / RESTORE',['verified-state_reset','verified-state_hold','verified-state_restore'],lambda v,m,r:v['checks'].get('state_contract')=='PASS' and r.get('state_values_validation',{}).get('status')=='PASS')
 tests[-1]['unit_test']=command('state-unit')
 if tests[-1]['unit_test'].get('exit_code')!=0:tests[-1]['status']='FAIL'
 run_test(19,'受控注入与非法输入/活动写入拒绝',['verified-state_injection'],lambda v,m,r:r.get('state_values_validation',{}).get('status')=='PASS')
 run_test(20,'执行器归属、交接与状态事件日志完整',[neural,'verified-state_restore'],lambda v,m,r:r.get('state_log_validation',{}).get('status')=='PASS')
 tests[-1]['scope']='关键飞控数据连续记录；GRU/速度积分器及参考按操作与交接边界事件记录。'
 run_test(21,'自动运行、降落、结束与数据保存',[classic,neural,'verified-state_restore'])
 run_test(22,'日志解析、指标和可视化',[classic,neural])
 run_test(23,'连续三轮基础实验与三次交接稳定性',['final-classic-relative-01','final-classic-relative-02','final-classic-relative-03','verified-repeated_handover'])
 tests[-1]['cleanup_audit']=command('process-cleanup')
 if tests[-1]['cleanup_audit'].get('exit_code')!=0:tests[-1]['status']='FAIL'
 cmdtest(24,'活动路径不依赖旧仓库',['final-health-classic','final-health-raptor'])
 cmdtest(25,'Git 忽略整个 Lab，保留实验源码和原始证据',['git-boundaries'])
 all_runs=[]
 for p in sorted((ROOT/'data').glob('*/validation.json')):
  d=json.loads(p.read_text());all_runs.append({'run':p.parent.name,'status':d.get('status'),'reason':d.get('reason')})
 result={'generated_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),'experiment_status':'环境检查完成',
         'status':'PASS' if all(t['status']=='PASS' for t in tests) else 'INCOMPLETE','tests':tests,'all_runs_including_failed_attempts':all_runs,
         'limits':['仅本机冻结配置短时 headless SITL；不包括真实飞行或长期统计显著性。','训练动力学元数据不完整；native 约125Hz与训练100Hz差异保留并记录。','完整 FlightTask/EKF/滤波器/Lissajous 状态快照未提供；当前状态参考实验限定 MC_RAPTOR_INTREF=0。','历史显式AMSL起飞路径间歇失败；当前入口用上游默认相对起飞语义，失败证据保留。']}
 (OUT/'acceptance.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 lines=['| 测试 | 内容 | 结果 | 证据 |','|---|---|---|---|']
 for t in tests:
  evidence=t.get('runs',[{}])[0].get('evidence',[])
  path=evidence[0] if evidence else t.get('commands',[{}])[0].get('log','')
  lines.append(f'| {t["id"]} | {t["title"]} | {t["status"]} | [{Path(path).name}](../{path}) |')
 (ROOT/'docs/THOR_ACCEPTANCE_MATRIX.md').write_text('# 最终验收矩阵\n\n机器可读命令、退出码和逐轮证据见 [acceptance.json](../data/environment-20261009/acceptance.json)。PASS 限于测试声明范围。\n\n'+'\n'.join(lines)+'\n')
 print(result['status']);print({s:sum(t['status']==s for t in tests) for s in ['PASS','FAIL','BLOCKED','NOT_RUN']})
 return 0 if result['status']=='PASS' else 1
if __name__=='__main__':sys.exit(main())
