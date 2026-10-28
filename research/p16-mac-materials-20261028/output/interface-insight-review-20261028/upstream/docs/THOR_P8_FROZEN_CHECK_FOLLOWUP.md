# P8 冻结预测核对：本机输入追踪续查

2026-10-24（Asia/Shanghai）。接手基线与开工时远端 `main` 均为 `5fd4cab95184c7d825495d4c2e82192484e7ce3d`（`git ls-remote` 核实）。本次没有新增飞行、训练、拟合、调参或替代预测；未改 `tools/p8/`、实验配置、原始资料、旧分析输出及[历史核对报告](THOR_P8_FROZEN_CHECK.md)。新增输出放在同一分析目录的 `followup-01/`、`locate-01/`、`locate-02/`。

**冻结输入仍未找齐，预测核对未闭环。** 在下述已检查位置没有找到原预测、完整模型及原误差/跳过规则。实际文件 SHA-256 为 **NA（未取得文件，非哈希不符）**；要求的哈希仍为：

```text
fe784e62aa5ee8c1ea5cb29fc2ec2d44169c2d02a084130c31342d28d25ba7d4
```

## 找到了什么来源线索

本机原交接会话 `~/.claude/projects/-home-car-uav-handover/14bf78b5-987e-4bec-a7d3-f2e6732bac7f.jsonl` 保存了两版任务。相关段落、消息哈希、会话哈希及行号见[输入定位记录](../data/p8-frozen-check-20261024/locate-01/input-search.json) 的 `handover`，没有把整份会话上传。

- 第3行，2026-10-21 15:16:38（UTC+8）：最初设想由项目侧交付包括预测文件在内的材料。
- **第784行，2026-10-22 02:02:24（UTC+8）：后续任务明确改为项目侧另存带预测的 `p8_frozen.json`，并明确说明 Thor 没有这份文件，只登记哈希。** 同一消息称项目侧没有本实验仓库的写权限，故仅以附录交付四份源码/索引，在 Thor 重建不含预测的清单。这解释了“未提交”和“未交付”的区别，不能把最早的交付计划当成实际已收到文件。
- 后续任务指向 **`p8-refit/README.md`**，称模型补入约88 ms纯延迟，基于该版本冻结B清单；还转述过P7留出结果。这里仅记录交接者的说法，**未取得该 README、实现、参数或原验证记录，未将这些数字作为本次实证结论**。
- 更早任务另指向项目侧 `notes/target-interface/experiments/common.py`。该路径与 `p8-refit/` 是定位模型项目的具体标识；不假设二者一定在同一级目录。
- `tools/p8/p8_build_lists.py` 只按候选池种子和 `p8_list_index.json` 重建输入；索引不含模型参数、误差界或 `zone` 判定逻辑。在线BO的GP是使用实测反馈的搜索器，也不能替代原冻结预测模型。Lab中的 RAPTOR 策略包同样不是待查的低阶预测模型。

**最可能的位置是生成P8清单的项目侧研究工作区，其中有 `p8-refit/README.md`；可能在另一台机器。当前证据没有机器名、绝对路径或项目远端地址，因此不能把“另一台机器”写成已核实事实。** 本次未登录未知机器，也没有可凭据定位的远端项目。GitHub连接器未提供此实验仓库的访问权；本地 `gh` 没有登录。这是访问路径限制，不能据此推断远端文件不存在。本实验仓库的 SSH Git 读写通道可用。

## 检查范围与未覆盖范围

[可复现定位脚本](../tools/p8_frozen_locate.py)记录每个检查的状态，而非把失败当成“无文件”。[初轮完整记录](../data/p8-frozen-check-20261024/locate-01/input-search.json)、[归档清单](../data/p8-frozen-check-20261024/locate-01/archive-inventory.csv)与[大型/7z归档补查](../data/p8-frozen-check-20261024/locate-02/archive-completion.json)共同界定搜索范围。

| 位置/来源 | 实际检查 |
|---|---|
| 本机目录 | 枚举 `/home`（含当前实验目录、Lab、`uav-lab/raptor`、`uav_sf`、`px4_contract_gap`、Documents/Codex、Downloads、scp、回收站和备份）、`/mnt`、`/media`、`/opt`、`/srv`、`/tmp`、`/var/tmp`、`/var/backups`、`/target`、`/root` 的可读名称；检索原文件名、P8模型/预测/refit标识及已知项目侧路径 |
| 关联内容与交接 | 定向搜索关联研究目录、Claude/Codex会话、文件历史和本次之前的临时脚本；命中的是说明、任务及配置哈希，没有完整原模型 |
| 当前Git | 所有本地分支、远端跟踪分支及reflog中的对象路径，含 `archive/full-raw-history`；当前只有一个工作树；未找到目标路径 |
| 关联Git | `/home/car/uav-lab/raptor`、`/home/car/uav_sf` 的所有引用/reflog对象路径；未找到目标路径 |
| 历史归档 | 当前Git中16个、旧RAPTOR仓库中10个不同归档对象逐一检查成员名称；均无目标。包括历史 `project-source.tar.gz` 和多版untracked补丁包 |
| 悬空对象 | 当前仓库 `git fsck --connectivity-only --no-reflogs --unreachable` 返回0；36个悬空tree逐一查路径，81个悬空blob全部计算SHA-256，无指定哈希命中；[对象记录](../data/p8-frozen-check-20261024/locate-01/git-unreachable.txt)保留 |

名称枚举不等于全文读取所有文件；没有遍历 `.git` 内部文件名，而用Git对象检查；没有递归展开归档中的嵌套归档。`uav3d` 是指向已不存在目标的符号链接，属于断链而非读取权限错误。目录搜索遇到30项错误：29项 `EACCES`（包括 `/root`、`/media/root`、`/opt/containerd`、系统私有临时目录及一处旧PX4运行目录），另1项为 `/tmp/fuse` 路径不存在；这些位置不声称已查遍。

初轮记录2525个归档路径，2464个可检索成员名称（163种不同内容哈希）；其余61个通过已安装的 `bsdtar` 补查，58个完成成员检查，无目标命中、无超时。最终3个读取失败分别为两份实际是Docker构建文本的 `Dockerfile.tar` 和本次测试故意构造的损坏归档；仍明确保留 `read_error`。两处名称命中来自本次定位器回归测试创建的**空文件归档夹具**，路径在 `/tmp/pytest-of-car/pytest-30/`，不是模型输入；直接名称命中的两个 `/tmp/p8-refit-*errors` 也是本次查找日志，不是项目目录。完整状态见 `locate-02/archive-completion.json`，不把读取失败称为“已证明无文件”。

## 900条复核和严格匹配边界

原2750个输入文件在分析前后再次全部通过SHA-256核验。原B2前376次对象与保留归档逐项相等，后74次单独标记；CSV、配置、summary、完整事件参数、预算及种子仍为900/900一致，900个身份和仿真种子均互异。旧的固定随机基线划分逐条保留，24次T1探索独立保留（18域内、6域外、12个不同种子），未加入900分母或校准集。

| 对照状态 | 数量 | 解释 |
|---|---:|---|
| 已匹配离线输入 | 540 | random/contest/ours；完整输入可与原清单核对，不代表已匹配预测 |
| 其中预算也相同、等待原预测 | 539 | `strict_comparison_candidate=True`；当前真正预测匹配仍为0 |
| 离线时域不同 | 1 | 单列，不能进入严格预测比较 |
| 在线fuzz/bo | 360 | 明确 `online_no_verified_prior_prediction`；未借用别的方法或共享候选的预测 |
| 未执行离线条目 | 540 | 不进实测分母，不能把1080清单当1080次实验 |
| 原预测匹配 | **0/900** | 文件未取得；不是900条预测错误或900条模型失败 |

唯一时域差异仍是 `contest-T0-s0-k28`：`v=2.4, heading=28°, durs=[0.32,0.27], restored=[0.46]`，窗口 `[[0,0.32],[0.78,1.05]]`；首段都是1.00 s，历史闭式预算/离线清单末段2.60 s，实际配置2.55 s。该次实际主/任务判据均通过，但不能证明2.60 s预测正确。原预测本体缺失，其具体预测时域未确认，继续排除严格匹配。其他899条仅可称历史预算与实际相同；其中360条在线记录仍没有已核实的事前预测。

新[逐条对照表](../data/p8-frozen-check-20261024/followup-01/matching-ledger.csv)保留完整输入和实际预算，另列事前/事后状态及各判据NA。各系统×方法×次数的[分组表](../data/p8-frozen-check-20261024/followup-01/group-summary.csv)明确列出误差、秩相关、危险低估、原跳过数/比例、跳过集合倾角/掉高/主/任务失败数及区间、保形跳过与覆盖相关字段；缺输入均 **NA**，不填0。即使补齐离线预测，也只有在原冻结模型完整可复现时，才可对在线输入另外做“事后使用冻结模型评价”，不得标成事前预测。本次没有做此补算。

## 不依赖模型的结果

计数与历史一致：倾角失败432/900，掉高失败111/900，原主判据失败432/900，任务失败511/900。其中79条仅掉高失败，占倾角通过468条的16.88%；**这不是原模型跳过集合的漏判率**。倾角失败单独按峰值≥45°统计，掉高按损失>1 m；主判据直接读取原结果，并未用倾角替代其定义。失败中止造成后续时域删失，仍明确标记，不补造未观测事件。

| 系统/中断次数 | 实测n | 倾角失败 | 掉高失败 | 原主失败 | 任务失败 | 固定校准/检验n |
|---|---:|---:|---:|---:|---:|---:|
| T0/2 | 157 | 55 | 36 | 55 | 83 | 22/22 |
| T0/3 | 178 | 70 | 44 | 70 | 102 | 13/16 |
| T0/4 | 115 | 62 | 13 | 62 | 71 | 10/7 |
| T1/2 | 170 | 78 | 5 | 78 | 83 | 23/23 |
| T1/3 | 155 | 92 | 4 | 92 | 94 | 17/10 |
| T1/4 | 125 | 75 | 9 | 75 | 78 | 5/12 |

系统×方法每组90次及更细交叉分层、各实测失败率与95% Wilson描述性区间见分组表；[失败率图](../data/p8-frozen-check-20261024/followup-01/failure-rates.png)和[倾角/高度图](../data/p8-frozen-check-20261024/followup-01/tilt-altitude.png)重现历史结果。自适应搜索的依赖与分布偏移仍限制这些二项区间的总体解释。

固定划分仍是每系统随机基线90条，按 `SHA256('P8-frozen-check-v1|'+run_id)` 排序，前45校准、后45检验；其余360条仅评价。没有因结果改变分配。若输入齐全，原计划单侧90%保形残差用第42阶统计量；**当前没有残差，因此覆盖率、跳过比例、跳过集合各判据失败率及其区间均NA**，不是0%覆盖或0失败。[保形状态表](../data/p8-frozen-check-20261024/followup-01/conformal-status.csv)逐系统明确列出45/45与缺预测数量。细分至次数后，校准最少仅5条、检验最少7条；方法×次数还有空组，不能声称稳定覆盖，也不混入定向/在线样本补校准。倾角覆盖仍不能替代高度或任务安全覆盖。

T0相位的所有方法×次数分层[完整保留](../data/p8-frozen-check-20261024/followup-01/t0-phase.csv)：任一计划恢复间隔落在[0.4,0.6] s时123/275主失败，其他64/175；random为8/36与8/54，ours则33/45与43/45，2次中断层方向也反转。它是受次数、速度、方向及搜索反馈混杂的观察关联，不能确定普遍危险相位。独立[24次探索账本](../data/p8-frozen-check-20261024/followup-01/exploration-ledger.csv)没有混入这些T0或900条统计。

## 下一步需要取得的原件

从**生成P8清单的项目侧工作区或其当时归档**取得以下材料，并记录机器/仓库/提交或归档身份：

1. 原始字节的 `p8_frozen.json`，要求上述完整SHA-256，不接受按现有清单重建的替代文件；包含全部输入、预测、原 `model`/`zone` 字段和时域定义。
2. `p8-refit/README.md` 及其引用的冻结模型实现、全部参数（包括延迟实现）、依赖版本、生成入口和对应提交/归档；需要原误差界、分档/非对称规则及“可跳过”的精确定义，不能只提供约88 ms这个转述值。
3. 生成预测与清单的当时脚本、运行记录/manifest和工件哈希；核实生成时所用预算及 `contest-T0-s0-k28` 的2.60 s终止时域。定位时可用 `notes/target-interface/experiments/common.py` 作为另一条项目标识。

没有机器路径时，下一步是向持有上述项目侧工作区的人取得**位置或原始工件包**，而不是在Thor上重新拟合或重建预测。只有原件核验后才能完成误差、危险低估、原跳过集合失败率及固定划分的保形数值。

## 复现与验证

```bash
# 路径必须不存在；保留已有分析和搜索现场。
uav_lab/.local/venv/bin/python tools/p8_frozen_locate.py --output /tmp/p8-locate-new
uav_lab/.local/venv/bin/python tools/p8_frozen_locate.py \
  --complete-archives-from /tmp/p8-locate-new/input-search.json --output /tmp/p8-archives-new
MPLCONFIGDIR=/tmp/p8-mpl uav_lab/.local/venv/bin/python tools/p8_frozen_check.py \
  --output /tmp/p8-check-new
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=tools uav_lab/.local/venv/bin/python -m pytest -q \
  tests/test_p8.py tests/test_p8_frozen_check.py tests/test_p8_frozen_locate.py \
  tests/test_export_target_association.py
```

初轮搜索的精确脚本快照及其哈希保存在 `locate-01/script-snapshot.py`；最终定位器另增加大型/7z归档补查入口。搜索目录、临时文件、Git引用会随运行改变，搜索记录不承诺逐字节稳定；固定实测分析的输出应确定重现。验证结果与输出哈希见[本次验证记录](../data/p8-frozen-check-20261024/followup-01/validation.json)。
