# P14 运动地图补充复现

全离线，**不要调用 `tools/experiment`、任何batch或飞行启动器**。工作目录 `/home/car/uav_handover`，Python `uav_lab/.local/venv/bin/python`，`OPENBLAS_NUM_THREADS=1`；绘图可设 `MPLCONFIGDIR=/tmp/p14-motion-mpl`。每个输出目录必须全新，不覆盖历史。

## 输入和输出

* 计算前规范：`config/p14-motion-offline.json`、`data/p14-motion-20261027/protocol-seal.json`。原规范/计划不改，后续确定语义错误在报告和独立seal记录。
* 四条原始ULog/body/rotor/sync/history路径和hash：`inputs-v3/index.json`、`old-input-hashes.json`。本机P13数据未上传或删除。
* task0过去输入：`inputs-v3/<id>/task-input-nav.json`；A前条件输入：同目录`edge-input.json`。不要用旧`task-input.json`替代正确导航版本。
* 最终点预测：`point-v2`；全量四例新评分/首次偏离/事件窗：`analysis-v2`；有限未来缓存替换：`cache-diagnostics-v1/v2/v3-edge`，绝不可计为自主。
* 最终管束：`tubes-final-v2/summary.json`。前两项是`final-v1`已完成结果的明确引用；驱动先核对core/tube/algebra hash再复用。未重复已完成离线项冒充新实验。
* 地图/图/机器结论：`delivery-v5/map-edge.json`、`edge-regions/`、`machine-conclusion.json`；三图在`docs/figures/p14-motion/`。实际NDArray由local hash清单绑定，沿用已有p14 NPZ忽略规则。

## 计算

以下都是离线计算，示例路径须换成尚不存在的新目录：

```bash
OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python tools/p14_motion/prepare.py /tmp/p14-motion-input-repro
OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python tools/p14_motion/run_points.py /tmp/p14-motion-points-repro
OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python tools/p14_motion/reproduce.py /tmp/p14-motion-independent-repro
OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python tools/p14_motion/final_tubes.py /tmp/p14-motion-tubes-repro
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/p14-motion-mpl uav_lab/.local/venv/bin/python tools/p14_motion/assemble.py /tmp/p14-motion-delivery-repro
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/p14-motion-mpl uav_lab/.local/venv/bin/python -m pytest -q tests/test_p14_motion.py tests/test_p14.py tests/test_p13.py tests/test_p12_score.py
```

批驱动读取固定canonical补充输入/结果，输出新目录。`run_points`在bwrap内隐藏data/export并隔离网络/PID；若宿主禁止NETLINK_ROUTE，保留失败回执，由获授权宿主环境执行同一离线命令，不能为省事取消数据隔离。`reproduce`核对一例四变体数组完全相同和16调用tube逐字段一致。重算score可用`p12.score.score`指向新预测/原packed/measured并输出新目录；`analyze.py`固定读取本轮最终point-v2作报告再生。

旧结构尝试必须使用各自`source-versions/<attempt>/`或`pre-group-source/`中的hash绑定源码和原inputs-v2，不能拿当前tube函数重算后覆盖旧结果；当前模型要求task0 H0/D0字段。失败/工具错误见报告末节和全部`.log`。

## 数学与数据声明

点模型只用过去初态/计划；实际未来命令、raw gyro/bias、姿态/LP/cache注入分目录，仅为诊断。A前条件初始化是地图边输入，不是task0盲预测。1cm全域与千分之一微小域均是指定场景，没有声称覆盖未观测真实EKF/队列。一个名义时序分支不代表所有合法时钟；连续采样间安全和独立区间libm验证仍缺。

源核单步/给命令开放重放、连续神经重放、条件集合包含、旧飞行科学结论和本机单元测试是不同证据。发布时远端SHA和真实CI另存本地回执，不用本地pytest代替CI。
