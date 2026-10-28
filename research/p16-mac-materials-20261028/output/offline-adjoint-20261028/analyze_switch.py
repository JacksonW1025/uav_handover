from core import *
from analyze_drop import plain
def load(n):return dict(np.load(ROOT/f'switch-{n}.npz')),json.loads((ROOT/f'switch-{n}.json').read_text())
D0,I0=load('N0');D2,I2=load('N2')
def replay(alpha=T(0.),which='N0',mode='constant',residual=None,joint_path=False):
 d,info=load(which);h=T(D0['h'])+alpha*T(D2['h']-D0['h']);prev=T(D0['previous'])+alpha*T(D2['previous']-D0['previous']);hist=prev
 n=int((info['change_us']-int(d['time'][0]))/4000)+1;actions=[]
 residual=T(np.zeros(4)) if residual is None else residual
 for k in range(n):
  if k:hist=(hist+prev)/2 if d['native'][k] else prev
  x=T(d['x'][k if mode=='recorded' else 0])
  if joint_path:x=T(D0['x'][0])+alpha*T(D2['x'][0]-D0['x'][0])
  hh,a=net(h,torch.cat([x,hist]));a=a+residual
  if d['native'][k]:h=hh
  prev=a;actions.append(a)
 motors=.5*(a[[0,2,3,1]]+1)
 classic=T(info['classic_last'])
 if joint_path:classic=T(I0['classic_last'])+alpha*T(np.array(I2['classic_last'])-np.array(I0['classic_last']))
 j=torch.abs(motors-classic).max()
 return j,motors,torch.stack(actions)
def main():
 result={'scope':'First actuator ownership change. Start from first complete input sample at entry+4ms; original activation sample missing. N0/N2 effective memory states interpolated after that first call. Predict next 8ms by held initial exogenous input; recorded-input replay is an independent diagnostic.'}
 a=T(0.).requires_grad_();j,m,acts=replay(a);grad=torch.autograd.grad(j,a)[0]
 result['adjoint']={'baseline':j,'slope':grad}
 result['finite_difference']=[]
 for e in [1e-4,1e-3,.01,.1,1.]:
  jp=replay(T(e))[0];jm=replay(T(-e))[0]
  result['finite_difference'].append({'epsilon':e,'central_slope':(jp-jm)/(2*e),'forward_change':jp-j.detach()})
 result['common_initial_full_effect']=replay(T(1.))[0]-j.detach()
 aa=T(0.).requires_grad_();jj=replay(aa,joint_path=True)[0];gg=torch.autograd.grad(jj,aa)[0]
 result['observed_snapshot_path']={'adjoint_full_change':gg,'central_fd_1e4':(replay(T(.0001),joint_path=True)[0]-replay(T(-.0001),joint_path=True)[0])/.0002,'model_full_change':replay(T(1.),joint_path=True)[0]-jj.detach(),'note':'Interpolates memory, observed exogenous state and incoming classic command. This matches endpoints but is not a pure memory intervention.'}
 result['cases']=[]
 for n,a0 in [('N0',0.),('N2',1.)]:
  pred,info=load(n);const,cm,ca=replay(T(a0),n);recorded,rm,ra=replay(T(a0),n,'recorded')
  result['cases'].append({'case':n,'held_input_prediction':const,'recorded_input_prediction':recorded,'actual':info['measured_motor_step'],'motor_prediction':cm,'actual_motors':info['first_neural_motor'],'action_replay_max_error':np.max(np.abs(ra.detach().numpy()-pred['action'][:len(ra)])),'physical_speed_baseline':info['physical_speed'],'tilt_peak_deg':info['tilt_peak_deg'],'altitude_loss_m':info['altitude_loss_m']})
 result['actual_change']=I2['measured_motor_step']-I0['measured_motor_step']
 # Map cell: additive action-output discrepancy. Train on N0's three calls,
 # apply to N2, using initial input hold in both cases (no N2 fit).
 with torch.no_grad():
  a0=replay(T(0.))[2];res=T(D0['action'][:len(a0)])-a0;mean=res.mean(0)
 b=T(np.zeros(4)).requires_grad_();jb=replay(T(0.),residual=b)[0];g=torch.autograd.grad(jb,b)[0];index=int(torch.argmax(torch.abs(g*mean)))
 small=T(np.zeros(4));small[index]=mean[index]
 old=replay(T(1.),'N2')[0];allp=replay(T(1.),'N2',residual=mean)[0];one=replay(T(1.),'N2',residual=small)[0]
 result['map']={'train_N0_output_mean_residual':mean,'gradient':g,'coordinate':index,'heldout_N2_old':old,'heldout_N2_all_residual':allp,'heldout_N2_goal_coordinate':one,'actual':I2['measured_motor_step'],'old_error':abs(old-I2['measured_motor_step']),'all_error':abs(allp-I2['measured_motor_step']),'goal_error':abs(one-I2['measured_motor_step'])}
 (ROOT/'switch-results.json').write_text(json.dumps(plain(result),indent=2));print(json.dumps(plain(result),indent=2))
if __name__=='__main__':main()
