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
    # resolved result so offline builds (local dev) can reuse it without hitting the network.
    cache_file = _CACHE_DIR / f'registry_{pkgid}.json'
    if offline and cache_file.exists():
        with cache_file.open(encoding='utf-8') as f:
            return pkgid, json.load(f)
    spec = importlib.util.spec_from_file_location(f"pkg.{pkgid}", p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    content = module.load()
    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        with cache_file.open('w', encoding='utf-8') as f:
            json.dump(content, f)
    except OSError:
        pass
    return pkgid, content
