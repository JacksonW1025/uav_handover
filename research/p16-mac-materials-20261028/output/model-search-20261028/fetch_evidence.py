"""Read historical artifacts only; never executes remote experiment code."""
from pathlib import Path
import subprocess,json,concurrent.futures,hashlib
ROOT=Path(__file__).resolve().parent
REF='d0f3924c762e7fbaf5d799ae582a5b59ebb578f0'
def fetch(path):
 out=ROOT/'upstream'/path
 if out.exists() and out.stat().st_size:return out
 out.parent.mkdir(parents=True,exist_ok=True)
 for trial in range(3):
  p=subprocess.run(['gh','api','-H','Accept: application/vnd.github.raw+json',f'repos/JacksonW1025/uav_handover/contents/{path}?ref={REF}'],capture_output=True)
  if p.returncode==0:out.write_bytes(p.stdout);return out
 raise RuntimeError(path+': '+p.stderr.decode()[:250])
if __name__=='__main__':
 s=(ROOT.parent.parent/'app/data/experiment-stages.ts').read_text();stages=json.JSONDecoder().raw_decode(s.split('export const stages: Stage[] = ',1)[1])[0]
 paths=list(dict.fromkeys(x['report'] for x in stages if x.get('report')))
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:outputs=list(ex.map(fetch,paths))
 (ROOT/'source_manifest.json').write_text(json.dumps(dict(ref=REF,files=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in outputs]),indent=2))
 print('Read',len(outputs),'archived reports.')
