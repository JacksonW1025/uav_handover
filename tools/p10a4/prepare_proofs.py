#!/usr/bin/env python3
"""Export three declared candidate traces for independent exact A4 auditing."""
import argparse
from pathlib import Path
from bench import load
from theory import candidate
from data import save,write,sha,ROOT

def main(out):
    out.mkdir(parents=True,exist_ok=False);b=load()
    for name,eps in [('T0',0.),('C04',.001),('CR06',.00001)]:
        case=next(c for c in b['config']['theory']['repair_candidates'] if c['id']==name)
        result,arrays=candidate(b,case,eps,keep=True);d=out/name;d.mkdir()
        save(d/'trace.npz',arrays);write(d/'candidate.json',result)
        write(d/'manifest.json',{'trace_sha256':sha(d/'trace.npz'),'candidate_sha256':sha(d/'candidate.json'),
            'config_sha256':sha(ROOT/'config/p10_a4.json'),'source_A3_manifest_sha256':sha(ROOT/'data/p10-20261025-a3/source-08/manifest.json')})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);main(p.parse_args().output)
