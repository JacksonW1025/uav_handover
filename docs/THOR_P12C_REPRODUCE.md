# P12c 离线复现与证据索引

本轮已停：准备10/12、正式0/24，剩余全部未启动，不自动续跑。下列仅离线命令；output必须从未存在，不能回写旧run。当前campaign有停止后guard，实际运行driver已单独归档。

```bash
# 用宿主允许的命名空间隔离复现，仍不启动SITL。
# 若工具sandbox内bwrap NETLINK_ROUTE不允许，在有权限的Thor宿主执行同命令；
# 不去掉未来日志隐藏或网络/PID隔离来凑通过。
uav_lab/.local/venv/bin/python tools/p12c_platform/workflow.py \
  --run /home/car/uav_handover/data/p12c-20261026-development/prep-safe_event-b1-on/run \
  --models /home/car/uav_handover/data/p12-cont-20261026-freeze/models \
  --output /tmp/p12c-offline-new

uav_lab/.local/venv/bin/python data/p12c-20261026-analysis-source/conditional_maps.py \
  /tmp/p12c-conditional-maps-new.json

uav_lab/.local/venv/bin/python data/p12c-20261026-analysis-source/event_geometry.py \
  data/p12c-20261026-development/prep-safe_event-b1-on \
  /tmp/p12c-event-table-new

uav_lab/.local/venv/bin/python -m pytest -q \
  tests/test_p12c_platform.py tests/test_p12c_offline_review.py tests/test_p12_score.py
```

已完成`data/p12c-20261026-reproduction-host/reproduction.json`：M2/M3/M4及四个既有消融的数组逐项一致，scorev2的models除compute_s完全一致。首次`...-reproduction/`在嵌套sandbox隔离准备阶段失败，完整失败/参数/log保留，宿主重试新目录成功；两者新增SITL均0。

核心证据位于`data/p12c-20261026-preparation/`：

| 文件/目录 | 作用 |
|---|---|
| `baseline.json`, `baseline-observer-source/` | 远端7e54974e、旧56启动/报告/冻结hash、旧实际源码归档 |
| `noninterference-spec.json`, `protocol.json`, `preflight-seal.json` | 首飞前尺度/分配/三门规范、516项hash |
| `source-closure.json`, build/apply/idempotence日志 | 零ULog/一次direct、控制源码反向一致、实际编译及幂等 |
| `runtime-snapshot.json` | PX4/插件/权重/构建普通文件副本hash，大文件在`data/p12c-20261026-runtime-local/` |
| `attempts.jsonl`, `queue-stop-receipt.json`, `host-stopped-check.json` | 10个唯一START及FINISH、主动案例间止启、无遗留仿真/运行时无漂移 |
| `acceptance-partial-v2.json`, `acceptance-supplement-v3.json` | 硬语义/动态/充分性分别报告，原尺度未放宽 |
| `completeness-final.json` | 必须的capture/resume见证修订；2个未启动项不是字段缺失 |
| `formal-stop.json`, `freeze-status.json` | 2准备+24正式未启动、正式未冻结，没有成功回执 |
| `post-stop-driver-guard/` | 实际driver普通副本、停止后仅防续跑版本差异，原seal不改 |
| 各tests日志 | 初始专项41/继承契约12、全项目255/8、最终专项27；旧失败不改断言掩盖 |

`data/p12c-20261026-delivery/`：

- `event-tables/manifest.json`及每条`event-states.json`，完整A/B/恢复/终点、L/D/W、神经动作执行/cache；`event-COM-geometry-and-W-provenance.json`附COM速度项、回调区间与物理时间UNKNOWN。
- `costs-and-process/costs-and-states.json`：完整任务和共同事件窗口、机械代理/跟踪、A后速度符号见证。没有新REPAIR臂。
- `dynamic-difference-v2/`：6.47°全过程定位，不能替换原验收指标；原CLI末尾打印key错误的v1输出/脚本/erratum也保留。
- `finite-execution-domain/`：独立SDF矩阵、旧5飞行全部servo-only矩阵核查及完整本地数组；联系旧全耦合solver审核，不把子集当全轨迹证书。
- `conditional-maps.json`：精确逆矩阵、全前缀L/D/W、恢复储备/反例，未验证前提明确。
- `domain-membership-v2/all-records.json`：16实际记录逐前缀、所有未启动项、首观测投影出界/真实成员UNKNOWN、不可观测字段；v1和source-only域修订也保留。
- `prediction-prefixes-v2/summary.json`、完整NPZ及`fulltopic-crossings.json`：冻结预测逐时/逐前缀、B前误差、组件/OR/事件窗分母；最初路径处理失败的v1目录保留，不冒充有效评分。
- `height-diagnostics-v2/old-F4-PH1-AB/`：物理步对齐的未来输入/阻力诊断，不是自主预测。先前host阶段近似版本仍保留。
- 原始与派生hash、实际版本、旧历史/模型不变及机器结论见最终审核清单。

所有原始ULog、telemetry/resources/sends、motor/direct bin、完整预测/诊断NPZ及实际大二进制留Thor且git-ignored，没有降采样。flight.ulg与rootfs/log可能硬链接，清单记录inode并去重分配空间；不删除历史、不断开链接以假报释放。

源patch独立导出`patches/p12c-20261026-minimal/`，旧patch不覆盖。源生成器只迁移声明观察代码；任何重新SITL验证需要另一个获授权身份/预算，不能以“复现”替换本轮或旧停批。理论/数值/模型版本、CI与工程验收分别解释，不把交付完整性审核PASS当放行。
