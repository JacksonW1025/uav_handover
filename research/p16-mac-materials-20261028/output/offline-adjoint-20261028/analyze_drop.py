from core import *
def plain(x):
 if isinstance(x,torch.Tensor):return x.detach().numpy().tolist()
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,dict):return {k:plain(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [plain(v) for v in x]
 return x
def predict(rep,variant='AB',alpha=None,bias=None):
 with torch.no_grad():return drop(rep,variant,alpha=None if alpha is None else T(alpha),bias=None if bias is None else T(bias))
def residual(rep,variant,horizon=1.8):
 d,doc,i=load_drop(rep,variant);n=round(horizon/DT);rot=rotor_at(d,i);res=[]
 for k in range(i,i+n-2):
  a,dw=acceleration(T(d['velocity'][k]),T(d['attitude'][k]),T(d['omega'][k]),rot)
  # LP is held at alternate control calls. Compare its 8-ms changes.
  av=(d['velocity'][k+2]-d['velocity'][k])/.008
  aw=(d['omega'][k+1]-d['omega'][k])/.004
  res.append(np.r_[av-a.numpy(),aw-dw.numpy()]);rot=motor(rot,speeds(T(d['action'][k])))
 return np.mean(res,0),np.std(res,0)
def main():
 result={'scope':'P11 F4, local 1.8 s after first observed stale capture. Frozen M2. r1 trains map, r2 evaluates. Plant/model rollouts only; no simulator.'}
 a=T(0.).requires_grad_();b=T(np.zeros(6)).requires_grad_()
 j,y,out,obs,info=drop(alpha=a,bias=b)
 grad=[torch.autograd.grad(z,(a,b),retain_graph=True) for z in j]
 result['baseline']={'predicted':j,'actual':y,'adjoint_alpha':[g[0] for g in grad],'adjoint_bias':[g[1] for g in grad], 'info':info}
 result['finite_difference']=[]
 for e in [1e-4,1e-3,.01,.1,1.]:
  plus=predict(1,alpha=e)[0];minus=predict(1,alpha=-e)[0]
  result['finite_difference'].append({'epsilon':e,'central_slope':(plus-minus)/(2*e),'forward_change':plus-j.detach()})
 result['common_initial_full_effect']=predict(1,alpha=1.)[0]-j.detach()
 result['observed_pairs']=[]
 for rep in [1,2]:
  vals=[]
  for variant in ['AB','REPAIR']:
   pred,actual,_,_,info=predict(rep,variant)
   vals.append({'rep':rep,'variant':variant,'predicted':pred,'actual':actual,'vD':info['initial_speed']*.36})
  result['observed_pairs'].append({'values':vals,'actual_change':vals[1]['actual']-vals[0]['actual'],'model_change_separate_initials':vals[1]['predicted']-vals[0]['predicted']})
 # Each event-mode cell uses local acceleration residuals from r1 only.
 # Compare full six-coordinate mean update against one-coordinate goal-weighted update.
 result['map']=[]
 for variant in ['AB','REPAIR']:
  bias,sd=residual(1,variant)
  b=T(np.zeros(6)).requires_grad_();pred,_,_,_,_=drop(1,variant,bias=b)
  gs=torch.stack([torch.autograd.grad(z,b,retain_graph=True)[0] for z in pred]).numpy()
  old,actual,*_=predict(2,variant)
  allpred=predict(2,variant,bias=bias)[0]
  # Cheap equal-capacity comparator: largest mean next-state residual, with
  # velocity scaled by 1m/s and angular velocity by 1rad/s (explicit scales).
  stat_index=int(np.argmax(np.abs(bias)));stat_bias=np.zeros(6);stat_bias[stat_index]=bias[stat_index]
  stat_pred=predict(2,variant,bias=stat_bias)[0]
  goals=[]
  for g in [0,1]:
   k=int(np.argmax(np.abs(gs[g]*bias)));small=np.zeros(6);small[k]=bias[k]
   new=predict(2,variant,bias=small)[0]
   goals.append({'objective':g,'coordinate':k,'predicted_first_order_correction':gs[g,k]*bias[k],'new_prediction':new,'absolute_error':torch.abs(new-T(actual))})
  result['map'].append({'variant':variant,'train_mean_residual':bias,'train_residual_sd':sd,'gradients':gs,'heldout_old':old,'heldout_actual':actual,'heldout_all_mean':allpred,'old_abs_error':torch.abs(old-T(actual)),'all_mean_abs_error':torch.abs(allpred-T(actual)),'largest_residual_coordinate':stat_index,'heldout_largest_residual':stat_pred,'largest_residual_abs_error':torch.abs(stat_pred-T(actual)),'goal_updates':goals})
 result['clock_robustness']=[{'offset':e,'prediction':drop(1,offset=e)[0].detach()} for e in [-.004,0,.004]]
 (ROOT/'drop-results.json').write_text(json.dumps(plain(result),indent=2))
 print(json.dumps(plain(result),indent=2))
if __name__=='__main__':main()
