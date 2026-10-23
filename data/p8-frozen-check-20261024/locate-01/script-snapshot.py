#!/usr/bin/env python3
"""Locate original P8 inputs without modifying evidence, extracting archives or fitting.

Writes a new audit directory; never overwrites an earlier search. Run on the Thor:
  uav_lab/.local/venv/bin/python tools/p8_frozen_locate.py --output <new-directory>
The filesystem search is by name, not an assertion about every file's contents.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 'fe784e62aa5ee8c1ea5cb29fc2ec2d44169c2d02a084130c31342d28d25ba7d4'
PATTERN = re.compile(r'p8[_-](?:frozen\.json|refit|model|predict)|notes/target-interface/experiments/common\.py', re.I)
ARCHIVES = ('.tar', '.tar.gz', '.tgz', '.tar.xz', '.tar.bz2', '.zip', '.7z')
SEARCH_ROOTS = ['/home', '/mnt', '/media', '/opt', '/srv', '/tmp', '/var/tmp',
                '/var/backups', '/target', '/root']
REPOS = [ROOT, Path('/home/car/uav-lab/raptor'), Path('/home/car/uav_sf')]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def command(args, cwd=ROOT):
    r = subprocess.run(args, cwd=cwd, capture_output=True, check=False)
    return {'command': args, 'cwd': str(cwd), 'returncode': r.returncode,
            'stdout': r.stdout.decode(errors='replace'), 'stderr': r.stderr.decode(errors='replace')}


def archive_members(path, data=None):
    """Inspect member names only. Unreadable/unsupported is never reported as absent."""
    source = io.BytesIO(data) if data is not None else path
    try:
        if str(path).lower().endswith('.zip'):
            with zipfile.ZipFile(source) as z:
                names = z.namelist()
        elif str(path).lower().endswith('.7z'):
            return {'status': 'unsupported_7z_not_searched', 'members': None, 'matches': []}
        else:
            with tarfile.open(fileobj=source if data is not None else None,
                              name=None if data is not None else path, mode='r:*') as t:
                names = t.getnames()
        return {'status': 'member_names_searched', 'members': len(names),
                'matches': [n for n in names if PATTERN.search(n)]}
    except (OSError, tarfile.TarError, zipfile.BadZipFile, EOFError) as e:
        return {'status': 'read_error', 'error': str(e), 'members': None, 'matches': []}


def filesystem_search():
    errors, hits, archives, links, counts = [], [], [], [], {}
    for root in SEARCH_ROOTS:
        n = 0
        def onerror(e):
            errors.append({'path': e.filename, 'errno': e.errno, 'error': e.strerror})
        for directory, dirs, files in os.walk(root, onerror=onerror, followlinks=False):
            # Git objects are covered separately; avoid duplicate archive/content scans.
            dirs[:] = [d for d in dirs if d != '.git']
            for name in dirs + files:
                p = Path(directory) / name
                if PATTERN.search(str(p)):
                    hits.append({'path': str(p), 'kind': 'directory' if name in dirs else 'file'})
                if p.is_symlink() and ('uav' in str(p) or PATTERN.search(str(p))):
                    if not p.exists():
                        links.append({'path': str(p), 'target': os.readlink(p), 'status': 'broken_symlink'})
            for name in files:
                n += 1
                p = Path(directory) / name
                # All archive names are inventoried, including policy/build archives.
                if name.lower().endswith(ARCHIVES):
                    archives.append(p)
        counts[root] = n
    return {'roots': SEARCH_ROOTS, 'files_enumerated': counts, 'name_matches': hits,
            'errors': errors, 'broken_research_symlinks': links,
            'scope': 'all accessible names, no symlink traversal; .git handled separately'}, archives


def inspect_archives(paths):
    rows, cache = [], {}
    for p in sorted(paths):
        try:
            if p.stat().st_size > 64 * 1024 * 1024 or str(p).endswith('.7z'):
                rows.append({'path': str(p), 'bytes': p.stat().st_size,
                             'status': 'unsupported_7z_not_searched' if str(p).endswith('.7z')
                             else 'over_64MiB_not_searched', 'matches': []})
                continue
            digest = file_sha(p)
            if digest not in cache:
                cache[digest] = archive_members(p)
            rows.append({'path': str(p), 'bytes': p.stat().st_size, 'sha256': digest, **cache[digest]})
        except OSError as e:
            rows.append({'path': str(p), 'status': 'read_error', 'error': str(e)})
    return rows


def git_search(repo, output):
    if not (repo / '.git').exists():
        return {'repository': str(repo), 'status': 'not_present'}
    refs = command(['git', 'show-ref'], repo)
    history = command(['git', 'rev-list', '--all', '--reflog', '--objects'], repo)
    lines = history['stdout'].splitlines()
    named = [l for l in lines if ' ' in l and PATTERN.search(l.split(' ', 1)[1])]
    # Archived historical source bundles, including ones no longer in the worktree.
    archived = {l.split(' ', 1)[0]: l.split(' ', 1)[1] for l in lines
                if ' ' in l and l.lower().endswith(ARCHIVES)}
    bundles = []
    for oid, name in archived.items():
        size = command(['git', 'cat-file', '-s', oid], repo)
        if int(size['stdout']) > 64 * 1024 * 1024:
            bundles.append({'oid': oid, 'path': name, 'status': 'over_64MiB_not_searched'})
            continue
        data = subprocess.run(['git', 'cat-file', 'blob', oid], cwd=repo,
                              capture_output=True, check=True).stdout
        bundles.append({'oid': oid, 'path': name, 'sha256': sha(data), **archive_members(name, data)})
    unreachable = []
    if repo == ROOT:
        # Connectivity mode avoids rereading multi-GB raw-flight packs; includes dangling objects.
        fsck = command(['git', 'fsck', '--connectivity-only', '--no-reflogs', '--unreachable'], repo)
        (output / 'git-unreachable.txt').write_text(fsck['stdout'] + fsck['stderr'])
        for line in fsck['stdout'].splitlines():
            parts = line.split()
            if len(parts) != 3 or parts[0] != 'unreachable':
                continue
            _, kind, oid = parts
            if kind == 'tree':
                tree = command(['git', 'ls-tree', '-r', '--name-only', oid], repo)
                unreachable.append({'oid': oid, 'kind': kind,
                                    'name_matches': [n for n in tree['stdout'].splitlines() if PATTERN.search(n)]})
            elif kind == 'blob':
                size = int(command(['git', 'cat-file', '-s', oid], repo)['stdout'])
                row = {'oid': oid, 'kind': kind, 'bytes': size}
                if size <= 64 * 1024 * 1024:
                    data = subprocess.run(['git', 'cat-file', 'blob', oid], cwd=repo,
                                          capture_output=True, check=True).stdout
                    row.update(sha256=sha(data), expected_hash_match=sha(data) == EXPECTED)
                else:
                    row['status'] = 'over_64MiB_not_hashed'
                unreachable.append(row)
        fsck.pop('stdout')
    else:
        fsck = {'status': 'not_run_for_associated_repo'}
    return {'repository': str(repo), 'refs': refs, 'history_returncode': history['returncode'],
            'history_stderr': history['stderr'], 'object_path_records': len(lines),
            'name_matches': named, 'archive_objects': bundles, 'unreachable': unreachable, 'fsck': fsck}


def handover():
    p = Path('/home/car/.claude/projects/-home-car-uav-handover/14bf78b5-987e-4bec-a7d3-f2e6732bac7f.jsonl')
    if not p.exists():
        return {'path': str(p), 'status': 'not_available_on_this_machine'}
    records = []
    for i, line in enumerate(p.open(), 1):
        r = json.loads(line)
        if r.get('type') != 'user':
            continue
        content = r.get('message', {}).get('content', [])
        if isinstance(content, list):
            content = '\n'.join(x.get('text', '') for x in content if x.get('type') == 'text')
        if 'p8_frozen.json' not in content:
            continue
        selected = [s for s in content.splitlines() if any(x in s for x in
                    ['p8-refit/README.md', '项目那边另存了一份', '项目那边没有这个仓库的写权限'])]
        records.append({'line': i, 'timestamp_utc': r.get('timestamp'),
                        'message_sha256': sha(content.encode()), 'relevant_paragraphs': selected})
    return {'path': str(p), 'session_sha256': file_sha(p), 'records': records,
            'note': 'Quoted handover claims are leads, not verified model artifacts or validation results.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    fs, archives = filesystem_search()
    print('Filesystem search complete; inspecting archives.', flush=True)
    archive_rows = inspect_archives(archives)
    print('Archive search complete; inspecting Git history.', flush=True)
    result = {'expected_frozen_sha256': EXPECTED, 'filesystem': fs,
              'archives': archive_rows, 'git': [git_search(r, out) for r in REPOS],
              'handover': handover(), 'script_sha256': file_sha(Path(__file__)),
              'limits': ['No access to other machines; project-side hostname and absolute path unknown.',
                         'Permission errors, broken links, unsupported archives and size limits are explicit.',
                         'No fitted model, prediction or skip rule is generated by this script.']}
    (out / 'input-search.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    with (out / 'archive-inventory.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['path', 'bytes', 'sha256', 'status', 'members', 'matches', 'error'])
        w.writeheader()
        for row in archive_rows:
            w.writerow({**row, 'matches': json.dumps(row.get('matches', []))})
    print(json.dumps({'archives': len(archive_rows), 'errors': len(fs['errors']),
                      'name_matches': fs['name_matches']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
