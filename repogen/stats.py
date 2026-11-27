"""GitHub download and star counts of packages, shown on app pages and in the API as `stats`.

The source repository is the one the package's manifest URL (or, failing that, the manifest's
ipk URL) releases from. `stars` is the repository's star count; `downloads` is the sum of
`download_count` over every `.ipk` release asset of every release, so manifests and source
archives do not inflate it. Update downloads are counted too.

Counts are cached in cache/stats.json, keyed by `owner/repo`. In CI (`CI` set) every build
fetches fresh counts. Locally the cache is used whatever its age, and a repository missing
from it is fetched only when GITHUB_TOKEN is set; without one it is skipped silently, since
anonymous API access allows just 60 requests an hour. A failed request logs a warning and
leaves that repository without stats; it never fails the build. Counts come from the GraphQL API,
which always needs a token, many repositories per request.

Run `python -m repogen.stats` to refresh the whole local cache. It reads the token from
GITHUB_TOKEN, so `GITHUB_TOKEN=$(gh auth token) python -m repogen.stats` works.
"""
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent / 'cache' / 'stats.json'
# Bump when the cached shape changes.
_CACHE_VERSION = 1
_API = 'https://api.github.com'
_RELEASE_URL = re.compile(r'^https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s]+)/releases/', re.IGNORECASE)

_session = requests.Session()
_cache: Optional[dict[str, dict]] = None
# Repositories already looked up in this process, so a shared repo is fetched once per build.
_resolved: dict[str, Optional[dict]] = {}


def compact_number(value: int) -> str:
    """A count in a few characters for page display: 950, 1.2k, 742k, 1.2M."""
    for limit, suffix in ((1_000_000, 'M'), (1_000, 'k')):
        if value >= limit:
            scaled = value / limit
            # Two significant digits below 10, none after the point from there on; a value
            # that rounds up to the next unit (999999) moves to it.
            text = f'{scaled:.1f}' if scaled < 10 else f'{scaled:.0f}'
            if text == '1000' and suffix == 'k':
                return '1M'
            return text.removesuffix('.0') + suffix
    return str(value)


def repo_of(info: dict) -> Optional[str]:
    """`owner/repo` the package releases from, or None when it is not a GitHub release."""
    candidates = [info.get('manifestUrl'), (info.get('manifest') or {}).get('ipkUrl')]
    for url in candidates:
        m = _RELEASE_URL.match(url) if isinstance(url, str) else None
        if m:
            return f'{m.group(1)}/{m.group(2)}'
    return None


def _token() -> Optional[str]:
    return os.environ.get('GITHUB_TOKEN') or None


def _load_cache() -> dict[str, dict]:
    global _cache
    if _cache is None:
        _cache = {}
        try:
            with _CACHE_FILE.open(encoding='utf-8') as f:
                cached = json.load(f)
            if cached.get('version') == _CACHE_VERSION:
                _cache = cached['repos']
        except (OSError, ValueError, KeyError, AttributeError):
            pass
    return _cache


def _save_cache(repos: dict[str, dict]):
    try:
        _CACHE_FILE.parent.mkdir(exist_ok=True)
        with _CACHE_FILE.open('w', encoding='utf-8') as f:
            json.dump({'version': _CACHE_VERSION, 'repos': repos}, f, indent=1, sort_keys=True)
    except OSError:
        pass


_GRAPHQL = f'{_API}/graphql'
# 100 releases of 50 assets each is the most a repository can add to a query's node budget
# (500,000), so keep batches small enough to stay well under it and under the time limit.
_BATCH = 5
_ATTEMPTS = 3
_REPO_FIELDS = """stargazerCount
    releases(first: 100%s) {
      pageInfo { hasNextPage endCursor }
      nodes { id releaseAssets(first: 50) { pageInfo { hasNextPage endCursor } nodes { name downloadCount } } }
    }"""

# For reporting how heavy a refresh is.
requests_made = 0
last_rate_limit: Optional[dict] = None
_errors: list = []


def _query(query: str, variables: Optional[dict] = None) -> dict:
    """One GraphQL request. Returns the `data` object, which may hold nulls for repositories
    that errored; raises on HTTP failure or when there is no data at all."""
    global requests_made, last_rate_limit
    token = _token()
    if not token:
        raise RuntimeError('GraphQL needs GITHUB_TOKEN')
    requests_made += 1
    resp = _session.post(_GRAPHQL, json={'query': query, 'variables': variables or {}}, timeout=60,
                         headers={'Authorization': f'Bearer {token}'})
    resp.raise_for_status()
    body = resp.json()
    data = body.get('data')
    if not data:
        raise RuntimeError(f'GraphQL error: {body.get("errors")}')
    _errors[:] = body.get('errors') or []
    if data.get('rateLimit'):
        last_rate_limit = data['rateLimit']
    return data


def _ipk_downloads(assets: list) -> int:
    return sum(int(a.get('downloadCount') or 0) for a in assets if a and (a.get('name') or '').lower().endswith('.ipk'))


def _more_assets(release_id: str, cursor: str) -> int:
    total = 0
    while cursor:
        data = _query('query($id: ID!, $c: String) { rateLimit { cost remaining } node(id: $id) { ... on Release {'
                      ' releaseAssets(first: 50, after: $c) { pageInfo { hasNextPage endCursor }'
                      ' nodes { name downloadCount } } } } }', {'id': release_id, 'c': cursor})
        assets = data['node']['releaseAssets']
        total += _ipk_downloads(assets['nodes'])
        cursor = assets['pageInfo']['endCursor'] if assets['pageInfo']['hasNextPage'] else None
    return total


def _summarise(repo: str, node: dict) -> dict:
    """Stats out of one repository node, following release and asset pages beyond the first."""
    owner, name = repo.split('/', 1)
    downloads = 0
    releases = node['releases']
    while True:
        for release in releases['nodes']:
            if not release:
                continue
            assets = release['releaseAssets']
            downloads += _ipk_downloads(assets['nodes'])
            if assets['pageInfo']['hasNextPage']:
                downloads += _more_assets(release['id'], assets['pageInfo']['endCursor'])
        if not releases['pageInfo']['hasNextPage']:
            break
        data = _query('query($o: String!, $n: String!, $c: String) { rateLimit { cost remaining }'
                      ' repository(owner: $o, name: $n) { releases(first: 100, after: $c) {'
                      ' pageInfo { hasNextPage endCursor } nodes { id releaseAssets(first: 50) {'
                      ' pageInfo { hasNextPage endCursor } nodes { name downloadCount } } } } } }',
                      {'o': owner, 'n': name, 'c': releases['pageInfo']['endCursor']})
        releases = data['repository']['releases']
    return {'stars': int(node['stargazerCount']), 'downloads': downloads}


def fetch_many(repos: list[str]) -> dict[str, dict]:
    """Stats of repositories from the GraphQL API, a batch of repositories per request.

    Returns `owner/repo` -> a dict with `stars` and `downloads`. A repository that does not
    exist (renamed, deleted, private), or whose batch failed, is left out with a warning."""
    result: dict[str, dict] = {}
    for start in range(0, len(repos), _BATCH):
        batch = repos[start:start + _BATCH]
        fields = '\n'.join(
            f'r{i}: repository(owner: {json.dumps(r.split("/", 1)[0])}, name: {json.dumps(r.split("/", 1)[1])}) '
            f'{{ {_REPO_FIELDS % ""} }}' for i, r in enumerate(batch))
        pending = list(enumerate(batch))
        for attempt in range(_ATTEMPTS):
            if not pending:
                break
            fields = '\n'.join(
                f'r{i}: repository(owner: {json.dumps(r.split("/", 1)[0])}, name: {json.dumps(r.split("/", 1)[1])}) '
                f'{{ {_REPO_FIELDS % ""} }}' for i, r in pending)
            try:
                data = _query('query { rateLimit { cost remaining }\n' + fields + '\n}')
            except Exception as e:
                log.warning('cannot read stats of %s (attempt %d): %s', ', '.join(r for _, r in pending),
                            attempt + 1, e)
                continue
            # An alias named in an error came back incomplete (timeout, node limit, or a
            # repository that does not exist): do not trust its data.
            errored = {e['path'][0] for e in _errors if e.get('path')}
            retry = []
            for i, repo in pending:
                node = data.get(f'r{i}')
                if f'r{i}' in errored or not node:
                    msgs = sorted({e.get('message') for e in _errors if e.get('path', [None])[0] == f'r{i}'})
                    if any(e.get('type') == 'NOT_FOUND' for e in _errors if e.get('path', [None])[0] == f'r{i}'):
                        log.warning('%s: no such repository, no stats', repo)
                    else:
                        log.warning('%s: incomplete response (attempt %d): %s', repo, attempt + 1, msgs)
                        retry.append((i, repo))
                    continue
                try:
                    result[repo] = _summarise(repo, node)
                except Exception as e:
                    log.warning('%s: cannot read stats: %s', repo, e)
                    retry.append((i, repo))
            pending = retry
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _prefetch(wanted: str):
    """Fetch every repository the package files release from in one go, so a build makes a
    handful of batched requests instead of one per package. `wanted` is the repository whose
    lookup started this; it is fetched too if the files did not name it."""
    cache = _load_cache()
    repos: dict[str, str] = {wanted.lower(): wanted}
    pattern = re.compile(r'github\.com/([^/\s\'"]+)/([^/\s\'"]+)/releases/', re.IGNORECASE)
    for path in Path(__file__).parent.parent.joinpath('packages').iterdir():
        try:
            for m in pattern.finditer(path.read_text(encoding='utf-8')):
                repos.setdefault(f'{m.group(1)}/{m.group(2)}'.lower(), f'{m.group(1)}/{m.group(2)}')
        except OSError:
            pass
    ci = 'CI' in os.environ
    todo = [r for k, r in sorted(repos.items()) if k not in _resolved and (ci or k not in cache)]
    for repo, fetched in fetch_many(todo).items():
        cache[repo.lower()] = {**fetched, 'fetchedAt': _now()}
        _resolved[repo.lower()] = fetched
    for repo in todo:
        _resolved.setdefault(repo.lower(), None)
    if todo:
        _save_cache(cache)


def _lookup(repo: str) -> Optional[dict]:
    key = repo.lower()
    if key not in _resolved:
        cache = _load_cache()
        if _token() and ('CI' in os.environ or key not in cache):
            _prefetch(repo)
        if key not in _resolved:  # no fetch wanted or possible: whatever the cache holds
            entry = cache.get(key) if 'CI' not in os.environ else None
            _resolved[key] = {k: entry[k] for k in ('downloads', 'stars') if k in entry} if entry else None
    return _resolved[key]


def for_package(info: dict) -> Optional[dict]:
    """The `stats` object of a package, or None when it has no GitHub release repository or
    nothing could be determined."""
    repo = repo_of(info)
    return _lookup(repo) if repo else None


def refresh_all() -> int:
    """Fetch every package's repository into the cache. Returns the number of repositories
    without stats."""
    from repogen import pkg_info
    global _cache
    repos: dict[str, str] = {}
    for info in pkg_info.list_packages(Path(__file__).parent.parent / 'packages', offline=True):
        if repo := repo_of(info):
            repos.setdefault(repo.lower(), repo)
    fetched = fetch_many(sorted(repos.values(), key=str.lower))
    _cache = {r.lower(): {**v, 'fetchedAt': _now()} for r, v in fetched.items()}
    _save_cache(_cache)
    failed = len(repos) - len(fetched)
    print(f'{len(fetched)} of {len(repos)} repositories have stats, {failed} failed; '
          f'{requests_made} HTTP requests, last rateLimit {last_rate_limit}')
    return failed


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    if not _token():
        print('GITHUB_TOKEN is not set; anonymous access is limited to 60 requests an hour', file=sys.stderr)
    refresh_all()
