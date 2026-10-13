#!/usr/bin/env python3
"""Create a separate analysis directory; retain every previous result unchanged."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main(raw,out,position_reference=None):
    raw=raw.resolve();out=out.resolve();out.mkdir(parents=True,exist_ok=False);(out/'logs').mkdir()
    # A run whose in-runner analysis crashed has no metrics.json; record that instead of failing.
    original=sha(raw/'metrics.json') if (raw/'metrics.json').exists() else None
    for name in ['config.json','metadata.json','validation.json','events.jsonl','telemetry.jsonl','resources.jsonl']:
        if (raw/name).exists():shutil.copy2(raw/name,out/name)
    # Read-only parser input. A hard link preserves content without duplicating disk data.
    os.link(raw/'flight.ulg',out/'flight.ulg')
    if (raw/'gz-motor').is_dir():
        (out/'gz-motor').mkdir()
        for f in sorted((raw/'gz-motor').iterdir()):os.link(f,out/'gz-motor'/f.name)
    if position_reference:
        # Explicit, recorded criterion override for re-verification; the raw config is untouched.
        cfg=json.loads((out/'config.json').read_text());cfg['joint_recovery']['position_reference']=position_reference
        (out/'config.json').write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+'\n')
    for name in ['gz-stats.log','tegrastats.log']:
        if (raw/'logs'/name).exists():shutil.copy2(raw/'logs'/name,out/'logs'/name)
    provenance={'raw_directory':str(raw.relative_to(ROOT)),'raw_metrics_sha256':original,'position_reference_override':position_reference,
        'ulog_sha256':sha(raw/'flight.ulg'),'analysis_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['analyze.py','p0_metrics.py','recovery.py']}}
    command=[sys.executable,str(ROOT/'tools/analyze.py'),str(out)];provenance['command']=command
    p=subprocess.run(command,capture_output=True,text=True);(out/'logs/analysis.log').write_text(p.stdout+p.stderr)
    provenance['exit_code']=p.returncode;provenance['raw_metrics_unchanged']=(sha(raw/'metrics.json') if (raw/'metrics.json').exists() else None)==original
    assert provenance['raw_metrics_unchanged']
    (out/'analysis-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');print(out,p.returncode)
    return p.returncode
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('raw',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--position-reference',help='override joint_recovery.position_reference in the copied config (recorded)');a=p.parse_args()
    raise SystemExit(main(a.raw,a.output,a.position_reference))
