"""Frozen local recovery update: a discrepancy in W dynamics, not label fit.
Only legal post-A information updates a bounded acceleration interval; successor
history and old D remain intact. Coefficient is empirical until separately bounded.
"""
import numpy as np

def local(prediction,snapshot,context):
 z=np.asarray(prediction['full_prefix']);t=snapshot['profile_s'];k=max(0,min(len(z)-1,int(np.searchsorted(z[:,0],t))));predW=float(z[k,3]);predL=float(z[k,1]);window=max(.004,t-(context['A_start']+context['A_duration']));raw=(snapshot['LP_W_m_s']-predW)/window
 return dict(schema='P15-local-recovery-v1',vertical_acceleration_residual=float(np.clip(raw,-.5,.5)),unclipped_acceleration_residual=float(raw),measured_W=snapshot['LP_W_m_s'],predicted_W=predW,measured_L=float(snapshot['position'][2]+context['H0_LP']),predicted_L=predL,recovery_window_s=window,source='one legal postA observation against its own preA prediction; bounded empirical discrepancy for recovery mode only',not_future_hard_bound=True,no_history_or_D_reset=True,scope='next nominal recovery interval; full current state reinitialized from observed history, not scalar label offset')
