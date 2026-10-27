# P14R离线复现与证据入口

工作根目录 `/home/car/uav_handover`，基线 `69ca54ff3029df671de740cf0a4ab4495b03b44a`；最终源提交见发布回执。`data/p14r-20261027/delivery-v3/`是最终机器结论、地图、成本及原始/完整数组hash入口。旧delivery-v1/v2与全部失败保留。

以下命令全部离线，不调用SITL启动器，不消耗或恢复任何飞行预算。输出目录必须不存在；不要对旧结果原地重跑。Python使用Lab已有venv，不下载/迁移Lab。

```bash
export OPENBLAS_NUM_THREADS=1
uav_lab/.local/venv/bin/python -m pytest -q tests/test_p14r.py tests/test_p14_motion.py tests/test_p14.py tests/test_p13.py tests/test_p12.py tests/test_p12_score.py tests/test_p12b.py tests/test_p12c_platform.py
uav_lab/.local/venv/bin/python tools/p14r/reproduce.py quick /tmp/p14r-repeat-new
uav_lab/.local/venv/bin/python tools/p14r/initial_stage_audit.py /tmp/p14r-initial-new
uav_lab/.local/venv/bin/python tools/p14r/height_constraint.py /tmp/p14r-height-new
```

原始文件在六个 `runs/<id>/run/`，包含ULog、sends、物理/执行/OP/gyro二进制，所有失败和有效前缀保留。普通运行副本在pre-change-runtime/runtime-v1/runtime-v2，不能用CLI链接代替历史二进制。二进制和NPZ本机保存，Git收小证据/源/图；缺原始文件时必须报告不可复现，不能用摘要替代。

## 分层链与输入来源

- `source-replay-d01..06-v1/result.json`：真实C++ OP，实际未来IMU/融合输入只用于已知输入诊断；55秒以后31字段逐位一致，d01隔离不变。
- `source-inputs-v3/d02..04`、`source-inputs-v4/d05..06`：过去初态/参数。h/history为同次调用post，生产者前缀截至Run开始；`initial-stage-v1`证明全部早于首次预测调用，但不是同步完整快照。
- `registered-points-v1`：五条记录×旧互补及8源时序词；其`isolation.json`保存bwrap命令，data/export隐藏且断网。`run_registered.py`可复制全部输入/封存核心并独立离线重算（约115秒历史实测），输出必须新建。
- `registered-score-v1`及`registered-errors-v1`：冻结三值评分、LP缓存高度、首偏离、0.5/2秒/完整窗及裁剪轴。未来实测仅评分，d05高度实际UNKNOWN保留。
- `A-input-contrasts-v3`及`closed-diagnostics-v2`：未来实测物理、命令、融合、缓存与读取词替换，仅诊断；不能混进自主成绩或认为其误差改进可相加。

真实OP离线库从已有Lab源码构建：

```bash
uav_lab/.local/venv/bin/python tools/p14r/build_offline.py /tmp/p14r-op-build-new
```

`offline-build-v2/manifest.json`保存实际源hash、命令、flags和普通库副本；当前模型默认读取该已封存副本。新构建库若hash/行为不同，应作为新的分析版本核验。经典核编译命令和结果在`classic-kernel-v5/build.json`、`result.json`，只执行Position/Attitude/Rate源码，不启用uORB或飞行。

## 联合集合、组合与理论

`B-joint-hulls-v2`含全部66实测成员见证；`B-bundle-plan-v2`先固定每族12，共24点；点集不是连续覆盖。`C-joint-v6`是双publisher-clock fiber×4分段的最终初态并集。每job使用`run_tubes.py child JOB NEWDIR`，保留job、源hash、资源和失败。

全无压缩对照耗费较大，**只按需要显式选择**。以下离线命令有CPU/地址空间上限，保留流式metric前缀；操作系统因上限终止时不能删除该目录或把最后一行当完整后继。

```bash
uav_lab/.local/venv/bin/python tools/p14r/reproduce.py no-compression /tmp/p14r-nocompress-new --cpu-seconds 900
uav_lab/.local/venv/bin/python tools/p14r/reproduce.py continue /tmp/p14r-continue-new --cpu-seconds 1800
```

第二条读取已保存的`C-no-compression-full-v1/regions/resume.{json,npz}`，在该后继之后追加预定B，携带数值G、D/history和固定时序。不是通用任意根/时钟恢复器；新代码明确拒绝未经验证的配置。原900 CPU秒进程终止137，信号源未独立证实；8调用数值恢复误差0；最终续算141调用失精度、197调用失域。保存的原早期倾角行不全，不能补称全程前缀安全。浮点/libm/外包数值认证未闭合。

`compose.py NEWDIR`实际运行四事件点地图并对每个序列化后继重新续算，携带完整OP/gyro/slot/history/filter和COM/LP D；`compose-v2`与不中断最大差3.6e-15。`storage-v2`为869维解析一阶链的16调用时变因子及非线性余项义务。`height-constraint-v1`为源码参数推得的非空条件全前缀COM余量关系。它们均不构成真实EKF/SERVO未来整程安全证明，A4仍未排除。

## 验证、成本与发布

最终89项Python测试、80ms重复传播、8调用集合恢复、真实PX4 build-v8、注入幂等、宿主容量和生命周期分别留证。失败构建/旧测试/旧评分未删除。`delivery-v3/cost.json`列全部能计量组件、约596秒新增物理进程、约7833秒历史P13依赖、端到端建模和未计量项。并行墙时不相加成独占CPU；净测试成本收益未建立。

GitHub CI与本地测试分开查询，未配置/无记录不写绿灯。最终发布回执保存commit、远端回读、CI API原始状态。任何后续新采集均需独立授权；本轮余2次不使用。
