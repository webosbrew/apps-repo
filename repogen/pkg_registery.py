import importlib
import json
from pathlib import Path
from typing import TypedDict, NotRequired, Literal, List

import yaml

_CACHE_DIR = Path(__file__).parent.parent / 'cache'


class PackageRequirements(TypedDict):
    webosRelease: NotRequired[str]
    deviceSoC: NotRequired[List[str]]


class PackageRegistry(TypedDict):
    title: str
    iconUri: str
    manifestUrl: str
    manifestUrlBeta: NotRequired[str]
    category: str
    description: str
    shortDescription: NotRequired[str]
    pool: Literal['main', 'non-free']
    requirements: NotRequired[PackageRequirements]
    detailIconUri: NotRequired[str]
    funding: NotRequired[dict[str, List[str]]]


def parse_yml_package(p: Path) -> tuple[str, PackageRegistry]:
    with p.open(encoding='utf-8') as f:
        content: PackageRegistry = yaml.safe_load(f)
    return p.stem, content


# noinspection PyUnresolvedReferences
def load_py_package(p: Path, offline: bool = False) -> tuple[str, PackageRegistry]:
    pkgid = p.stem
    # .py packages resolve their registry at runtime (often via network). Cache the
    # resolved result, keyed on the source file's mtime, so offline builds (local dev)
    # reuse it without hitting the network but still re-run when the .py file changes.
    mtime = p.stat().st_mtime
    cache_file = _CACHE_DIR / f'registry_{pkgid}.json'
    if offline and cache_file.exists():
        try:
            with cache_file.open(encoding='utf-8') as f:
                cached = json.load(f)
            if cached.get('mtime') == mtime:
                return pkgid, cached['content']
        except (OSError, ValueError, KeyError):
            pass  # fall through and reload on any cache problem
    spec = importlib.util.spec_from_file_location(f"pkg.{pkgid}", p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    content = module.load()
    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        with cache_file.open('w', encoding='utf-8') as f:
            json.dump({'mtime': mtime, 'content': content}, f)
    except OSError:
        pass
    return pkgid, content
