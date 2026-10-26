# P13正式前理论接口与有限工作域

本文件冻结适用前提，不把正式结果经验最大值回填为未来常数。工程PASS、实验设计PASS与完整理论NOT_PROVEN分别记录。P11/P12及A4原反例保留，A4状态仍NOT_PROVEN_EXCLUDED。

## 状态与模式

状态保留真实COM p/v、model-origin几何与速度项、R/omega、四旋翼相对角/速度、filter、消费/待执行命令、LP/姿态缓存及其物理/运输/native年龄、h/previous/mean/count、executor index/force-sync/activation/ready、sample/native时钟和消息slot。output调用、GRU提交、观测保持/更新、fresh/stale、capture/resume、重复sample拒绝、消费/施力/filter写入/积分不是一个4ms控制映射。合法native平台/跳进/追赶仍在接口内；P13点预测只声明名义独立时钟方案，不把它升级成实际时序全覆盖。

读门由同次pre-read实际initialized/force-sync/index核验，不以last-GRU猜测。target更新/严格超时与capture在重复sample拒绝之前；神经/history顺序沿用源码。修复仅预定实验sample门后非activation捕获启用，参数a=2m/s²，所有臂此前规则相同。

## 有限候选域（正式前固定）

时域为任务起点至完整post-stream后段，名义不超过31s；安全中止记录保留其完整有效前缀和未到达事件。model-origin H∈[.7,8]m、COM H∈[.7,8.5]m、倾角≤80°、物理线速度范数≤8m/s、body角速度各分量≤8rad/s；command/filter∈[0,1000]rad/s、scaled joint/free速度绝对值≤1100rad/s、目标水平位置范数≤26m/速度≤8m/s、h/previous/mean各分量≤1、cache候选年龄≤24ms、source world风为零、四空中SERVO模式。该域不是已证明不变集；模式/free/数值残差未直接观测时成员状态UNKNOWN。正式记录出域或模式变化如实标首次位置，不能删除失败以宣称覆盖。

原子物理步的COM起点/速度/姿态/时间现在直接可观测；其与控制初态异步差仍保留。记录点投影通过不等于连续域不变性。原点/COM关系使用完整实际链接惯心聚合：pC=pbase+R*r_ideal+δp_joint，vC=vbase+omega_world×(R*r_ideal)+δv_joint。原刚性δ=0的首条1e-8m检验FAIL保留，后验观测残差不成为未来界。

## 可复用的执行关系

四SERVO空中结构的A0=αI+κ11ᵀ，α=1/Ir，Ir=2.649858234714004e-5kgm²，κ=22.7821780951。CFM c=1e-9作用后A=dI+κ11ᵀ，d=α+c(α+κ)，显式逆A⁻¹=d⁻¹I−κ/[d(d+4κ)]11ᵀ。在同一适用结构且rhs每分量由command≤100rad/s、free≤110rad/s给出||b||₂≤420时，||λ||₂≤420/d≈.01113Nms；无限force limit不参与此有限界。

独立η=Aλ−b，量纲为对应servo关节速度；不能从e_j反算η再代回自证。原条件式e_j(next)=slowdown*(η−cDλ)，若速度限幅改变desired还须加入desired-command项。约束顺序/维数/模式必须匹配，混合接触LCP全向量不能直接混用servo速度单位。源码/数学逆、旧后验矩阵核查、未来ΔA/η预算分别标记；未来数值预算及模式可达性尚未完整认证。

原filter对于固定mode具有指数差分，跨分支的完整映射连续、各参数单调且平移等变，因此联合(state,input)无穷范数非扩张。消费选择不同的命令时，另加入真实slot/时序差，不能要求每个网络输出均执行。

## 源物理连接与增量

每个旋翼T_i=kΩ_i|Ω_i|（方向符号由真实joint/turningDirection处理），Fdrag_i=−cd|Ω_i|P_axis(v_link−wind)，v_link=vC+R(omega×r_i)+关节/几何残差。m dvC/dt=mg+Σ(Fthrust+Fdrag)+未建模外力。使用旋翼各向异性惯量、相对转角和spin角动量，可以独立构造body角动量增量核；单步用实测输入的吻合仍是后验验证。给定实际未来转速/姿态/速度的诊断不是自主预测。

源推力误差满足|δT_i|≤2kΩmax|δΩ_i|；轴投影阻力满足

|δFdrag_i| ≤ cd[Vrel,max|δΩ_i|+Ωmax(|δvrel_i|+2Vrel,max|δaxis_i|)]。

结合m与旋转矩阵作用，可传播有限时域速度/高度误差；初值、几何、求解误差和cache误差不能省略。有限样本局部Jacobian不作全域证明，孤立GRU不收缩不直接否定完整反馈。

## 全前缀高度与间隔关系

L=H0−H，D=max(0,sup过去L)，W=−dH/dt；D单调且一旦失败不能在capture/resume撤销。COM/model-origin分别保留：Horigin=HC−ez R r，Worigin=WC+ez R(omega×r)，并保留实际关节残差项。

若在恢复段内有经认证的向上加速度下界ar>0，则对向下W0≥0：W(t)≤W0−ar t，L(t)≤L0+W0 t−ar t²/2；全前缀上界取t∈[0,T]最大值，最大附加损高≤W0²/(2ar)。这是充分储备，不能称实际必要损高。B前集合由该流映射与A保持/接回跳变顺序组合，不在接回重置高度/历史；第二事件继续从该集合传播。

另可在有界真实Ω与Vrel域由源Tmax/dragmax算最大可能向上加速度Aup,max。只要该上界有效，即使最理想控制也至少损高W0²/(2Aup,max)才可停止下降；有限间隔取t*=min(T,W0/Aup,max)。这是域条件下必要余量，与前述充分储备方向相反，不把command限幅单独当实际joint未来上界。

要认证ar，由源推力/姿态/阻力推得

ar ≤ cos(theta_max)ΣkΩmin²/m −g−Fdrag,down,max/m−Eexternal。

这要求整段真实执行/姿态/相对速度域保持，不能凭瞬时不裁剪、一次峰值或示例a=1宣称成立。修复参数a只决定捕获参考减速，不等于机体ar。

## 捕获、保持、接回与历史

相关捕获的初态是同次控制实际读取的缓存p/v，不能替换独立自由目标。异步捕获误差含Vmax δt、Amax δt和cache误差。减速速度映射为shrink(v,a t)，对捕获速度非扩张，参考位置差≤δp_cap+tδv_cap；对参数扰动分别加入t|δa|与.5t²|δa|。这些关系跨停止/未停止模式连续。

整个保持段输入误差可用相关初态误差、机体/参考加速度预算积分；必须∀t覆盖保持，接回再加入实际计划目标与机体/捕获参考的跳变，随后继续传播h/action/history/filter和恢复段。瞬时速度匹配不证明整个保持不限幅，更不证明完整后段安全。恢复间隔对B前W/L及历史的作用为实验主要输出；不要求单调。

## 已知未闭合处

直接COM/time起点填补旧不可观测接口，但未来SERVO数值残差/模式与几何可达界仍是首个执行条件缺口。即便给定它们，EKF/gyro-filter/cache误差和神经历史的闭环联合传播还未闭合；新直接物理数据可定位这一误差，而不是把误差经验最大值升级成界。M5因此明确继承M4经验角/水平/cache闭合。完整源核开放重放出域及M5漏判保留，不能以任务OR正确掩盖倾角漏判或以小单步残差证明整段。
