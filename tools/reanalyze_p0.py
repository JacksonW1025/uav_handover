#!/usr/bin/env python3
"""Create a separate analysis directory; retain every previous result unchanged."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main(raw,out):
    raw=raw.resolve();out=out.resolve();out.mkdir(parents=True,exist_ok=False);(out/'logs').mkdir()
    original=sha(raw/'metrics.json')
    for name in ['config.json','metadata.json','validation.json','events.jsonl','telemetry.jsonl','resources.jsonl']:
        if (raw/name).exists():shutil.copy2(raw/name,out/name)
    # Read-only parser input. A hard link preserves content without duplicating disk data.
    os.link(raw/'flight.ulg',out/'flight.ulg')
    for name in ['gz-stats.log','tegrastats.log']:
        if (raw/'logs'/name).exists():shutil.copy2(raw/'logs'/name,out/'logs'/name)
    provenance={'raw_directory':str(raw.relative_to(ROOT)),'raw_metrics_sha256':original,
        'ulog_sha256':sha(raw/'flight.ulg'),'analysis_code_sha256':{n:sha(ROOT/'tools'/n) for n in ['analyze.py','p0_metrics.py','recovery.py']}}
    command=[sys.executable,str(ROOT/'tools/analyze.py'),str(out)];provenance['command']=command
    p=subprocess.run(command,capture_output=True,text=True);(out/'logs/analysis.log').write_text(p.stdout+p.stderr)
    provenance['exit_code']=p.returncode;provenance['raw_metrics_unchanged']=sha(raw/'metrics.json')==original
    assert provenance['raw_metrics_unchanged']
    (out/'analysis-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');print(out,p.returncode)
    return p.returncode
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('raw',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    raise SystemExit(main(a.raw,a.output))
