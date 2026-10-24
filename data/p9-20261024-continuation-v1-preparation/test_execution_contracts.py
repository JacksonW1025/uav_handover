"""Pure counter/plan contracts. No simulator, ledger write or experiment start."""
from pathlib import Path
import unittest,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_continuation import claim_continuation

ROOT=Path(__file__).resolve().parents[2]
MISSING='C-CZ15-g0.1-reference-P9-Z'
def fixture(n=102):
    return ([{'event':'START_INTENT','id':'dev'+str(i),'budget_class':'development'} for i in range(10)]
            +[{'event':'START_INTENT','id':MISSING if i==101 else 'formal'+str(i),'budget_class':'formal'} for i in range(n)])

class Contracts(unittest.TestCase):
    def test_missing_attempt_cannot_be_retried(self):
        with self.assertRaises(RuntimeError):claim_continuation(fixture(),{'id':MISSING})
    def test_last_permitted_start_is173(self):
        self.assertEqual(claim_continuation(fixture(172),{'id':'never-started'}),173)
    def test_no174th_start(self):
        with self.assertRaises(RuntimeError):claim_continuation(fixture(173),{'id':'never-started'})
    def test_no_new_development(self):
        with self.assertRaises(RuntimeError):claim_continuation(fixture()+[{'event':'START_INTENT','id':'dev11','budget_class':'development'}],{'id':'never-started'})
    def test_exact_unstarted_original_rows(self):
        old=json.loads((ROOT/'data/p9-20261024-freeze/plan.json').read_text())
        new=json.loads((ROOT/'data/p9-20261024-continuation-v1-freeze/plan.json').read_text())
        prefix=[json.loads(x) for x in (ROOT/'data/p9-20261024-continuation-v1-freeze/prior-ledger.jsonl').read_text().splitlines()]
        started={x['id'] for x in prefix if x['event']=='START_INTENT'}
        expected=[r for r in old['runs'] if r['stage'] in ['C-reference','D'] and r['id'] not in started]
        self.assertEqual(new['runs'],expected);self.assertEqual(len(expected),71)
        self.assertNotIn(MISSING,{r['id'] for r in new['runs']})

if __name__=='__main__':unittest.main()
