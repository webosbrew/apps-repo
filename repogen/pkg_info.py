import locale
import os
from datetime import datetime
from os.path import basename, isfile, join
from typing import TypedDict, Optional, List

import bleach

from repogen.common import url_fixup
from repogen.pkg_manifest import obtain_manifest, PackageManifest
from repogen.pkg_registery import PackageRegistry, parse_yml_package, load_py_package

locale.setlocale(locale.LC_TIME, '')


class PackageInfo(TypedDict):
    id: str
    title: str
    iconUri: str
    manifestUrl: str
    manifestUrlBeta: Optional[str]
    category: str
    description: str
    detailIconUri: Optional[str]
    funding: Optional[dict]
    pool: str
    nopool: Optional[bool]
    manifest: PackageManifest
    manifestBeta: Optional[PackageManifest]
    lastmodified: datetime
    lastmodified_str: str


def parse_package_info(info_path: str, offline=False) -> Optional[PackageInfo]:
    extension = os.path.splitext(info_path)[1]
    content: PackageRegistry
    if extension == '.yml':
        content = parse_yml_package(info_path)
    elif extension == '.py':
        content = load_py_package(info_path)
    else:
        return None
    if not ('title' in content) and ('iconUri' in content) and ('manifestUrl' in content):
        return None
    pkgid = os.path.splitext(basename(info_path))[0]
    manifest_url = url_fixup(content['manifestUrl'])
    pkginfo: PackageInfo = {
        'id': pkgid,
        'title': content['title'],
        'iconUri': content['iconUri'],
        'manifestUrl': manifest_url,
        'category': content['category'],
        'description': bleach.clean(content.get('description', '')),
    }
    if 'detailIconUri' in content:
        pkginfo['detailIconUri'] = content['detailIconUri']
    if 'funding' in content:
        pkginfo['funding'] = content['funding']
    if 'pool' in content:
        try:
            pkginfo['pool'] = valid_pool(content['pool'])
        except ValueError:
            return None
    else:
        # This is for compatibility, new submissions requires this field
        pkginfo['pool'] = 'main'
        pkginfo['nopool'] = True
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


def list_packages(pkgdir: str, offline: bool = False) -> List[PackageInfo]:
    paths = [join(pkgdir, f)
             for f in os.listdir(pkgdir) if isfile(join(pkgdir, f))]
    return sorted(filter(lambda x: x, map(lambda p: parse_package_info(p, offline), paths)), key=lambda x: x['title'])


def valid_pool(value: str) -> str:
    if value not in ['main', 'non-free']:
        raise ValueError(f'Unknown pool type {value}')
    return value
