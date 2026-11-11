"""069-seeded mutation runner; inherits physical protection and fresh attempt ledger."""
import argparse,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import handover_100.runner as runner
from handover_100.design import CASES as OLD

def configure(plan_path,case):
    plan=json.loads(Path(plan_path).read_text());spec=copy.deepcopy(plan['cases'][case])
    runner.CASES={case:spec};runner.SEED=spec['seed'];runner.EVIDENCE=ROOT/plan['batch']
    return plan,spec
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--case',required=True);p.add_argument('--attempt',default='a1');p.add_argument('--execute',action='store_true',required=True)
    a=p.parse_args();configure(a.plan,a.case);raise SystemExit(runner.run(a.case,a.attempt))
