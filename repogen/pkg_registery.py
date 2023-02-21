from typing import TypedDict, Optional

import yaml


class PackageRegistry(TypedDict):
    title: str
    iconUri: str
    manifestUrl: str
    category: str
    detailIconUri: Optional[str]
    funding: Optional[dict]


def parse_yml_package(p: str) -> PackageRegistry:
    with open(p, encoding='utf-8') as f:
        content = yaml.safe_load(f)
    return content


# noinspection PyUnresolvedReferences
def load_py_package(p: str) -> PackageRegistry:
    pkgid = os.path.splitext(basename(p))[0]
    spec = importlib.util.spec_from_file_location(f"pkg.{pkgid}", p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load()
