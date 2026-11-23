#!/usr/bin/env python3
"""Read-only baseline checks; never starts SITL or modifies a Lab."""
import ast
import json
from pathlib import Path
import re
import tarfile
ROOT = Path(__file__).resolve().parents[1]
for p in ROOT.rglob('*.py'):
    if '.git' not in p.parts:
        ast.parse(p.read_text(), filename=str(p))
for p in [ROOT/'environment.lock', *ROOT.glob('config/*.json')]:
    json.loads(p.read_text())
for p in ROOT.glob('patches/*.tar.gz'):
    with tarfile.open(p) as archive:
        for m in archive.getmembers():
            assert not Path(m.name).is_absolute() and '..' not in Path(m.name).parts, m.name
            assert not m.issym() and not m.islnk(), m.name
for p in [ROOT/'README.md', *ROOT.glob('docs/*.md')]:
    for link in re.findall(r'\]\(([^)]+)\)', p.read_text()):
        if '://' not in link and not link.startswith('#'):
            assert (p.parent/link.split('#')[0]).exists(), (p, link)
assert not list(ROOT.glob('data/*/flight.ulg'))
print('PASS: Python/JSON, source archive paths, local document links; no Lab/build/flight tested')
