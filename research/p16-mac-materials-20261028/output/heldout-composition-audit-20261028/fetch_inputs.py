import subprocess,json,concurrent.futures
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REF='d0f3924c762e7fbaf5d799ae582a5b59ebb578f0'
def fetch(path):
 p=ROOT/'upstream'/path
 if p.exists() and p.stat().st_size:return
 p.parent.mkdir(parents=True,exist_ok=True)
 for trial in range(3):
  r=subprocess.run(['gh','api','-H','Accept: application/vnd.github.raw+json',f'repos/JacksonW1025/uav_handover/contents/{path}?ref={REF}'],capture_output=True)
  if r.returncode==0:
   json.loads(r.stdout);p.write_bytes(r.stdout);return
 raise RuntimeError(path)
if __name__=='__main__':
 paths=[f'data/p3-20261015-b01-{d}-{n}-{r}/p3-metrics.json' for d in ['D1','D2','D3'] for n in ['N0','N2','N2s','N3'] for r in [1,2,3]]
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:list(ex.map(fetch,paths))
 print('Downloaded',len(paths),'archived JSON records; no remote execution.')
