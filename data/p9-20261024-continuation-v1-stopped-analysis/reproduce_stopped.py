#!/usr/bin/env python3
"""Archive-only read-only reproduction; no launch/retry, unique output required.
Replaces only the audit HEAD==execution-commit check with binding of every frozen
file to the recorded Git blobs; published descendant HEAD is permitted. The
flight launch gate is not changed or invoked. All original partial-audit errors
remain, including162/173 counts and missing attempt162.
"""
import argparse,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from p9_model import sha,write

def archive_verify(frozen):
    m=json.loads((frozen/'manifest.json').read_text());r=json.loads((frozen/'receipt.json').read_text())
    assert sha(frozen/'manifest.json')==r['manifest_sha256']
    for d,c in [(frozen,r['commit']),(ROOT/'data/p9-20261024-freeze',m['original_freeze_commit'])]:
        manifest=json.loads((d/'manifest.json').read_text())
        for p,h in manifest['files'].items():
            assert sha(ROOT/p)==h and hashlib.sha256(subprocess.check_output(['git','show',c+':'+p],cwd=ROOT)).hexdigest()==h,p
    assert (ROOT/'data/p9-20261024-preparation/attempts.jsonl').read_bytes().startswith((frozen/'prior-ledger.jsonl').read_bytes())
    assert sha(ROOT/'data/p9-20261024-formal/searches-sealed-before-reference.json')==m['sealed_searches_sha256']
    return m

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    freeze=ROOT/'data/p9-20261024-continuation-v1-freeze';archive_verify(freeze)
    if a.verify_only:print('ARCHIVE BINDING PASS: original27 + continuation59; no simulation');return
    if a.output is None:p.error('--output required unless --verify-only')
    out=a.output.resolve();out.mkdir(exist_ok=False);prep=ROOT/'data/p9-20261024-continuation-v1-preparation'
    sys.path.insert(0,str(prep));spec=importlib.util.spec_from_file_location('archive_audit',prep/'audit_continuation.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.verify_freeze=archive_verify
    code=mod.audit(ROOT/'data/p9-20261024-preparation',freeze,ROOT/'data/p9-20261024-continuation-v1-formal',out/'audit')
    if code!=1:raise RuntimeError('partial whole-batch audit expected FAIL, inspect rather than upgrading acceptance')
    au=json.loads((out/'audit/audit.json').read_text())
    if len(au['runs'])!=59 or not all(x['passed'] for x in au['runs']):raise RuntimeError('completed subset mismatch')
    subprocess.run([sys.executable,str(prep/'build_combined_report.py'),'--formal',str(ROOT/'data/p9-20261024-continuation-v1-formal'),'--audit',str(out/'audit'),'--output',str(out/'report')],cwd=ROOT,check=True)
    script=Path(__file__).resolve().parent/'postanalysis_stopped.py'
    subprocess.run([sys.executable,str(script),'--formal',str(out/'report/analysis-view'),'--report',str(out/'report'),'--audit',str(out/'audit'),'--output',str(out/'postanalysis')],cwd=ROOT,check=True)
    print('REPRODUCED PARTIAL EVIDENCE, whole-batch FAIL retained; no simulation')
if __name__=='__main__':main()
