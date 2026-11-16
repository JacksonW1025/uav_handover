"""Exploratory normal-use profiles. No gaps, no policy/internal-state changes."""
import math
from cn_single.design import hermite
SEED=20261110
ZERO=[0.,0.,0.]
def k(t,p,v=None):return (float(t),list(map(float,p)),list(map(float,v or ZERO)))
def line(v):
    return [k(0,ZERO),k(2,[v,0,0],[v,0,0]),k(4,[3*v,0,0],[v,0,0]),k(6,[4*v,0,0]),k(18,[4*v,0,0])]
def turn(sign):
    return [k(0,ZERO),k(3,[2,0,0],[.9,0,0]),k(5,[3,sign,0],[0,sign*.9,0]),k(7,[2,2*sign,0],[-.9,0,0]),k(9,[1,sign,0]),k(18,[1,sign,0])]
CASES={
 'hover':dict(label='悬停交接',knots=[k(0,ZERO),k(18,ZERO)],switches=[(3.,'N')]),
 'slow_line':dict(label='慢速直线交接',knots=line(.6),switches=[(3.,'N')]),
 'fast_line':dict(label='较快直线交接',knots=line(1.5),switches=[(3.,'N')]),
 'accelerating':dict(label='加速中交接',knots=line(1.5),switches=[(1.,'N')]),
 'braking':dict(label='减速中交接',knots=line(1.5),switches=[(4.8,'N')]),
 'left_turn':dict(label='左转中交接',knots=turn(-1),switches=[(4.,'N')]),
 'right_turn':dict(label='右转中交接',knots=turn(1),switches=[(4.,'N')]),
 'climbing':dict(label='爬升中交接',knots=[k(0,ZERO),k(3,[.6,0,-.8],[.3,0,-.5]),k(6,[1.2,0,-1.8]),k(18,[1.2,0,-1.8])],switches=[(3.,'N')]),
 'descending':dict(label='下降中交接',knots=[k(0,ZERO),k(3,[.6,0,.5],[.3,0,.35]),k(6,[1.2,0,1.2]),k(18,[1.2,0,1.2])],switches=[(3.,'N')],note='计划下降1.2m；固定1m失高判据照报，须与相对参考高度误差分开'),
 'yawing':dict(label='偏航转头中交接',knots=[k(0,ZERO),k(18,ZERO)],switches=[(2.,'N')],yaw_sweep_deg=90.),
 'moving_n_to_c':dict(label='神经运动中交还经典',knots=line(1.2),switches=[(.5,'N'),(3.,'C')]),
 'reentry':dict(label='短间隔往返再入',knots=turn(1),switches=[(2.,'N'),(4.,'C'),(5.5,'N')]),
 'mission_native':dict(label='Mission运动中原生捕获',source='mission',reference_kind='native_capture',switches=[(0.,'N')]),
 'mission_external':dict(label='Mission运动中连续外部刹停',source='mission',reference_kind='external_brake',switches=[(0.,'N')]),
}
# A small adaptive extension after the original 14 completed. Same controller,
# continuous reference and physical protection; do not continue to a stronger
# corner if the preceding corner already triggers protection.
CASES.update({
 'mission_native_descending':dict(label='补充：Mission下降阶段原生捕获',source='mission',reference_kind='native_capture',switches=[(0.,'N')],extension=True,trigger_vertical='descending',note='任一有效Mission航段，水平速度>=0.6m/s且实际NED vz>=0.5m/s持续0.2s；a1保留原第二航段限制失败，a2改为关注真实下降'),
 'fast_2p5':dict(label='补充：2.5m/s直线交接',knots=[k(0,ZERO),k(1.5,[1.875,0,0],[2.5,0,0]),k(3,[5.625,0,0],[2.5,0,0]),k(4.5,[7.5,0,0]),k(18,[7.5,0,0])],switches=[(2.25,'N')],extension=True),
})
for speed in (1.8,2.0):
    scale=1.8/speed
    name='tight_turn_'+str(speed).replace('.','p')
    CASES[name]=dict(label='补充：紧转弯'+str(speed)+'m/s节点速度',
        knots=[k(0,ZERO),k(2*scale,[2,0,0],[speed,0,0]),k(3*scale,[3,1,0],[0,speed,0]),k(4*scale,[2,2,0],[-speed,0,0]),k(5*scale,[1,1,0]),k(18,[1,1,0])],
        switches=[(2.5*scale,'N')],extension=True,
        note='节点速度不是全程恒速；应使用实际接管速度/姿态和完整轨迹，不用标签速度替代观测')

for control in ('classic_only','raptor_preentered'):
    key='tight_control_'+control
    CASES[key]=dict(CASES['tight_turn_1p8'])
    CASES[key].update(label='紧弯对照：'+('经典全程' if control=='classic_only' else 'RAPTOR提前稳定进入'),
        control_baseline=control,switches=[],neural_before_profile=control=='raptor_preentered',
        note='同tight_turn_1p8参考，经典全程无主体切换；提前神经对照在参考hold中正常进入后等3秒。非匹配因果证据。')

for name,s in CASES.items():
    s.update(case=name,source=s.get('source','offboard'),seed=SEED,duration_s=18. if s.get('source')!='mission' else 12.,
             reference_kind=s.get('reference_kind','continuous_shared_50hz'),planned_gaps=False,
             state_parameters={'MC_RAPTOR_RINI':0,'MC_RAPTOR_RTGT':0,'MC_RAPTOR_RREC':0,'MC_RAPTOR_NCO':0})

def evaluate(spec,t,origin,yaw,velocity=None):
    t=max(0.,float(t))
    if spec['source']=='mission':
        v=list(velocity or ZERO);knots=[k(0,ZERO,v),k(2,[.7*v[0],.7*v[1],.4*v[2]]),k(12,[.7*v[0],.7*v[1],.4*v[2]])]
    else:knots=spec['knots']
    if t>=knots[-1][0]:p=[origin[j]+knots[-1][1][j] for j in range(3)];v=ZERO[:];a=ZERO[:]
    else:
        lo,hi=next((x,y) for x,y in zip(knots,knots[1:]) if x[0]<=t<y[0])
        rows=[hermite(lo[1][j],lo[2][j],hi[1][j],hi[2][j],hi[0]-lo[0],t-lo[0]) for j in range(3)]
        p=[origin[j]+rows[j][0] for j in range(3)];v=[r[1] for r in rows];a=[r[2] for r in rows]
    y=yaw;yr=0.
    if spec.get('yaw_sweep_deg'):
        yy,yr,_=hermite(0.,0.,math.radians(spec['yaw_sweep_deg']),0.,4.,min(t,4.));y+=yy
        if t>=4.:yr=0.
    return p,v,a,y,yr

def geometry(spec,origin=(0.,0.,-3.),yaw=0.,velocity=None):
    rows=[evaluate(spec,i*.01,origin,yaw,velocity) for i in range(int(spec['duration_s']*100)+1)]
    return dict(max_reference_radius_m=max(math.hypot(*r[0][:2]) for r in rows),
        min_reference_altitude_m=min(-r[0][2] for r in rows),max_reference_altitude_m=max(-r[0][2] for r in rows),
        max_reference_speed_m_s=max(math.sqrt(sum(x*x for x in r[1])) for r in rows),
        max_reference_acceleration_m_s2=max(math.sqrt(sum(x*x for x in r[2])) for r in rows))
