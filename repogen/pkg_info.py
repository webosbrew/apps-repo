import locale
import sys
from datetime import datetime
from itertools import repeat
from pathlib import Path
from typing import TypedDict, List, NotRequired

import nh3

from repogen import validators
from repogen.common import url_fixup
from repogen.pkg_manifest import obtain_manifest, PackageManifest
from repogen.pkg_registery import PackageRequirements, PackageRegistry, parse_yml_package, load_py_package

locale.setlocale(locale.LC_TIME, '')

# Attributes kept when sanitizing rendered description HTML. 'class' and 'id' are
# allowed on every tag so markdown-generated heading anchors and code-highlighting
# spans survive sanitization.
_DESCRIPTION_ATTRIBUTES = {
    '*': {'class', 'id'},
    'a': {'href', 'hreflang', 'title'},
    'bdo': {'dir'},
    'blockquote': {'cite'},
    'col': {'align', 'char', 'charoff', 'span'},
    'colgroup': {'align', 'char', 'charoff', 'span'},
    'del': {'cite', 'datetime'},
    'h1': {'align'},
    'hr': {'align', 'size', 'width'},
    'img': {'align', 'alt', 'height', 'src', 'width'},
    'ins': {'cite', 'datetime'},
    'ol': {'start'},
    'p': {'align'},
    'q': {'cite'},
    'table': {'align', 'char', 'charoff', 'summary'},
    'tbody': {'align', 'char', 'charoff'},
    'td': {'align', 'char', 'charoff', 'colspan', 'headers', 'rowspan'},
    'tfoot': {'align', 'char', 'charoff'},
    'th': {'align', 'char', 'charoff', 'colspan', 'headers', 'rowspan', 'scope'},
    'thead': {'align', 'char', 'charoff'},
    'tr': {'align', 'char', 'charoff'},
}


def sanitize_description(html: str) -> str:
    """Sanitize rendered description HTML.

    Run this AFTER markdown conversion, never on the markdown source: an HTML
    sanitizer escapes markdown control characters (e.g. the '>' of a blockquote),
    which silently breaks the rendered output.
    """
    return nh3.clean(html, attributes=_DESCRIPTION_ATTRIBUTES, link_rel=None)


class PackageInfo(TypedDict):
    id: str
    title: str
    iconUri: str
    manifestUrl: str
    manifestUrlBeta: NotRequired[str]
    category: str
    description: str
    shortDescription: NotRequired[str]
    detailIconUri: NotRequired[str]
    funding: NotRequired[dict]
    pool: str
    requirements: NotRequired[PackageRequirements]
    manifest: PackageManifest
    manifestBeta: NotRequired[PackageManifest]
    lastmodified: datetime
    lastmodified_str: str
    # Only set on API output, for packages listed in FEATURED_APPS.
    featured: NotRequired[bool]


def load_registry(info_path: Path, offline: bool = False) -> tuple[str, PackageRegistry]:
    extension = info_path.suffix
    content: PackageRegistry
    if extension == '.yml':
        pkgid, content = parse_yml_package(info_path)
    elif extension == '.py':
        pkgid, content = load_py_package(info_path, offline)
    else:
        raise ValueError(f'Unsupported package file `{info_path.name}` — package files must be '
                         f'named `<package id>.yml`')
    validator = validators.for_schema('packages/PackageInfo.json')
    validators.validate(validator, content)
    return pkgid, content


def from_package_info_file(info_path: Path, offline=False) -> PackageInfo:
    pkgid, content = load_registry(info_path, offline)
    return from_package_info(pkgid, content, offline)


def from_package_info(pkgid: str, content: PackageRegistry, offline=False) -> PackageInfo:
    print(f'Parsing package info for {pkgid}', file=sys.stderr)
    manifest_url = url_fixup(content['manifestUrl'])
    pkginfo: PackageInfo = {
        'id': pkgid,
        'title': content['title'],
        'iconUri': content['iconUri'],
        'manifestUrl': manifest_url,
        'category': content['category'],
        # Raw markdown source; sanitized after conversion via sanitize_description().
        'description': content.get('description', ''),
    }
    if 'shortDescription' in content:
        pkginfo['shortDescription'] = content['shortDescription']
    if 'detailIconUri' in content:
        pkginfo['detailIconUri'] = content['detailIconUri']
    if 'funding' in content:
        pkginfo['funding'] = content['funding']
    pkginfo['pool'] = valid_pool(content['pool'])
    if 'requirements' in content:
        pkginfo['requirements'] = content['requirements']
    manifest, lastmodified_r = obtain_manifest(pkgid, 'release', manifest_url, offline)
    if manifest:
        pkginfo['manifest'] = manifest
    lastmodified_b = None
    if 'manifestUrlBeta' in content:
        manifest_b, lastmodified_b = obtain_manifest(pkgid, 'beta', url_fixup(content['manifestUrlBeta']))
        if manifest_b:
            pkginfo['manifestBeta'] = manifest_b
    lastmodified = lastmodified_r, lastmodified_b
    pkginfo['lastmodified'] = max(d for d in lastmodified if d is not None)
    pkginfo['lastmodified_str'] = pkginfo['lastmodified'].strftime('%Y/%m/%d %H:%M:%S %Z')
    return pkginfo


def list_packages(pkgdir: Path, packages: List[str] | None = None, offline: bool = False) -> List[PackageInfo]:
    paths: List[Path] = [f for f in pkgdir.iterdir() if f.is_file()]

    def map_package_info(p: Path) -> PackageInfo | None:
        pkgid, content = load_registry(p, offline)
        if packages and pkgid not in packages:
            return None
        try:
            return from_package_info(pkgid, content, offline)
        except Exception as e:
            print(f'Error loading package info file {p.name}: {e}', file=sys.stderr)
            return None

    pkgs = sorted(filter(lambda x: x, map(map_package_info, paths)), key=lambda x: x['title'])
    return pkgs


def valid_pool(value: str) -> str:
    if value not in ['main', 'non-free']:
        raise ValueError(f'Unknown pool type {value}')
    return value
