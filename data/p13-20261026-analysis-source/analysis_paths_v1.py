"""Versioned analysis-only pointer; never relocates or overwrites old evidence."""
import json

def analysis_dir(target):
 p=target/'analysis-pointer-v2.json'
 return target/json.load(open(p))['directory'] if p.exists() else target/'analysis-v1'
