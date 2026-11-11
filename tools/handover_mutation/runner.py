"""069-seeded mutation runner; inherits physical protection and fresh attempt ledger."""
import argparse,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import handover_100.runner as runner
from handover_100.design import CASES as OLD

class MutationExperiment(runner.Experiment):
    """Optional declared reference end after N has received a fresh external stream."""
    def switch(self, current, target, iteration):
        super().switch(current, target, iteration)
        delay = self.spec.get('active_timeout_after_s')
        if target == 'N' and delay is not None:
            self.pump(float(delay))
            rs = self.latest.get('raptor_status')
            if rs is None or not rs.active or rs.trajectory_setpoint_stale:
                raise RuntimeError('active-timeout setup did not observe fresh neural reference')
            bound = self.native_bound_streaming()
            self.reference_enabled = False
            self.event('mutation_active_reference_end', iteration=iteration,
                       end_bound_px4_us=bound, delay_after_switch_confirmed_s=float(delay),
                       reference_count=self.send_count,
                       observed_active=True, observed_reference_stale=False,
                       purpose='declared external stream completion during neural ownership; natural 200ms timeout')

runner.Experiment = MutationExperiment

def configure(plan_path,case):
    plan=json.loads(Path(plan_path).read_text());spec=copy.deepcopy(plan['cases'][case])
    runner.CASES={case:spec};runner.SEED=spec['seed'];runner.EVIDENCE=ROOT/plan['batch']
    return plan,spec
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--case',required=True);p.add_argument('--attempt',default='a1');p.add_argument('--execute',action='store_true',required=True)
    a=p.parse_args();configure(a.plan,a.case);raise SystemExit(runner.run(a.case,a.attempt))
