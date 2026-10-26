# P12c 有限执行算子、残余下降与高度/历史传播

工程未放行，正式0；以下明确区分实数结构关系、后验数值核查和未认证未来域。没有新增预测模型/拟合，没有把经验最大值当硬界，A4仍NOT_PROVEN_EXCLUDED。

## 四SERVO无接触子域的全域结构

候选工作域覆盖task0至完整poststream（≤36s），H_model∈[.7,8]m、θ≤50°、机体速度范数≤8m/s、body omega各分量≤8rad/s、命令/filter∈[0,1000]rad/s、实际/自由joint缩放速度≤1100rad/s、unwrapped rotor角绝对值≤1e6rad、cache age≤24ms；保留真实sample/native模式词，物理步为4ms，控制不是单一4ms映射。它允许45°/1m任务失败，不因失败标签删数据。未来域不变性及连续实际状态成员资格尚未证明。

逐个读取实际碰撞box及link/model变换，用旋转包围球和三角不等式得到所有collision点距named origin上界.621582459m。单机平地、self_collide=false且H_model≥.7时，该条件几何域内无地面/自身接触；不是忽略接触。域外接触/其他约束仍在原完整LCP记录里。最初候选H_min=.6不能推出无接触，source-only修订和原失败候选保留，未改实验条件/阈值。物理q/H回调不构成连续域不变性证明。

四rotor绕平行z轴，COM在轴上，轴向惯量相同：

`I_r = 2.649858234714004e−5 kg·m²`。

机体yaw自由有效惯量由SDF给出：

`E_z = I_base,zz + Σ m_i(x_i²+y_i²)`，`κ=1/E_z=22.7821780951`。

消去free-base速度的质量矩阵Schur补，在理想实数刚体模型、仅四个无限力/速度限SERVO、原±1e16位置限不激活时：

`A0 = I_r^−1 I4 + κ 11ᵀ`。

这是动能/质量结构关系，不是采样Jacobian或拟合。C_f=c=1e−9只增加对角c·diag(A0)。令α=I_r^−1、D=α+κ、d=α+cD，则

`A = d I4 + κ11ᵀ`，

`A^−1 = I4/d − κ11ᵀ/[d(d+4κ)]`。

精确有理数验证逆矩阵恒等式；每个rhs基向量均精确满足。λ_min≥37737.8679，理想条件数≤1.002414782。**无穷force limit没有给冲量界；正惯量结构和有界b给条件界。**

若joint command≤100rad/s、free velocity≤110rad/s，则`||b||₂≤420rad/s`，实数精确求解给`||λ||₂≤.011129405 N·m·s`。沿用已核验源码等式`e_j(next)=slowdown(η−cDλ)`，未发生command clipping时CFM项缩放L2误差上界约`4.202536e−6 rad/s`。这不是观测最大值。

同一声明子域、相同c与结构A，对任意两组b：

`||Δλ||₂≤||Δb||₂/d`，

`||Δ(v_post−u)||₂≤γ (||Δu||₂+||Δv_free||₂)`，`γ=cD/d≈1.000603694e−9`。

实际安装库还有ΔA/独立η项；需要未来机器误差预算。不能用后验η≈1e−15宣布未来机器求解误差全域受控，也不能把条件实数子映射称完整仿真器证明。body/free-velocity、数值积分和cache域仍需闭合。

复用P12b五条已见飞行：**74,689个仅四SERVO系统**与独立SDF矩阵的最大元素差7.275958e−12。完整118,941系统中其余含接触/其他约束的记录不删、不套这条子域定理；原全耦合数值等式审核仍保留。行数不是独立飞行样本，数值吻合仅核验源码连接，不替代上述前提或实际二进制全域认证。

## 连接历史偏离、推力与垂向误差

保留相关capture、异步capture时序误差、减速参考非扩张、实际hidden/previous/mean/count及输出/GRU模式顺序；滤波继续用真实升/降分支与dt。捕获参考不可改成独立自由初值，不要求GRU孤立收缩，动作绝对差2不作实验配对门。

有符号源推力`T_i=k z_i|z_i|`，k=8.54858e−6。有限|z_i|≤Ω̄时，

`|ΔΣT_i| ≤ 2k Ω̄ Σ|Δz_i|`。

令n为真实rotor/world共同轴，F̄_T为总推力上界，则

`|Δa_down| ≤ (F̄_T/m)||Δn|| + (2kΩ̄/m)Σ|Δz_i| + E_drag/m`。

源码阻力是`−c_d|z_i|(I−nnᵀ)v_rel,i`，不是只依赖垂向速度的标量阻尼。保守增量可由速度、转速及投影差组合：

`E_drag ≤ c_d[V̄Σ|Δz_i| + Ω̄Σ||Δv_link,i|| + 2NΩ̄V̄||Δn||]`。

`v_link=v_origin+R(omega×r_i)−wind`；c_d=8.06428e−5。机体姿态、真实自由速度、风及cache/数值误差域必须有来源。理想执行小增益不自动闭合神经—机体—估计器反馈。

## 全片段高度、D与恢复条件

L=H_origin−H、W=−dH/dt，D为整个任务到当前的历史最大损高。保持/接回/恢复任意片段T：

`W_out=W_in+∫a_down ds+velocity_defects`；

`L_out=L_in+W_in T+∫(T−s)a_down(s)ds+integration/geometry_defects`；

`D_out=max(D_in, sup_prefix L)`。

物理capture/resume不重置L/W/D；参考跳变和神经/history模式影响后续a，不能删接回/末段。COM至model的R相关高度、`e_z R(omega×r)`速度项，以及LP估计/初始参照差均需传播。世界界要转成原LP任务保证，还缺LP/cache映射误差界。

同一物理时间词下，条件增量为`E_W,out≤E_W,in+T E_a+E_vel`、`E_L,out≤E_L,in+T E_W,in+T²E_a/2+E_geom/int`；不同时钟/时长词另加时序项。不能将sample/native平台统一成恒定4ms控制映射。允许短时放大并逐段组合，完整反馈储能尚未证明。

B前的可计算充分条件：

`D_B≤1`且`L_B+max_{0≤s≤T_B}(W_B s+ās²/2)+ε_geom/int≤1`。

最大值检查端点和域内驻点，不能只看末端。若完整恢复段能保证向上加速度至少a_r>0，则从W_B>0开始的停止时间上界W_B/a_r、额外损高充分储备W_B²/(2a_r)。这是充分储备，不能误称必要最小值；必要界需最大可用减速度。

例：W_B=.98m/s、保证a_r=1m/s²，停止≤.98s，充分储备.4802m。按源质量/推力/阻力，θ≤20°、joint误差≤1rad/s、link相对空气速度≤2m/s、Ω≤1000时，每个filter全恢复段保持约**845.936rad/s**即可满足这个向上加速度条件，低于命令上限。未证明真实神经闭环会维持这些域与下界，故不是已验收修复参数区间。

全hold不裁剪也有条件式：捕获误差Ep0/Ev0，body−reference加速度残差≤A_res，则`Ev(t)≤Ev0+t A_res`、`Ep(t)≤Ep0+t Ev0+t²A_res/2`；对**全部**hold前缀满足原1m/s/.5m裁剪界，resume还须加计划外部目标的跳变界。它不单独保证倾角/高度。修复参数如何改变A_res和后段推力/姿态域仍未闭合。

`conditional-maps.json`完整列出A pre-timeout→capture→hold→resume→恢复至B→B及后段的精确有理数例子，同17°峰值下单事件最大损高.51156m、组合完整后段1.584016875m。它反驳只看倾角峰值或事件处重置高度的构造；声明机械/运动学包络可行不等于已证明NN/Gazebo可达，不排除A4。

## 实际用途与最早缺口

新记录中F2在A接回后至B约1.875s，B前向下W已为负；F4间隔约.541–.545s，B前W仍约.94m/s并已损高.446–.574m。它们任务方向和事件间隔都不同，不能把差异纯归因于间隔或神经记忆，但L/D/W映射解释了为何恢复时间和残余下降必须进入组合测试边界。

最具体的实际准入缺口：pose回调丢失物理采样时间且vz用裁剪native回调dt差分，尚不能给出真实COM初始W和测量延迟的硬区间。执行子映射还缺未来ΔA/η浮点预算与自由/机体/cache域不变性。仅补小关节残差不能解决自由plant在事件前离域或全时刻姿态误差。完整证书、全后段修复参数约束及A4排除均未证明；这些缺口没有被用作本轮工程停止理由。

## 全部目标记录的逐前缀核查

`delivery/domain-membership-v2/all-records.json`逐前缀检查16条实际完整记录：本轮10条、旧P12b五条求解来源、旧F4倾角漏判一条；2条准备和24条正式未启动单列。检查保留完整事件/后段，电机物理步逐条核查，旧求解来源同时检查**全任务solver行**，并非只取无接触子集证明全轨迹。

已观测的H/R、callback速度、controller gyro/cache、h/previous/mean以及filter/command/joint投影未见候选界越出；但真正物理COM速度、连续姿态/高度、当前未观测free velocity/约束模式及未来数值误差不能由这些代理补造。每条actual_finite_domain均为**UNKNOWN_FROM_INITIAL_PHYSICAL_STATE_AND_CONTINUOUS_MEMBERSHIP**，首次实际域状态未知从任务起点开始，不能把“投影未出界”写成已覆盖整个失败轨迹。

旧未来实际执行输入驱动的自由经验plant在2.672062669s已到45.219°，越出45°/8rad/s/10m/8m的**停止包络**，早于A；这不是一个已证明精度适用域的边界。新M4数值完整、未触发同包络仍可有14.370°逐时倾角误差。旧漏判、自由重放停止和新预测误差分别保留；矩阵一致性不能把它们升级为覆盖证书。

初态/流动坐标另在`domain-coordinate-extension-v2.json`声明LP水平半径10m、参考目标半径26m（10+8²/(2·RTDEC2)的源码减速位移条件界）、参考速度8m/s及hidden/previous/mean实数box和nominal force2 count。扩展坐标逐前缀同样检查，未改工程门、模型或结果分组；机器舍入与真正物理状态仍不因投影通过而认证。
