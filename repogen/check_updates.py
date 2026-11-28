"""Stage 1 of the site pipeline: find out which packages published a new version.

Fetches the manifest of every package in packages/ and compares its `version` and
`ipkHash.sha256` (and those of the beta manifest, if the package has one) with the entry the
live site publishes in api/apps.json and api/non-free/apps.json. What is compared against is
what is deployed, not a record of earlier checks, so when a build or deploy fails the next check
still sees the difference and tries again. Prints a JSON array of the ids that changed; the build
only needs to run when it is not empty. With GITHUB_OUTPUT set (GitHub Actions) it also writes
`changed=<json>` and `any=true|false` there.

A package is changed when it is not deployed yet, or its version or hash differs from the
deployed one. A deployed package that left packages/ counts as changed, so the site drops it. A
manifest that cannot be fetched or parsed counts as unchanged and a warning is logged, so a flaky
host never triggers a build. A baseline that cannot be fetched is treated as `--force`: a missing
baseline must never skip a build.

  python -m repogen.check_updates [--force] [--packages DIR] [--site URL] [--baseline FILE_OR_DIR]

`--force` reports every package as changed (the daily full build). `--site` is the site whose
published data is the baseline; it defaults to the site's own URL (content/extra/CNAME).
`--baseline` reads a local copy of api/ (a directory holding apps.json and non-free/apps.json)
or a single apps.json instead, for tests. Manifests are fetched fresh, bypassing cache/.
Fetching a GitHub release manifest counts as a download of that asset.
"""
import argparse
import json
import logging
import os
import sys
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from urllib.request import url2pathname

import requests

from repogen.apidata import APPS, POOL_DIRS
from repogen.pkg_registery import parse_yml_package, load_py_package
from repogen.siteurl import siteurl

log = logging.getLogger('check_updates')

_ROOT = Path(__file__).parent.parent
PACKAGES_DIR = _ROOT / 'packages'
DEFAULT_SITE = 'https://repo.webosbrew.org'
_POOL = 4
# (connect, read) seconds; a connect that hangs is retried rather than waited out.
_TIMEOUT = (8, 30)
_ATTEMPTS = 3

_lock = threading.Lock()
requests_made = 0
bytes_received = 0


def _get_json(url: str):
    """The JSON document at `url` (http, https or file), fresh. Raises on any failure."""
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
    return resp.json()


def _fetch_manifest(url: str) -> dict:
    manifest = _get_json(url)
    if not isinstance(manifest, dict):
        raise ValueError('manifest is not a JSON object')
    return manifest


def _identity(manifest: Optional[dict]) -> Optional[dict]:
    if not manifest:
        return None
    sha = (manifest.get('ipkHash') or {}).get('sha256')
    return {'version': manifest.get('version'), 'sha256': sha}


def _check(path: Path) -> tuple[str, Optional[dict]]:
    """(package id, fresh identity), or None for the identity when anything failed."""
    pkgid = path.stem
    try:
        if path.suffix == '.yml':
            _, content = parse_yml_package(path)
        else:
            _, content = load_py_package(path)
        entry = {'manifest': _identity(_fetch_manifest(content['manifestUrl'])), 'beta': None}
        if beta_url := content.get('manifestUrlBeta'):
            entry['beta'] = _identity(_fetch_manifest(beta_url))
        return pkgid, entry
    except Exception as e:
        log.warning('%s: cannot check manifest, treating as unchanged: %s: %s', pkgid, type(e).__name__, e)
        return pkgid, None


def _read_list(location: str) -> list[dict]:
    """All packages of the list at `location` (URL or file URL), following paging.nextUrl."""
    packages: list[dict] = []
    seen = set()
    while location:
        if location in seen:
            raise ValueError(f'paging loops at {location}')
        seen.add(location)
        doc = _get_json(location)
        packages.extend(doc['packages'])
        next_url = (doc.get('paging') or {}).get('nextUrl')
        location = urllib.parse.urljoin(location, next_url) if next_url else None
    return packages


def load_baseline(site: str, baseline: Optional[Path] = None) -> dict[str, dict]:
    """The deployed identity of every published package, by id: from the site's api/ lists of
    every pool, or from a local copy of them. Raises if any list cannot be read."""
    if baseline is not None and baseline.is_file():
        locations = [baseline.resolve().as_uri()]
    elif baseline is not None:
        locations = [baseline.resolve().joinpath(d, APPS).as_uri() for d in POOL_DIRS.values()]
    else:
        site = site.rstrip('/')
        locations = [f'{site}/api/' + (f'{d}/' if d else '') + APPS for d in POOL_DIRS.values()]
    deployed: dict[str, dict] = {}
    for location in locations:
        for pkg in _read_list(location):
            deployed[pkg['id']] = {'manifest': _identity(pkg.get('manifest')),
                                   'beta': _identity(pkg.get('manifestBeta'))}
    return deployed


def check(packages_dir: Path = PACKAGES_DIR, site: str = DEFAULT_SITE, baseline: Optional[Path] = None,
          force: bool = False) -> list[str]:
    """Compare every package's fresh manifest with what is deployed and return the sorted ids
    that changed."""
    paths = sorted(p for p in packages_dir.iterdir() if p.is_file() and p.suffix in ('.yml', '.py'))
    ids = {p.stem for p in paths}
    if force:
        return sorted(ids)
    try:
        deployed = load_baseline(site, baseline)
    except Exception as e:
        log.warning('cannot read the deployed site data, building everything: %s: %s', type(e).__name__, e)
        return sorted(ids)
    changed: set[str] = set(deployed) - ids  # removed packages
    with ThreadPoolExecutor(max_workers=_POOL) as pool:
        results = list(pool.map(_check, paths))
    for pkgid, entry in results:
        if entry is None:
            continue
        if pkgid not in deployed:
            log.info('%s: not deployed yet', pkgid)
            changed.add(pkgid)
        elif deployed[pkgid] != entry:
            log.info('%s: deployed %s, now %s', pkgid, deployed[pkgid], entry)
            changed.add(pkgid)
    for pkgid in sorted(set(deployed) - ids):
        log.info('%s: removed from packages/', pkgid)
    return sorted(changed)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s', stream=sys.stderr)
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--force', action='store_true', help='report every package as changed')
    ap.add_argument('--packages', type=Path, default=PACKAGES_DIR)
    ap.add_argument('--site', default=siteurl() or DEFAULT_SITE, help='site whose published data is the baseline')
    ap.add_argument('--baseline', type=Path, help='local copy of api/ (or one apps.json) instead of --site')
    args = ap.parse_args(argv)
    changed = check(args.packages, args.site, args.baseline, args.force)
    text = json.dumps(changed)
    print(text)
    log.info('%d changed; %d HTTP requests, %d bytes', len(changed), requests_made, bytes_received)
    if out := os.environ.get('GITHUB_OUTPUT'):
        with open(out, 'a', encoding='utf-8') as f:
            f.write(f'changed={text}\nany={"true" if changed else "false"}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
