"""Stage 1 of the site pipeline: find out which packages published a new version.

Fetches the manifest of every package in packages/ and compares its `version` and
`ipkHash.sha256` (and those of the beta manifest, if the package has one) with the state kept in
.stats-cache/manifests.json. Prints a JSON array of the ids that changed; the build only needs to
run when it is not empty. With GITHUB_OUTPUT set (GitHub Actions) it also writes `changed=<json>`
and `any=true|false` there.

A package is changed when it is new to the state, or its version or hash differs. One that left
packages/ is dropped from the state and counts as changed, so the site drops it too. A manifest
that cannot be fetched or parsed counts as unchanged: the stored entry is kept and a warning
logged, so a flaky host never fails the job or triggers a build.

  python -m repogen.check_updates [--force] [--packages DIR] [--state FILE]

`--force` reports every package as changed (the daily full build); it still refreshes the state.
Manifests are fetched fresh, bypassing cache/. Fetching a GitHub release manifest counts as a
download of that asset.
"""
import argparse
import json
import logging
import os
import sys
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.request import url2pathname

import requests

from repogen.pkg_registery import parse_yml_package, load_py_package

log = logging.getLogger('check_updates')

_ROOT = Path(__file__).parent.parent
STATE_FILE = _ROOT / '.stats-cache' / 'manifests.json'
PACKAGES_DIR = _ROOT / 'packages'
_STATE_VERSION = 1
_POOL = 8
# (connect, read) seconds; a connect that hangs is retried rather than waited out.
_TIMEOUT = (8, 30)
_ATTEMPTS = 3

_lock = threading.Lock()
requests_made = 0
bytes_received = 0


def _fetch_manifest(url: str) -> dict:
    """The manifest at `url`, fresh. Raises on any failure."""
    global requests_made, bytes_received
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == 'file':
        with open(url2pathname(parsed.path), encoding='utf-8') as f:
            return json.load(f)
    for attempt in range(_ATTEMPTS):
        try:
            resp = requests.get(url, allow_redirects=True, timeout=_TIMEOUT)
            break
        except (requests.ConnectionError, requests.Timeout):
            if attempt == _ATTEMPTS - 1:
                raise
            log.info('retrying %s', url)
    with _lock:
        requests_made += 1 + len(resp.history)
        bytes_received += len(resp.content)
    resp.raise_for_status()
    manifest = resp.json()
    if not isinstance(manifest, dict):
        raise ValueError('manifest is not a JSON object')
    return manifest


def _identity(manifest: dict) -> dict:
    sha = (manifest.get('ipkHash') or {}).get('sha256')
    return {'version': manifest.get('version'), 'sha256': sha}


def _check(path: Path) -> tuple[str, Optional[dict]]:
    """(package id, fresh state entry), or None for the entry when anything failed."""
    pkgid = path.stem
    try:
        if path.suffix == '.yml':
            _, content = parse_yml_package(path)
        else:
            _, content = load_py_package(path)
        url = content['manifestUrl']
        entry = {**_identity(_fetch_manifest(url)), 'manifestUrl': url}
        if beta_url := content.get('manifestUrlBeta'):
            entry['beta'] = _identity(_fetch_manifest(beta_url))
            entry['betaUrl'] = beta_url
        return pkgid, entry
    except Exception as e:
        log.warning('%s: cannot check manifest, treating as unchanged: %s: %s', pkgid, type(e).__name__, e)
        return pkgid, None


def _load_state(state_file: Path) -> dict[str, dict]:
    try:
        with state_file.open(encoding='utf-8') as f:
            state = json.load(f)
        if state.get('version') == _STATE_VERSION:
            return state['packages']
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    return {}


def _same(old: dict, new: dict) -> bool:
    keys = ('version', 'sha256', 'beta')
    return all(old.get(k) == new.get(k) for k in keys)


def check(packages_dir: Path = PACKAGES_DIR, state_file: Path = STATE_FILE, force: bool = False) -> list[str]:
    """Compare every package's manifest with the stored state, write the new state back and
    return the sorted ids that changed."""
    paths = sorted(p for p in packages_dir.iterdir() if p.is_file() and p.suffix in ('.yml', '.py'))
    old = _load_state(state_file)
    ids = {p.stem for p in paths}
    new: dict[str, dict] = {}
    changed: set[str] = set(old) - ids  # removed packages
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with ThreadPoolExecutor(max_workers=_POOL) as pool:
        results = list(pool.map(_check, paths))
    for pkgid, entry in results:
        if entry is None:
            if pkgid in old:
                new[pkgid] = old[pkgid]
            continue
        if pkgid not in old or not _same(old[pkgid], entry):
            changed.add(pkgid)
        new[pkgid] = {**entry, 'checked_at': now}
    if force:
        changed = ids | changed
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with state_file.open('w', encoding='utf-8') as f:
        json.dump({'version': _STATE_VERSION, 'packages': new}, f, indent=1, sort_keys=True)
    return sorted(changed)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s', stream=sys.stderr)
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--force', action='store_true', help='report every package as changed')
    ap.add_argument('--packages', type=Path, default=PACKAGES_DIR)
    ap.add_argument('--state', type=Path, default=STATE_FILE)
    args = ap.parse_args(argv)
    changed = check(args.packages, args.state, args.force)
    text = json.dumps(changed)
    print(text)
    log.info('%d changed; %d HTTP requests, %d bytes', len(changed), requests_made, bytes_received)
    if out := os.environ.get('GITHUB_OUTPUT'):
        with open(out, 'a', encoding='utf-8') as f:
            f.write(f'changed={text}\nany={"true" if changed else "false"}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
