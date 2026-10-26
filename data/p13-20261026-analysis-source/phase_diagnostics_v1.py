"""Post-hoc lag/amplitude attribution diagnostic; NEVER replaces official time score."""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'))
from p12c.features import load
from p11.models import tilt
from p9_model import write,sha

def diagnose(target,out):
 out.mkdir(parents=True,exist_ok=False);a=target/'analysis-v1';d=load(target/'run',a);doc=json.load(open(a/'packed-physical/prediction-input.json'));m=json.load(open(a/'measured/measurement.json'));end=min(m['observed_profile_end_s'],doc['plan']['nominal_horizon_profile_s']);A,B=[w[0] for w in doc['plan']['full_source_windows_profile_s']];windows=[('pre_A',max(0,A-1),A),('A_response',A,A+.5),('A_to_B',A,B),('B_response',B,B+.5),('tail',B+.5,end)];angle=np.array([tilt(q) for q in d['attitude']]);rows=[]
 for name in ['M3','M4','M5']:
  tr=np.load(a/f'prediction/{name}.npz')['trace'];pt=tr[:,0];pred=tr[:,7]
  for label,lo,hi in windows:
   # Same interior denominator for every tested lag: no shift-dependent censor.
   x=max(lo,pt[0]+.1);y=min(hi,end,pt[-1]-.1);idx=np.flatnonzero((d['t']>=x)&(d['t']<=y));t=d['t'][idx]
   if len(t)<10:rows.append({'model':name,'window':label,'status':'INSUFFICIENT_COMMON_INTERIOR','requested_window_s':[lo,hi]});continue
   obs=angle[idx];lags=np.arange(-.1,.10001,.004);errors=np.array([np.mean((np.interp(t+lag,pt,pred)-obs)**2) for lag in lags]);j=int(np.argmin(errors));un=np.interp(t,pt,pred)-obs;amplitude=float(np.ptp(obs));p_amp=float(np.ptp(np.interp(t,pt,pred)));rows.append({'model':name,'window':label,'status':'DYNAMIC_SIGNAL' if max(amplitude,p_amp)>=5 else 'WEAK_SIGNAL_LAG_NOT_IDENTIFIED','requested_window_s':[lo,hi],'same_all_lag_interior_s':[float(t[0]),float(t[-1])],'rows':len(t),'unshifted_RMSE_deg':float(np.sqrt(np.mean(un*un))),'best_diagnostic_shift_s':float(lags[j]),'diagnostic_shifted_RMSE_deg':float(np.sqrt(errors[j])),'observed_peak_to_peak_deg':amplitude,'predicted_peak_to_peak_deg':p_amp,'unshifted_window_peak_difference_deg':float(np.max(np.interp(t,pt,pred))-np.max(obs)),'on_lag_search_boundary':j in [0,len(lags)-1]})
 write(out/'diagnostic.json',{'schema':'p13-lag-amplitude-diagnostic-1','id':target.name,'rows':rows,'scope':'posthoc time-shift for error localization only, cannot be heldout forecast performance, causal attribution, initial correction, or replacement of any unshifted score','lag_grid_s':[-.1,.1,.004],'weak_signal_scale_deg':5,'scale_source':'frozen minimal meaningful tilt effect, not tuned to model outcomes','first_8ms_or_4ms_delay_not_automatically_cause':True,'new_SITL':0,'model_parameters_unchanged':True,'source_sha256':sha(Path(__file__))})
if __name__=='__main__':diagnose(Path(sys.argv[1]),Path(sys.argv[2]))
