"""Verify source generator does not modify an already prepared checkout."""
from pathlib import Path
import hashlib,subprocess
root=Path(__file__).resolve().parents[1];sources=[root/'uav_lab/.local/checkouts'/('px4-'+variant) for variant in ['classic','raptor']]
def snapshot():
    result={}
    for source in sources:
        files=subprocess.check_output(['git','-C',str(source),'ls-files','--cached','--others','--exclude-standard','-z']).decode().strip('\0').split('\0')
        result.update({str(source.name)+'/'+n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in files if n and (source/n).is_file() and not (source/n).is_symlink()})
    return result
before=snapshot()
for _ in range(2):subprocess.run(['python3',str(root/'tools/apply_research.py')],check=True)
after=snapshot();changed=[n for n in set(before)|set(after) if before.get(n)!=after.get(n)]
assert not changed,changed
print('PASS: two applications preserve all source bytes')
