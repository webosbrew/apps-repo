"""GitHub download and star counts of packages, shown on app pages and in the API as `stats`.

The source repository is the one the package's manifest URL (or, failing that, the manifest's
ipk URL) releases from. `stars` is the repository's star count; `downloads` is the sum of
`download_count` over every `.ipk` release asset of every release, so manifests and source
archives do not inflate it. Update downloads are counted too.

Counts are cached in .stats-cache/stats.json, keyed by `owner/repo`, with each release's `.ipk`
download sum kept under its node id. In CI (`CI` set) every build refreshes incrementally: it
reads each repository's star count and only its 5 most recent releases, and takes the cached
sums for all older releases. Downloads of current releases, new releases (paging further if all
5 fetched are unknown) and star changes are therefore picked up on every build. Old releases
still gain a trickle of downloads the incremental fetch does not see, and a release deleted
upstream lingers in the cache; both are corrected by a full scan of every release, which a
repository gets when it has no cache entry, the cache version changed, or its last full scan
(`full_at`) is over 24 hours old. CI persists the cache between runs with actions/cache.
Locally the cache is used whatever its age, and a repository missing from it is fetched (in
full) only when GITHUB_TOKEN is set; without one it is skipped silently, since anonymous API
access allows just 60 requests an hour. A failed request logs a warning and
leaves that repository without stats; it never fails the build. Counts come from the GraphQL API,
which always needs a token, many repositories per request.

Run `python -m repogen.stats` to fully refresh the whole local cache, or `python -m repogen.stats
--incremental` to run the CI path against it. It reads the token from
GITHUB_TOKEN, so `GITHUB_TOKEN=$(gh auth token) python -m repogen.stats` works.
"""
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent / '.stats-cache' / 'stats.json'
# Bump when the cached shape changes.
_CACHE_VERSION = 2
# How long a full scan of a repository's releases stays good for.
_FULL_MAX_AGE = timedelta(hours=24)
# Most recent releases an incremental fetch reads per repository.
_WINDOW = 5
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
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _CACHE_FILE.open('w', encoding='utf-8') as f:
            json.dump({'version': _CACHE_VERSION, 'repos': repos}, f, indent=1, sort_keys=True)
    except OSError:
        pass


_GRAPHQL = f'{_API}/graphql'
# A full scan of 100 releases of 50 assets each is the most a repository can add to a query's
# node budget (500,000), so full batches stay small; the incremental window is far lighter.
_BATCH_FULL = 5
_BATCH_INCREMENTAL = 20
_ATTEMPTS = 3
_ASSETS = 'releaseAssets(first: 50) { pageInfo { hasNextPage endCursor } nodes { name downloadCount } }'
_FULL_FIELDS = f"""stargazerCount
    releases(first: 100) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{ id {_ASSETS} }}
    }}"""
_WINDOW_FIELDS = f"""stargazerCount
    releases(first: {_WINDOW}, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{ id {_ASSETS} }}
    }}"""

# For reporting how heavy a refresh is.
requests_made = 0
points_spent = 0
last_rate_limit: Optional[dict] = None
_errors: list = []


def _query(query: str, variables: Optional[dict] = None) -> dict:
    """One GraphQL request. Returns the `data` object, which may hold nulls for repositories
    that errored; raises on HTTP failure or when there is no data at all."""
    global requests_made, last_rate_limit, points_spent
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
        points_spent += int(last_rate_limit.get('cost') or 0)
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


def _release_sums(releases: dict) -> dict[str, int]:
    """Release node id -> `.ipk` downloads, for one page of releases."""
    sums = {}
    for release in releases['nodes']:
        if not release:
            continue
        assets = release['releaseAssets']
        downloads = _ipk_downloads(assets['nodes'])
        if assets['pageInfo']['hasNextPage']:
            downloads += _more_assets(release['id'], assets['pageInfo']['endCursor'])
        sums[release['id']] = downloads
    return sums


def _more_releases(repo: str, cursor: str, first: int, order: str = '') -> dict:
    owner, name = repo.split('/', 1)
    data = _query('query($o: String!, $n: String!, $c: String) { rateLimit { cost remaining }'
                  f' repository(owner: $o, name: $n) {{ releases(first: {first}, after: $c{order}) {{'
                  f' pageInfo {{ hasNextPage endCursor }} nodes {{ id {_ASSETS} }} }} }} }}',
                  {'o': owner, 'n': name, 'c': cursor})
    return data['repository']['releases']


def _entry(stars: int, releases: dict[str, int], full_at: str) -> dict:
    return {'stars': stars, 'downloads': sum(releases.values()), 'releases': releases, 'full_at': full_at}


def _summarise_full(repo: str, node: dict, cached: Optional[dict]) -> dict:
    """Cache entry out of one repository node, following release and asset pages beyond the first."""
    sums: dict[str, int] = {}
    releases = node['releases']
    while True:
        sums.update(_release_sums(releases))
        if not releases['pageInfo']['hasNextPage']:
            break
        releases = _more_releases(repo, releases['pageInfo']['endCursor'], 100)
    return _entry(int(node['stargazerCount']), sums, _now())


def _summarise_window(repo: str, node: dict, cached: Optional[dict]) -> dict:
    """Cache entry out of a repository's most recent releases plus the cached older ones. When
    none of the fetched releases is known, newer ones may have been missed, so page on until a
    known release shows up or the list ends."""
    known = cached['releases']
    releases = node['releases']
    live = _release_sums(releases)
    while releases['pageInfo']['hasNextPage'] and not any(i in known for i in live):
        releases = _more_releases(repo, releases['pageInfo']['endCursor'], _WINDOW,
                                  ', orderBy: {field: CREATED_AT, direction: DESC}')
        live.update(_release_sums(releases))
    sums = {i: d for i, d in known.items() if i not in live}
    sums.update(live)
    return _entry(int(node['stargazerCount']), sums, cached['full_at'])


def _fetch_batches(repos: list[str], batch_size: int, fields: str, summarise, cache: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for start in range(0, len(repos), batch_size):
        pending = list(enumerate(repos[start:start + batch_size]))
        for attempt in range(_ATTEMPTS):
            if not pending:
                break
            query = '\n'.join(
                f'r{i}: repository(owner: {json.dumps(r.split("/", 1)[0])}, name: {json.dumps(r.split("/", 1)[1])}) '
                f'{{ {fields} }}' for i, r in pending)
            try:
                data = _query('query { rateLimit { cost remaining }\n' + query + '\n}')
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
                    result[repo] = summarise(repo, node, cache.get(repo.lower()))
                except Exception as e:
                    log.warning('%s: cannot read stats: %s', repo, e)
                    retry.append((i, repo))
            pending = retry
    return result


def _needs_full(entry: Optional[dict]) -> bool:
    """Whether a repository is due a full scan: no usable entry, or the last one is too old."""
    if not entry or not isinstance(entry.get('releases'), dict):
        return True
    try:
        full_at = datetime.fromisoformat(entry['full_at'])
    except (KeyError, TypeError, ValueError):
        return True
    return datetime.now(timezone.utc) - full_at > _FULL_MAX_AGE


def fetch_many(repos: list[str], cache: Optional[dict] = None, force_full: bool = False) -> dict[str, dict]:
    """Cache entries of repositories from the GraphQL API, a batch of repositories per request.

    Repositories with a usable entry in `cache` that had a full scan within 24 hours get the
    incremental fetch, the others (or all, with `force_full`) a full scan. Returns
    `owner/repo` -> an entry with `stars`, `downloads`, `releases` and `full_at`. A repository
    that does not exist (renamed, deleted, private), or whose batch failed, is left out with a
    warning."""
    cache = cache if cache is not None else {}
    full = [r for r in repos if force_full or _needs_full(cache.get(r.lower()))]
    incremental = [r for r in repos if r not in full]
    result = _fetch_batches(full, _BATCH_FULL, _FULL_FIELDS, _summarise_full, cache)
    result.update(_fetch_batches(incremental, _BATCH_INCREMENTAL, _WINDOW_FIELDS, _summarise_window, cache))
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
    for repo, fetched in fetch_many(todo, cache).items():
        cache[repo.lower()] = {**fetched, 'fetchedAt': _now()}
        _resolved[repo.lower()] = {k: fetched[k] for k in ('downloads', 'stars')}
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


def refresh_all(incremental: bool = False) -> int:
    """Fetch every package's repository into the cache, in full unless `incremental` (then
    repositories with a fresh enough full scan get the incremental fetch). Returns the number
    of repositories without stats."""
    from repogen import pkg_info
    global _cache
    repos: dict[str, str] = {}
    for info in pkg_info.list_packages(Path(__file__).parent.parent / 'packages', offline=True):
        if repo := repo_of(info):
            repos.setdefault(repo.lower(), repo)
    cache = _load_cache() if incremental else {}
    fetched = fetch_many(sorted(repos.values(), key=str.lower), cache, force_full=not incremental)
    _cache = {k: v for k, v in cache.items() if k in repos}
    _cache.update({r.lower(): {**v, 'fetchedAt': _now()} for r, v in fetched.items()})
    _save_cache(_cache)
    failed = len(repos) - len(fetched)
    print(f'{len(fetched)} of {len(repos)} repositories have stats, {failed} failed; '
          f'{requests_made} HTTP requests, {points_spent} points, last rateLimit {last_rate_limit}')
    return failed


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    if not _token():
        print('GITHUB_TOKEN is not set; anonymous access is limited to 60 requests an hour', file=sys.stderr)
    refresh_all(incremental='--incremental' in sys.argv[1:])
