import json,subprocess,sys,concurrent.futures,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO='JacksonW1025/uav_handover'
REF='d0f3924c762e7fbaf5d799ae582a5b59ebb578f0'
def api(endpoint):
    return json.loads(subprocess.check_output(['gh','api',endpoint]))
def tree(sha):
    return api(f'repos/{REPO}/git/trees/{sha}?recursive=1')['tree']
def fetch(path):
    dst=ROOT/'upstream'/path
    if dst.exists() and dst.stat().st_size:return path
    dst.parent.mkdir(parents=True,exist_ok=True)
    if path.endswith(('.npz','.ulg')):
        parent,name=path.rsplit('/',1)
        info=api(f'repos/{REPO}/contents/{parent}?ref={REF}')
        sha=next(x['sha'] for x in info if x['name']==name)
        blob=api(f'repos/{REPO}/git/blobs/{sha}')
        dst.write_bytes(base64.b64decode(blob['content']))
        return path
    for attempt in range(3):
        with dst.with_suffix(dst.suffix+'.partial').open('wb') as f:
            r=subprocess.run(['gh','api','-H','Accept: application/vnd.github.raw+json',f'repos/{REPO}/contents/{path}?ref={REF}'],stdout=f)
        if r.returncode==0:
            dst.with_suffix(dst.suffix+'.partial').replace(dst)
            break
    else: raise RuntimeError(path)
    return path
def many(paths):
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for p in ex.map(fetch,paths): print(p,flush=True)
if __name__=='__main__':many(sys.argv[1:])

