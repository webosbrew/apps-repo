import importlib
from os import path
from typing import TypedDict, NotRequired, Literal

import yaml


class PackageRegistry(TypedDict):
    title: str
    iconUri: str
    manifestUrl: str
    manifestUrlBeta: NotRequired[str]
    category: str
    description: str
    pool: Literal['main', 'non-free']
    detailIconUri: NotRequired[str]
    funding: NotRequired[dict]


def parse_yml_package(p: str) -> (str, PackageRegistry):
    pkgid = path.splitext(path.basename(p))[0]
    with open(p, encoding='utf-8') as f:
        content: PackageRegistry = yaml.safe_load(f)
    return pkgid, content


# noinspection PyUnresolvedReferences
def load_py_package(p: str) -> (str, PackageRegistry):
    pkgid = path.splitext(path.basename(p))[0]
    spec = importlib.util.spec_from_file_location(f"pkg.{pkgid}", p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return pkgid, module.load()
