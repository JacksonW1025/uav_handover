# P14H 接口与适用域

实验平台：原P13/P14R固定轻量canonical记录，加P14HSnapshot被动post-EKF全交叉P。权重、4ms物理步、真实latest-value消费、安全保护不变。源码差异剥离、普通二进制/插件/policy副本、构建及异常退出格式测试见data/p14h-20261027。没有关闭观测平台等价主张。

|状态/接口|来源与实际实现|本轮模型/限制|
|---|---|---|
|物理COM/body/q/omega|同physics step Pre/Post，P13直接记录|源角/平移/转速模型；保留杆臂与真实关节残差，未来SERVO误差未认证|
|EKF全P及state|每次_ekf.update成功后、LP publish前，25 nominal /24 covariance，自然跨项|直接记录完整P，不以对角代替；aiding queues、辅助滤波状态仍缺，不能完整恢复EKF|
|OP与缓存|source CALC/FUSE环与sample身份、真实LP/att缓存戳|初始OP callback完成是显式条件投影，非原子完整快照；未来PRE_COMPLETE、LP后att队列|
|下采样|ImuDownSampler .9avg+.1dt，roundf、count/accum严格判据|决策和20项timestamp队列由过去全dt恢复；FUSION_PRE是开始，原v2字段“completed”命名误导另有scope-v3更正；payload/aiding不补造|
|gyro|物理机体系、源biquad及sensor/output bias|与物理q/估计q/LP导航原点分别保存；禁止用yaw差旋转LP导航速度|
|读取/提交|真实pre-read、force-sync2、latest pending、capture在duplicate拒绝之前|两侧release真实走读取/严格timeout/capture/resume；处理包含运输/cache总效应|
|神经/动作/执行|h、previous、mean/count、pending command、filter/joint|无hidden/history reset；输出调用与GRU提交分离；执行latest-value下一物理消费|
|历史任务量|H0、L、D、W，LP与COM分列|D单调、失败不可撤销；capture/resume/边拼接不重置|

新记录器：131072×4320字节有界mmap，sequence、count/drop/error。complete=0为进程寿命设计，必须结合所属producer退出、文件长度/连续性/覆盖/hash，不能把header0当完整性结论。不声称检测所有OS写回错误。

源模型H1是一个条件名义模型。未知未来融合校正和生产调度没有有限硬覆盖预算，有限样本最大值不升级为未来界。H0完整反馈管束及W同域面板单列；H1因果队列中心预测和点拼接不能代替联合域包含证明。

地图边输入：模式、联合初态、事件A/B时刻、reference/history/cache规则、时钟分支、模型误差域。输出：运动中心、逐前缀倾角/LP/COM余量、D和后继内部状态、UNKNOWN来源、成本。机器实例map-v1/result/edge.json；实际同源联合域尝试sets-AB-v1。失精度前缀与失域后的TOP明确分界。

W为完整前缀输出的固定分支pullback，856维、192调用：Qpre[k]=Jkᵀ(CpostkᵀCpostk+Qpre[k+1])Jk。采用PSD半范数，不把最大特征值或瞬时h范数称恢复能力。非线性r、时序跳变和浮点预算未闭合时不能用此恒等式推出实际安全。
