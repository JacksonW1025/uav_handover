# P14 全离线复现

仓库`/home/car/uav_handover`；基线4e18dbcce39edd23c07347526ab0de4818fccb24。全部新输出必须使用新目录，不向旧run/冻结/评分目录写入。**不调用experiment、campaign、PX4、Gazebo或任何SITL启动器。** 本轮新飞行0。

## 输入与版本

- `config/p14-offline.json`和`data/p14-20261027/protocol-seal.json`在计算前固定尺度/窗口/范围。
- `candidate-v1/candidate-seal.json`绑定M14/G代码、原系数/权重及78份过去输入；无参数拟合。
- 原始数据在`data/p13-20261026-{development,formal}/<id>/run`，正式53按`analysis-pointer-v2.json`选择analysis-v2，开发早期预测按`common.records()`解析独立目录。
- P13过去输入含直接COM p/v、physical q/omega、source sample和host年龄；measurement.npz从不复制进预测子进程。
- `audit-v1/input-hashes.json`登记78条body/rotor/ULog/旧预测/观测/history和关键历史文档；P11另有69个ULog/score的独立链。原始matrix、普通实际二进制及旧缺字段范围见P13/P12复现文档，旧CLI链接不是历史二进制。
- 完整NPZ统一本机保存并由最终manifest记hash；Git只收小型证据/源码/图。不要删除、降采样或以格式转换释放旧原件。

## 实际计算入口

以下均为离线，输出参数换成从未存在的路径。原脚本会拒绝覆盖。标准Python用Lab venv；bwrap需要宿主命名空间权限，失败保留目录/日志，不放开未来输入来求成功。

```bash
uav_lab/.local/venv/bin/python tools/p14/audit.py data/p14-repro-audit-NEW
uav_lab/.local/venv/bin/python tools/p14/legacy.py data/p14-repro-legacy-NEW
uav_lab/.local/venv/bin/python tools/p14/run_predictions.py data/p14-repro-candidate-NEW
uav_lab/.local/venv/bin/python tools/p14/reproduce.py \
  --case p13-F4-b1-A --output data/p14-repro-one-NEW
OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python tools/p14/layers.py data/p14-repro-layers-NEW
OPENBLAS_NUM_THREADS=1 uav_lab/.local/venv/bin/python tools/p14/theory.py data/p14-repro-theory-NEW
uav_lab/.local/venv/bin/python tools/p14/height.py data/p14-repro-height-NEW.json
uav_lab/.local/venv/bin/python tools/p14/extension.py data/p14-repro-extension-NEW.json
uav_lab/.local/venv/bin/python -m pytest -q tests/test_p14.py tests/test_p12_score.py
```

`evaluate.py <新目录>`读取canonical `data/p14-20261027/candidate-v1/predictions`，全量重评分及过程分析；`details.py <新目录>`读同一候选补充首次高度越界/恢复/物理B前状态。它们不重新拟合或飞行；若比较另一个复现输出，应显式修改其候选根路径并记录新分析版本，不替换canonical。

P12b求解器复核原命令：

```bash
uav_lab/.local/venv/bin/python tools/p12b/solver.py \
  data/p12b-20261026-development-v2/prep05-F4-ph1-AB-on-direct-v2/run/gz-motor/dart-solver-2988137.bin \
  --output data/p14-repro-solver-NEW
```

`tools/p10a4/contract_counterexample.py`旧入口当前拒绝A3_SOURCE_DEPENDENCY_CHANGED，失败日志保留。不要禁用旧身份检查。`tools/p14/legacy.py`独立核对绑定的归档数学输入、重算22步有理数下界并与原反例精确比较，范围不包括从新源码重生成旧native oracle。

## 交付索引

|路径（均在data/p14-20261027）|内容|
|---|---|
|`evidence-v1/`|逐主张证据表、源码系数版本对照、支持与反证|
|`audit-v1/`|78条真实测量点/时间/传感字段及原始hash，P11的69条原始评分链|
|`legacy-v1/`|run70平台、formal27缺pre-read、A4独立有理复核|
|`candidate-v1/`|计算前封存、78份G/M14输出、隔离命令与wall时间|
|`evaluation-v1/`|78条旧模型精确重评分、新评分、阶段/前缀/B前误差、.5/2s分母|
|`details-v1/`|高度首跨括号、P0联合恢复、物理COM B前L/D/W误差|
|`layers-v1/`|78条已知输入target/NN/history；四例源核和B估计诊断、有限替换顺序|
|`legacy-solver-recheck/`|独立完整旧solver数值关系，η不用e_j反算|
|`theory-v1/`|原NED L符号错误输出，完整保留|
|`theory-v2/`|相关集合修订、条件SERVO预算、精确恢复、源扩展反例与A4义务|
|`reproduction-v1/`|代表案例隔离重算G/M14数组精确相等|
|`tests-v1.log`|27项相关本地检查，与CI分开|
|`tests-final.log`|加P13相关检查后31项通过；不称全项目或CI通过|

三张PNG/PDF在`docs/figures/p14/`。所有新成绩回顾性；A层未来命令/状态、B层未来body、C层真实读取/时钟/cache、D层实际18维输入/提交词仅诊断。E层隔离只读过去和计划。可复算不等于独立前瞻验证、完整实际域成员资格或安全证书。
