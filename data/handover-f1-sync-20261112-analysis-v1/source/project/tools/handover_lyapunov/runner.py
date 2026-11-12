"""Prospective V-guided exploration, existing native handover plus classic capture control."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import handover_100.runner as old
from handover_mutation.runner import MutationExperiment
class Experiment(MutationExperiment):
    def switch(self,current,target,iteration):
        if not self.spec.get('classic_capture_control'):
            return super().switch(current,target,iteration)
        quiet=float(self.spec.get('native_quiet_before_request_s',.26))
        self.reference_enabled=False
        self.event('hundred_declared_reference_end_before_request',quiet_s=quiet,purpose='matched quiet prefix before classic AUTO_LOITER capture')
        self.pump(quiet)
        l=self.latest['vehicle_local_position'];att=self.latest['vehicle_attitude']
        bound=self.native_bound_streaming()
        self.event('explore_pre_switch',iteration=iteration,position=[float(l.x),float(l.y),float(l.z)],velocity=[float(l.vx),float(l.vy),float(l.vz)],quaternion=list(map(float,att.q)),nav_state=int(self.latest['vehicle_status'].nav_state),reference_count=self.send_count)
        self.event('lyapunov_classic_capture_requested',end_bound_px4_us=bound,iteration=iteration,purpose='same prefix; continue classic controller with native AUTO_LOITER stop')
        self.mode(self.msgs.VehicleStatus.NAVIGATION_STATE_AUTO_LOITER)
        self.event('lyapunov_classic_capture_confirmed',end_bound_px4_us=self.native_bound_streaming())
    def finish_subject(self,current):
        return super().finish_subject('C' if self.spec.get('classic_capture_control') else current)
old.Experiment=Experiment
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--case',required=True);p.add_argument('--attempt',default='a1');p.add_argument('--execute',action='store_true',required=True);a=p.parse_args()
    plan=json.loads(Path(a.plan).read_text());spec=plan['cases'][a.case];old.CASES={a.case:spec};old.SEED=spec['seed'];old.EVIDENCE=ROOT/plan['batch'];raise SystemExit(old.run(a.case,a.attempt))
