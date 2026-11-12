"""100 preregistered exploratory conditions, one shared simulator seed.
Physical variants are x500 out-of-distribution tests, NOT retrained policies.
"""
import copy, math
from handover_explore.design import k, line, evaluate as old_evaluate, geometry, ZERO
SEED=20261110
CASES={}
def add(family,name,label,why,knots=None,switches=None,**kw):
    n=len(CASES)+1;key=f'{n:03d}_{name}'
    s=dict(case=key,family=family,label=label,rationale=why,source='offboard',seed=SEED,
        duration_s=20.,knots=knots or [k(0,ZERO),k(20,ZERO)],switches=switches or [(3.,'N')],
        reference_kind='continuous_shared_50hz',planned_gaps=False,initial_yaw_deg=0.,altitude_m=3.,
        state_parameters={'MC_RAPTOR_RINI':0,'MC_RAPTOR_RTGT':0,'MC_RAPTOR_RTDEC':2.,'MC_RAPTOR_RREC':0.,'MC_RAPTOR_NCO':0},
        policy_scope='unchanged x500 RAPTOR policy; no retraining or adaptation',single_seed_limit=True)
    s.update(kw);CASES[key]=s;return s

def turn(speed=1.2,sign=1):
    q=1.8/speed
    return [k(0,ZERO),k(2*q,[2,0,0],[speed,0,0]),k(3*q,[3,sign,0],[0,sign*speed,0]),k(4*q,[2,2*sign,0],[-speed,0,0]),k(5*q,[1,sign,0]),k(20,[1,sign,0])]
def rotate(knots,deg):
    c=math.cos(math.radians(deg));s=math.sin(math.radians(deg))
    def r(v):return [c*v[0]-s*v[1],s*v[0]+c*v[1],v[2]]
    return [k(t,r(p),r(v)) for t,p,v in knots]
# 1-12: speed and event phase deliberately crossed, not repeated seeds.
for v in [.4,.9,1.8,2.2]:
    for phase,t in [('acceleration',1.),('cruise',3.),('braking',4.8)]:
        add('linear',f'line_{v}_{phase}',f'{v}m/s直线{phase}交接',f'在同一{v}m/s参考的{phase}阶段进入神经控制，分离速度与加速度/倾角状态；节点速度不当作实际速度。',line(v),[(t,'N')])
# 13-24: signed curvature, temporal scale and entry location.
for v in [.9,1.2,1.5]:
    for sign in [-1,1]:
        for phase,at in [('entry',2.2),('exit',3.8)]:
            add('turn',f'turn_{v}_{sign}_{phase}',f'{v}m/s节点{"左" if sign<0 else "右"}弯{phase}',f'同样紧弯几何用{v}m/s节点速度和{phase}相位，检查曲率、方向对称性及既有滚转历史的影响。',turn(v,sign),[(at*1.8/v,'N')])
# 25-34: vertical motion with/without horizontal demand.
for rate in [.25,.6]:
    for sign in [-1,1]:
        for moving in [False,True]:
            vz=rate*sign;dx=1.8 if moving else 0.
            knots=[k(0,ZERO),k(3,[dx*.5,0,1.5*vz],[.6 if moving else 0.,0,vz]),k(5,[dx,0,2.5*vz]),k(20,[dx,0,2.5*vz])]
            add('vertical',f'vert_{rate}_{sign}_{int(moving)}',f'{rate}m/s{"下降" if sign>0 else "爬升"}{"伴横移" if moving else "垂直"}',f'检查垂向动量和推力余量，比较有无横向运动。计划下降与非计划失高分开报告。',knots,[(3.,'N')],altitude_m=4. if sign>0 else 3.)
for sign in [-1,1]:
    knots=[k(0,ZERO),k(3,[1,0,sign*.8],[.5,0,sign*.5]),k(5,[2,0,0],[.3,0,-sign*.5]),k(7,[2.5,0,-sign*.5]),k(20,[2.5,0,-sign*.5])]
    add('vertical',f'vert_reversal_{sign}',f'垂向反转{sign}', '在爬降反转附近接管，检查相同高度附近不同垂向速度/加速度历史。',knots,[(4.,'N')],altitude_m=4.)
# 35-42: yaw is not a cosmetic label; target-yaw frame changes policy inputs.
for angle in [-90,-45,45,90]:
    for moving in [False,True]:
        add('yaw',f'yaw_{angle}_{int(moving)}',f'转头{angle}度{"横移" if moving else "悬停"}',f'偏航目标旋转{angle}度，比较有无平移对目标坐标系、偏航角速度和姿态瞬态的影响。',line(.9) if moving else None,[(2.,'N')],yaw_sweep_deg=float(angle))
# 43-52: matched smooth knots, distinct geometry/history.
for sign in [-1,1]:
    ellipse=[k(0,ZERO),k(2,[1,0,0],[1,0,0]),k(4,[3,sign,0],[0,sign*.7,0]),k(6,[1,2*sign,0],[-1,0,0]),k(8,[0,sign,0],[0,-sign*.7,0]),k(10,[1,0,0]),k(20,[1,0,0])]
    add('geometry',f'ellipse_{sign}',f'椭圆方向{sign}','连续曲率闭合路径在首弯接管，比较左右转与返回初始区域后的累积误差。',ellipse,[(3.,'N')])
    eight=[k(0,ZERO),k(2,[1,sign,0],[1,0,0]),k(4,[2,0,0],[0,-sign,0]),k(6,[1,-sign,0],[-1,0,0]),k(8,[0,0,0],[0,sign,0]),k(10,[-1,sign,0],[-1,0,0]),k(12,[-2,0,0]),k(20,[-2,0,0])]
    add('geometry',f'eight_{sign}',f'八字首弯{sign}','在曲率即将反转时进入N，追查RAPTOR对曲率记忆与后续反向弯的响应。',eight,[(4.5,'N')])
    slalom=[k(0,ZERO),k(2,[1,sign*.7,0],[.6,0,0]),k(4,[2,-sign*.7,0],[.6,0,0]),k(6,[3,sign*.7,0],[.6,0,0]),k(8,[4,0,0]),k(20,[4,0,0])]
    add('geometry',f'slalom_{sign}',f'蛇形初始侧向{sign}','同一前进方向连续左右曲率反转，观察交接后多次激励的累积与一次瞬态区别。',slalom,[(3.,'N')])
    reversal=[k(0,ZERO),k(2,[1.2*sign,0,0],[1.2*sign,0,0]),k(4,[2.4*sign,0,0]),k(6,[1.2*sign,0,0],[-1.2*sign,0,0]),k(8,ZERO),k(20,ZERO)]
    add('geometry',f'reverse_{sign}',f'沿轴{sign}刹停反向','在速度经过零的反向时刻交接，检查低速度是否掩盖强加速度与控制历史。',reversal,[(4.,'N')])
    stopgo=[k(0,ZERO),k(2,[sign,0,0]),k(4,[sign,0,0]),k(6,[3*sign,0,0],[sign,0,0]),k(8,[4*sign,0,0]),k(20,[4*sign,0,0])]
    add('geometry',f'stopgo_{sign}',f'停走{sign}','先移动再停住再起步，静止接管而后续再加速，检查历史/后续任务触发的广义交接风险。',stopgo,[(3.5,'N')])
# 53-64: controller-side implemented initialization; exit-memory only after valid exit.
for path in ['line','turn']:
    knots=line(1.2) if path=='line' else turn(1.2)
    for mode in [0,1,3,4,'reentry_reset','exit_restore']:
        re=not isinstance(mode,int)
        s=add('history',f'history_{path}_{mode}',f'{path}历史{mode}',f'固定{path}参考，比较已实现的RINI={mode}机制；参数读回和真实memory事件而非名称证明生效。',knots,[(.5,'N'),(2.,'C'),(3.5,'N')] if re else [(3.,'N')])
        if re:s['after_first_exit_rini']=6 if mode=='exit_restore' else 0
        else:s['state_parameters']['MC_RAPTOR_RINI']=mode
# 65-74: native capture versus continuous target, not artificial streaming dropout.
for v in [.5,1.2,2.]:
    for rtgt in [0,1]:
        s=add('process',f'capture_{v}_rtgt{rtgt}',f'{v}m/s原生捕获RTGT{rtgt}',f'经典外部轨迹正常结束后由RAPTOR接管原生目标；比较零速度捕获与已有速度匹配刹停，实际捕获目标须由日志证明。',line(v),[(3.,'N')],handover_reference='native',reference_kind='native_capture_after_classic_stream_end')
        s['state_parameters']['MC_RAPTOR_RTGT']=rtgt
        s['native_quiet_before_request_s']=.26
        s['planned_gaps']=True
        s['rationale']+=' 明确在模式请求前结束外部流并等待0.26秒，使200ms新鲜度过期；这是已声明接管过程变量，须由实际capture activation标志验证。RTGT1只匹配水平速度。'
for v in [1.2,2.]:
    add('process',f'continuous_heading45_{v}',f'{v}m/s对角连续参考','与原生捕获对照：参考在交接前后连续，同时沿对角方向检验每轴裁剪及坐标系方向影响。',rotate(line(v),45),[(3.,'N')],initial_yaw_deg=45.)
for method in ['freeze','brake']:
    add('process',f'reference_{method}',f'接管时外部参考{method}',f'用显式外部{method}参考与原生捕获区分目标建立过程；记录真实状态锚点和实际到达状态，不称物理瞬时冻结。',line(1.2),[(3.,'N')],handover_reference=method,reference_kind=f'external_{method}_from_measured_state')
# 75-84: dwell spacing and direction, each has actual C/N ownership changes.
sequences=[[(.5,'N'),(2.,'C'),(4.,'N')],[(.5,'N'),(2.,'C'),(6.,'N')],[(1.,'N'),(3.,'C'),(3.5,'N')],[(1.,'N'),(3.,'C'),(4.,'N'),(6.,'C'),(7.,'N')],[(.5,'N'),(4.,'C')]]
for path in ['line','turn']:
    for j,seq in enumerate(sequences):
        add('reentry',f'reentry_{path}_{j}',f'{path}往返时序{j+1}',f'序列{seq}改变神经驻留/经典恢复间隔和最终方向；短窗恢复不足记UNKNOWN，后续段不借给前段。',line(1.) if path=='line' else turn(1.),seq)
# 85-94: perturb existing x500 model only, keep trained policy untouched.
variants=[('mass085',{'mass_scale':.85}),('mass115',{'mass_scale':1.15}),('inertia130',{'inertia_scale':1.3}),('motorlag150',{'motor_tau_scale':1.5}),('mass115_inertia130',{'mass_scale':1.15,'inertia_scale':1.3})]
for name,physical in variants:
    for path in ['line','turn']:
        add('physical',f'{name}_{path}',f'x500物理变体{name} {path}',f'已有x500模型施加{physical}，保持神经权重和控制分配不变。这是载荷/惯性/电机响应分布外试验，不是另一个机型已适配。',line(.9) if path=='line' else turn(.9),[(3.,'N')],physical_variant=physical,vehicle='x500 physics perturbation')
# 95-100: mission capture with actual state reported; nominal settings are not balance.
for ref in ['native_capture','external_brake']:
    for j,(alt,yaw) in enumerate([(2.5,0.),(3.5,45.),(4.5,-45.)]):
        add('mission',f'mission_{ref}_{j}',f'Mission {ref} 初始{alt}m/yaw{yaw}',f'真实AUTO_MISSION入口改变起飞高度和初始yaw，比较{ref}接管。Mission导航会改变高度，名义起飞高度不代表实际交接高度。',source='mission',reference_kind=ref,duration_s=16.,altitude_m=alt,initial_yaw_deg=yaw,switches=[(0.,'N')],switch_time_semantics='state-triggered; zero is an index marker, not profile time')
assert len(CASES)==100

def evaluate(spec,t,origin,yaw,velocity=None):
    # Runtime reference substitutions use their own elapsed time and state anchor.
    return old_evaluate(spec,t,origin,yaw,velocity)
