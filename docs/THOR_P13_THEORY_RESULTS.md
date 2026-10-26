# P13：有限执行关系、恢复间隔与高度余量

本文件是独立于正式平台冻结的离线理论结果层。实验版本仍为`4c122aaa9710b93699c52cbfc059653681ef4b31`；本文件和分析工具不改变实际控制器、插件、模型参数、事件或评分阈值。正式前的状态、域及义务保留在`THOR_P13_THEORY.md`。结论是**可计算的条件关系及明确缺口**，不是完整神经闭环安全证书。

## 1. 现在能直接确定的起点

五链接惯心的质量加权COM位置/速度、base姿态/角速度及物理步时间已经直接取得。Pre状态属于`simTime-dt`，Post属于`simTime`；二者共用步编号和目的步时间标签。`Post(k)=Pre(k+1)`可独立核对位置、速度、姿态、角速度及全部链接状态。运输、sample、native、LP/姿态缓存年龄仍是不同量，完整EKF/队列没有快照恢复。

固定理想刚体公式遗漏实际关节/约束残差：首条位置误差2.9494e-8m超过原1e-8m门，原FAIL保留。完整关系为

\[
p_C=p_b+Rr+\sum_i m_i\delta p_i/M,\quad
v_C=v_b+\omega_w\times Rr+\sum_i m_i\delta v_i/M.
\]

加入**同次直接观测**的残差后接近浮点精度，只是代数与数据连接核对，不证明未来残差界。源几何中base→COM为0.001869131m，named-model-origin→COM约0.241869131m；两者不得混用。向下速度直接由物理线速度取负，回调差分另标，绝不充当直接速度。

## 2. 物理源核：修正的是离散连接，未产生第二个候选模型

源码推力、轴投影阻力、各向异性转子惯量和spin角动量给出独立一步核。进一步按[DART 6.13.2 FreeJoint更新源码](https://raw.githubusercontent.com/dartsim/dart/v6.13.2/dart/dynamics/FreeJoint.cpp)处理基座的经典线加速度、姿态及速度坐标更新后，令`M=R_old,N=R_new,r=r_base_to_COM`，有

\[
v_{b0}=v_{C0}-M(\omega_0\times r),\quad
\alpha=(\omega_1-\omega_0)/h,
\]
\[
a_b=a_C-M[\alpha\times r+\omega_0\times(\omega_0\times r)],\quad
v_{b1}=v_{b0}+ha_b,
\]
\[
v_{C1}=v_{b1}+N(\omega_1\times r),\quad
p_{C1}=p_{C0}-Mr+hv_{b1}+Nr.
\]

代码与实际Ubuntu发行库的普通文件hash分别保存；阅读该上游源码不等于重新认证发行二进制。12条开发记录的一步核使用每一步真实Pre状态及实际已选命令：COM位置/速度最大差约3.1e-13m/2.7e-13m/s，角速度约2.3e-12rad/s，SO(3)角误差约1e-8度。详见`data/p13-20261026-theory/source-discrete-audit-v1/summary.json`。

同一开发NORMAL的独立核查`kernel-progression-v1`使用相同45°错误预测见证尺度，不混比旧50°与新80°的停止域。源平均惯量、实际转子各向异性、FreeJoint离散更新版本首次错误45°见证分别约11.40/20.65/21.33秒；共同前682步的位置最大误差分别4.16e-4/1.62e-7/2.06e-8m，说明源结构修正改善了受控开放重放，但仍会错误发散。把M4的LP经验plant强制赋真实物理q/omega会在2.64秒产生错误45°，这是状态/observer闭合的诊断，不能当作其原自主预测成绩排序。各版本未来输入也分别标明actual rotor或actual command，未装成相同输入试验。

这属于**后验单步关系核查**。只给初态及实际未来命令的开放重放仍在约21.3–22.7秒首次离域。替换实际joint或转子相位几乎不改变首次离域；逐步注入真实COM速度或机体姿态能使诊断保持在域内，但使用了未来实测量。证据在`controlled-kernel-replays-v1`。它定位了耦合积分/姿态—速度反馈的长期敏感性，不能证明实际失败由求解残差造成，也不能混入M5自主预测成绩。M5仍是唯一新候选，继承M4经验角/水平/cache闭合；本核未作为M6或正式后调参版本。

## 3. 有限四SERVO：不用无限force limit推冲量界

在四个平行轴、无接触/其他约束、无desired限幅、源质量/惯量结构的条件下，

\[
A_0=\alpha I+\kappa 11^T,\quad
A=dI+\kappa11^T,\ d=\alpha+c(\alpha+\kappa),
\]
\[
A^{-1}=d^{-1}I-\frac{\kappa}{d(d+4\kappa)}11^T.
\]

`Ir=2.649858234714004e-5kgm²`，`alpha=1/Ir`，`c=1e-9`，`kappa≈22.7821780951`。独立残差为`eta=A lambda-b`；不从joint误差反算eta再代回自证。

在正式前声明的角速度、执行和相对空气速度域，再明确条件`实际scaled joint与理想filter差≤Ej=1rad/s`下，源力矩和转子轴向Coriolis关系给出自由joint速度≤104.23825313rad/s；command≤100rad/s，因此`||b||2≤408.47650626rad/s`，

\[
\|\lambda\|_2\le\|b\|_2/d\le0.0108240483272\ {\rm Nms}.
\]

无限force limit没有参与这个有限上界。条件误差式仍为

\[
e_j(k+1)=10[\eta-cD\lambda+desired-command].
\]

在上述未限幅模式，精确实数求解的CFM项scaled误差≤4.08724e-6rad/s。使`Ej≤1`闭合的一个**充分数值预算**为`||eta||∞≤0.0999995912769rad/s`，另须处理实际矩阵扰动与浮点filter误差。数值来自源参数和域，并非正式数据最大值。`servo-budget-v1/budget.json`保留全部计算和义务。

**尚未证明**真实浮点DART在整个未来可达域均满足该eta/矩阵预算、无模式切换和几何残差预算；旧直接A/b/lambda小残差只是后验支持。P13轻量平台未重复采集矩阵，不能把其离散投影PASS写成完整SERVO成员PASS。最早执行缺口现在是这个明确的未来数值/模式义务，不是filter非扩张关系被反驳。

还有两个不依赖正式结果最大值的源关系：神经动作clip[-1,1]和固定映射`150+850(a+1)/2`给command∈[150,1000]rad/s；在实数源filter中，任何升/降切换的更新都是state/input的凸组合，初态与输入在[0,1000]时该区间不变。跨模式映射单调且平移等变，联合无穷范数非扩张；不同命令消费词须另加输入/时间差。实际C++浮点误差仍需预算。

相对链接速度上界也有明确来源：`|v_link|≤|v_COM|+|omega|rmax+E_joint_link`。正式前域给8+sqrt(3)·8·0.252846≈11.50354m/s；若另有未来链接残差≤0.49646m/s且源风为零，就得到候选Vrel≤12。这个残差余量不是观测最大值，其未来可达界尚未证明。计算在`finite-domain-antecedents-v1/relations.json`。

## 4. 源执行到全前缀高度的可计算必要余量

令`H=COM向上高度,W=-v_z,L=H0-H,D=max(D_old,sup L)`。当前L可恢复，D一旦越界不可撤销。力在filter更新之前计算。给定已知filter上界`f_i(k)`，源command≤1000rad/s、最快上升时间常数0.0125s给出理想最大filter递推

\[
f_i^+(k+1)=1000+[f_i^+(k)-1000]e^{-h/.0125}.
\]

若未来scaled joint≤`f_i^++Ej`，相对链接空气速度≤V，无额外上向接触力，则源推力/阻力给出最大可能向上加速度

\[
U_k=\frac{\sum_i k_T(f_i^++E_j)^2+c_dV\sum_i(f_i^++E_j)}m-g+E_{v,disc}/h.
\]

于是对所有未来控制、事件和native时钟词，在这些物理前提下

\[
\underline W_{k+1}=\underline W_k-hU_k,\quad
\underline L_{k+1}=\underline L_k+h\underline W_{k+1}-E_{p,disc}.
\]

`max_prefix lower L`是**至少需要的额外COM余量下界**；余量小于它时连最理想执行也不够。超过它仅表示未被这个必要条件排除，绝不是安全准入。已知首条待消费命令可以固定第一步，包含真实执行延迟。

理想源结构由旋转群增量给出`E_v,disc≤r h²(2 Omega Aomega+Omega³/2)`、`E_p,disc≤r Omega²h²/2`。域内`|omega_component|≤8`等源参数推得`Aomega≤1005.85rad/s²`，额外加速度预算约0.218353m/s²，位置预算2.87099e-6m/步；这些不是观测最大值。**额外实际浮点/关节几何误差仍须另有预算，域不变性也未证明。**

工具`height_constraints_v4.py`以45位区间算术和向外舍入计算每一前缀。条件`W0=.98m/s,四filter=750rad/s,Ej=1,V=12m/s`及上述理想源离散预算，额外必要COM储备约0.0643m。这个例子不是已认证的实际未来边界；COM→model-origin还要加姿态几何，转成LP主任务判据还需估计器误差。不能以COM必要储备直接判LP任务失败。

## 5. 恢复到B前的充分映射及间隔

若整段已证明净向上加速度至少`a_r>0`，则

\[
W_B\le W_A-a_rT,\quad L_B\le L_A+W_AT-a_rT^2/2,
\]
\[
D_B\le\max\{D_A,L_A+\max_{0\le s\le T}(W_As-a_rs^2/2)\}.
\]

驻点`min(T,max(0,W_A/a_r))`必须检查。需要至少`T≥W_A/a_r`才能由此保证非下降；附加全前缀储备`W_A²/(2a_r)`是**充分储备而非实际必要损高**。源推力、姿态及下向阻力必须使

\[
\cos\theta_{max}\sum_i k_T\Omega_{i,min}^2/m-g-F_{drag,down,max}/m-E_{external}\ge a_r.
\]

对DART物理采样点，应另保留离散位置预算：`W_j≤W0-j h a_r`，`L_j≤L0+j h W0-a_r h² j(j+1)/2+j epsilon_p`，逐j取最大D；`recovery_discrete_v1.py`以精确有理数核对30个例子。0.55秒只包括137个完整4ms步，最后部分及连续点需另有界，不能把下一步当作已在窗口内。上面的连续式仅适用于相应积分/跳变条件已闭合的平滑模型，不能直接代替DART全域认证。filter/joint下界、姿态锥和cache/历史反馈须覆盖A保持、接回、恢复、B及后段。参考减速度RTDEC2不是机体`a_r=2`。该关系把试验问题转成可检验的B前L/W/D和整段执行下界，不能用物理包络可行替代神经闭环可达。

高度/速度增量对每段有`E_W^+≤E_W+T E_a+E_jump`、`E_L^+≤E_L+T E_W+T²E_a/2+E_geom,int`。按真实模式词依序组合；jump在何时发生决定剩余时间对高度的权重。捕获相关性、保持、接回、执行和全部神经/动作历史不能省略。

## 6. 全保持修复参数条件与具体失败位置

修复速度匹配只适用于相关水平捕获；垂向和缓存误差另有预算。设整个真实保持时长≤T、实际PX4机体原点（base/IMU软件参考点）加速度范数≤A；Ep为捕获/当前缓存位置误差之差的全保持预算，Ev为当前与捕获速度缓存误差的合计全保持预算（包含初始速度偏差）。这些不能只由捕获瞬间误差推出；缓存跳变也须覆盖。则以下是所有保持前缀不裁剪的充分条件：

\[
E_p+E_vT+\tfrac12(A+a)T^2\le.5,
\quad E_v+(A+a)T\le1.
\]

另有参考制动路程`v²/(2a)≤Mpath`和接回参考跳变条件`Etrack+delta_v T+.5aT²≤.5`、`delta_v+aT≤1`。这是可计算的参数交集，不是只有捕获瞬间误差为零。

`v=1.8,T=.24,A=2,Ep=Ev=.02,Etrack=.2,delta_v=.1,Mpath=2`时交集约`[.81,2.08333]m/s²`，包含原a=2。**A=2及缓存/时长域没有被证明为实际未来域。** 源COM合力加速度盒约31.90575m/s²还不能直接充当model-origin/LP加速度界；按LP所指base/body的小杆臂补上旋转几何及源离散速度预算的候选界约34.363m/s²时，交集仍为空。其余浮点/关节/EKF/cache预算尚缺。这个具体保守性障碍说明瞬时匹配不足以给整段保证；即使局部交集非空，接回后的神经/执行/高度反馈仍未闭合。native平台/追赶改变真实T，不能默认全部保持恰为.16秒。

后续源码核对发现LP发布机体body原点，不能套用named-model的.241869杆臂；实际零IMUoffset与base_link传感器支持小杆臂.001869关系。v3的321.847是named-model点包络，保留但不再当LP包络；v4明确body点后全局候选界34.363，交集仍为空。36个修复保持段有6段base速度增量率投影超出假想A=2，不能把该局部例子称为记录覆盖；这是实际simdt的差分诊断，非直接加速度或未来界。named-model点的36段全部超2是不同几何点的诊断，v1原结果保留。

`repair-parameter-conditions-v1`遗漏位置式中的`Ev*T`，原文件保留；独立v2补齐并回查，示例由速度条件主导、交集和全盒为空结论不变，其余位置上界收紧；v3再区分COM与model-origin加速度预算，并明确全保持cache误差假设。正式参数、样本和分类完全未变。

## 7. 历史增量、反例和最具体剩余项

实际权重的解析Lipschitz构造保留ReLU/sigmoid/tanh、GRU提交/非提交与previous/mean更新，不用局部采样Jacobian证明全域收缩。`neural-increment-v1`得到输入映射无穷范数约57.60、hidden约10.98、输出约4.523；同外生输入、初始记忆差.001的这个保守构造在第3调用退化到动作绝对界2。它不是实际轨迹必然发散，也不构成实验拒绝门。没有证明孤立GRU收缩不是停止完整反馈分析的理由。

还对整个非负比较连接作了有限多步检查：加入机体/执行/cache反馈后的单调增量上界，逐分量不小于将其余误差输入置零的h/previous/mean子比较系统。因此这个具体“独立外盒+绝对增益”构造在子系统已于第3调用达到动作界2后，加入非负反馈项无法恢复信息性。详见`full-feedback-positive-comparison-v1/obstruction.json`。这不是实际闭环发散反例，也不证明独立hidden扰动可实现；说明必须利用状态相关性、可达集合或非对角/多步储能中的抵消，不能只换一个风险分数。完整耦合储能未建立。

两个相同当前L/W但不同历史D的状态不能具有相同任务成败；相同倾角峰值也不能确定积分损高。已有A4及P12b运动学反例保留，其神经闭环可达性不能由物理包络代替。**A4 NOT_PROVEN_EXCLUDED**；合法P11第70条native平台仍包含在接口内。

真正尚缺的是：在可达、含实际浮点/约束模式的有限域内认证执行误差，随后把姿态/物理速度经估计器/cache/时钟与h/action/history的恢复映射闭合到B及完整尾段。直接COM/time起点不再UNKNOWN；未来域及反馈不是由多飞几个相似小残差样本就能认证。可离线继续做源算法数值预算、EKF/cache结构和联合多步界；只有缺少真实新模式/间隔范围的信息时才需要另获预算的新飞行。

## 测量点关系的具体修正

`EKF2.cpp::PublishLocalPosition`和`OutputPredictor::getLatLonAlt/getVelocity`明确body/IMU-offset语义；66条ULog的IMUoffset均零，SDF传感器在base_link。LP应与COM→body小杆臂、EKF高度原点与时变cache误差连接，不能默认LP=Gazebonamed-origin。冻结M5恰有这项错误，保留其原前瞻成绩。独立输出重投影仅诊断、未重跑反馈，不能升级为新候选验证。源推力/COM余量与物理named-origin关系仍各自有效；转成LP约束必须使用正确body点和新的已认证误差预算。这项源码缺口已具体定位，完整估计器/缓存闭环仍未解决。
