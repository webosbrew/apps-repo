# -*- coding: utf-8 -*-
import json
import math
import os
import urllib.parse
from pathlib import Path
from typing import List, Set

import more_itertools
import requests
from markdown import Markdown

from repogen import pkg_info
from repogen.common import ITEMS_PER_PAGE, ensure_open
from repogen.icons import obtain_icon
from repogen.pkg_info import PackageInfo
from repogen.siteurl import siteurl

MANIFEST_KEYS = ('id', 'title', 'iconUri', 'manifestUrl', 'manifest', 'manifestUrlBeta', 'manifestBeta', 'pool',
                 'detailIconUri', 'requirements')


def fix_manifest_url(item: PackageInfo, app_dir: Path):
    if urllib.parse.urlparse(item['manifestUrl']).scheme != 'file':
        return
    manifest = item["manifest"]
    manifest_path = app_dir.joinpath('manifests', f'{manifest["version"]}.json')

    with ensure_open(manifest_path, mode='w') as mf:
        json.dump(manifest, mf)
    manifest_url = manifest_path.as_posix()
    item['manifestUrl'] = manifest_url[manifest_url.find('/api/apps'):]


def save_ipk(item: PackageInfo, apps_dir: Path, site_url: str):
    """
    Save the ipk file to the apps directory, and modify PackageInfo to point to the local file.
    """
    manifest = item['manifest']
    app_ipk = apps_dir.joinpath(item["id"], 'releases', f'{manifest["ipkHash"]["sha256"]}.ipk')
    if not app_ipk.parent.exists():
        app_ipk.parent.mkdir(parents=True, exist_ok=True)
    # Not likely to happen, but just in case someday we host some ipk files by ourselves directly.
    if site_url and manifest['ipkUrl'].startswith(site_url):
        return
    with requests.get(manifest['ipkUrl'], allow_redirects=True) as resp:
        with ensure_open(app_ipk, 'wb') as f:
            f.write(resp.content)
    manifest['ipkUrl'] = f'{site_url.removesuffix("/")}/{"/".join(app_ipk.parts[-4:])}'


def generate(packages: List[PackageInfo], api_dir: Path, apps_dir: Path = None, host_packages: Set[str] = None,
             featured_packages: Set[str] = None):
    markdown = Markdown()

    appsdir: Path = api_dir.joinpath('apps')
    site_url = siteurl()

    def package_item(p_info: PackageInfo, in_apps_dir: bool, is_details: bool) -> PackageInfo:
        package = {k: p_info[k] for k in MANIFEST_KEYS if k in p_info}
        # Prefer the manifest's appDescription, fall back to the package's shortDescription.
        package['shortDescription'] = p_info['manifest'].get('appDescription') or p_info.get(
            'shortDescription')
        # Present only on featured packages, so clients can highlight them.
        if featured_packages and p_info['id'] in featured_packages:
            package['featured'] = True
        if is_details:
            package['fullDescriptionUrl'] = f'../full_description.html'
        elif in_apps_dir:
            package['fullDescriptionUrl'] = f'{p_info["id"]}/full_description.html'
        else:
            package['fullDescriptionUrl'] = f'apps/{p_info["id"]}/full_description.html'
        if os.environ.get('CI'):
            package['iconUri'] = obtain_icon(package['id'], p_info["iconUri"], site_url)
            package['manifest']['iconUri'] = package['iconUri']
        return package

    packages_length = len(packages)
    # An empty pool still writes page 1, so never report fewer than one page.
    max_page = max(1, math.ceil(packages_length / ITEMS_PER_PAGE))

    def write_json(json_file: Path, items: [PackageInfo], in_apps_dir: bool, paging: dict):
        with ensure_open(json_file, 'w', encoding='utf-8') as pf:
            json.dump({
                'paging': paging,
                'packages': list(map(lambda x: package_item(x, in_apps_dir, False), items))
            }, pf, indent=2)

    def save_all(items: [PackageInfo]):
        """
        apps.json lists every package at once.

        The Homebrew Channel reads this file and never asks for another page,
        so it must hold the whole repository. It reports itself as a single
        page, which keeps paginating clients away from the apps/ tree.
        """
        write_json(api_dir.joinpath('apps.json'), items, False, {
            'page': 1,
            'count': len(items),
            'maxPage': 1,
            'itemsTotal': packages_length,
            'prevUrl': None,
            'nextUrl': None,
        })

    def save_page(page: int, items: [PackageInfo]):
        """
        apps/<page>.json is the paginated view. Page 1 is part of it, so every
        page has the same URL shape and clients can build it from the number.
        """
        write_json(appsdir.joinpath('%d.json' % page), items, True, {
            'page': page,
            'count': len(items),
            'maxPage': max_page,
            'itemsTotal': packages_length,
            # Null on the first and last page. Lets clients walk the pages
            # without knowing how the URLs are laid out.
            'prevUrl': '%d.json' % (page - 1) if page > 1 else None,
            'nextUrl': '%d.json' % (page + 1) if page < max_page else None,
        })

    chunks = more_itertools.chunked(packages, ITEMS_PER_PAGE) if packages else [[]]
    for index, chunk in enumerate(chunks):
        for item in chunk:
            api_app_dir = appsdir.joinpath(item['id'])
            releases_dir = api_app_dir.joinpath('releases')
            if host_packages and item['id'] in host_packages:
                save_ipk(item, apps_dir, site_url)
            fix_manifest_url(item, api_app_dir)
            # This will be used by dev-manager-desktop
            app_info = releases_dir.joinpath('latest.json')
            with ensure_open(app_info, 'w', encoding='utf-8') as f:
                json.dump(package_item(item, True, True), f)
            desc_html = api_app_dir.joinpath('full_description.html')
            with ensure_open(desc_html, 'w', encoding='utf-8') as f:
                f.write(pkg_info.sanitize_description(markdown.convert(item['description'])))
        save_page(index + 1, chunk)
    # Runs last: the loop above rewrites manifestUrl of every package.
    save_all(packages)
    print('Generated json data for %d packages.' % len(packages))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    args = parser.parse_args()

    generate(pkg_info.list_packages(Path(args.input_dir)), Path(args.output_dir))
