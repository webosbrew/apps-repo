# -*- coding: utf-8 -*-
import json
import math
import os
import posixpath
import urllib.parse
from pathlib import Path
from typing import List, Set

import more_itertools
import requests
from markdown import Markdown

from repogen import pkg_info
from repogen.common import ITEMS_PER_PAGE, ensure_open
from repogen.icons import obtain_icon
from repogen.mdext import ListAfterParagraphExtension
from repogen.pkg_info import PackageInfo
from repogen.siteurl import siteurl

MANIFEST_KEYS = ('id', 'title', 'iconUri', 'manifestUrl', 'manifest', 'manifestUrlBeta', 'manifestBeta', 'pool',
                 'category', 'detailIconUri', 'requirements', 'screenshots', 'stats')

# Where each pool's API lives, under api/ on the site.
POOL_DIRS = {'main': '', 'non-free': 'non-free'}

# The files of a pool's API, relative to its directory. These are format strings and,
# with a leading slash, OpenAPI path templates: the writer below and repogen/openapi.py
# share them, so the published definition describes the files actually written.
APPS = 'apps.json'
APPS_PAGE = 'apps/{page}.json'
RELEASE_LATEST = 'apps/{id}/releases/latest.json'
FULL_DESCRIPTION = 'apps/{id}/full_description.html'
CATEGORIES = 'categories.json'
CATEGORY = 'categories/{category}.json'
CATEGORY_PAGE = 'categories/{category}/{page}.json'


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


def relative_url(target: str, from_file: str) -> str:
    """URL of `target` relative to `from_file`, both given as paths under a pool's api/ directory."""
    return posixpath.relpath(target, posixpath.dirname(from_file) or '.')


def generate(packages: List[PackageInfo], api_dir: Path, apps_dir: Path = None, host_packages: Set[str] = None,
             featured_packages: Set[str] = None, *, categories: List[dict]):
    """Write the API of one pool into `api_dir`. `packages` are sorted by title, and
    `categories` is conf/categories.yml, whose order the category list keeps."""
    markdown = Markdown(extensions=[ListAfterParagraphExtension()])

    site_url = siteurl()
    known = {cat['slug'] for cat in categories}
    unknown = sorted({p['category'] for p in packages} - known)
    if unknown:
        raise ValueError(f'Package categories missing from conf/categories.yml: {", ".join(unknown)}')

    def package_item(p_info: PackageInfo, from_file: str) -> PackageInfo:
        package = {k: p_info[k] for k in MANIFEST_KEYS if k in p_info}
        # The package's shortDescription overrides the manifest's appDescription.
        package['shortDescription'] = p_info.get('shortDescription') or p_info['manifest'].get(
            'appDescription')
        # Present only on featured packages, so clients can highlight them.
        if featured_packages and p_info['id'] in featured_packages:
            package['featured'] = True
        package['fullDescriptionUrl'] = relative_url(FULL_DESCRIPTION.format(id=p_info['id']), from_file)
        if os.environ.get('CI'):
            package['iconUri'] = obtain_icon(package['id'], p_info["iconUri"], site_url)
            package['manifest']['iconUri'] = package['iconUri']
        return package

    def write_json(rel_path: str, data: dict, indent: int | None = 2):
        with ensure_open(api_dir.joinpath(rel_path), 'w', encoding='utf-8') as pf:
            json.dump(data, pf, indent=indent)

    def write_list(rel_path: str, items: [PackageInfo], paging: dict, head: dict = None):
        write_json(rel_path, {
            **(head or {}),
            'paging': paging,
            'packages': [package_item(x, rel_path) for x in items],
        })

    def save_all(rel_path: str, items: [PackageInfo], head: dict = None):
        """
        One file holding a whole list. It reports itself as a single page, which
        keeps paginating clients away from the paged tree.
        """
        write_list(rel_path, items, {
            'page': 1,
            'count': len(items),
            'maxPage': 1,
            'itemsTotal': len(items),
            'prevUrl': None,
            'nextUrl': None,
        }, head)

    def save_pages(page_path: str, items: [PackageInfo], head: dict = None):
        """
        The paginated view of a list, one file per page. Page 1 is part of it, so every
        page has the same URL shape and clients can build it from the number. An empty
        list still writes page 1.
        """
        max_page = max(1, math.ceil(len(items) / ITEMS_PER_PAGE))
        chunks = more_itertools.chunked(items, ITEMS_PER_PAGE) if items else [[]]
        for page, chunk in enumerate(chunks, start=1):
            rel_path = page_path.format(page=page)
            write_list(rel_path, chunk, {
                'page': page,
                'count': len(chunk),
                'maxPage': max_page,
                'itemsTotal': len(items),
                # Null on the first and last page. Lets clients walk the pages
                # without knowing how the URLs are laid out.
                'prevUrl': relative_url(page_path.format(page=page - 1), rel_path) if page > 1 else None,
                'nextUrl': relative_url(page_path.format(page=page + 1), rel_path) if page < max_page else None,
            }, head)

    for item in packages:
        api_app_dir = api_dir.joinpath(posixpath.dirname(FULL_DESCRIPTION.format(id=item['id'])))
        if host_packages and item['id'] in host_packages:
            save_ipk(item, apps_dir, site_url)
        fix_manifest_url(item, api_app_dir)
        # This will be used by dev-manager-desktop
        latest = RELEASE_LATEST.format(id=item['id'])
        write_json(latest, package_item(item, latest), indent=None)
        desc = pkg_info.sanitize_description(markdown.convert(item['description']))
        if item.get('screenshots'):
            # Above the description, as on the site. Added after sanitizing, which
            # would strip its inline styles.
            desc = pkg_info.screenshots_html(item['screenshots']) + '\n' + desc
        with ensure_open(api_dir.joinpath(FULL_DESCRIPTION.format(id=item['id'])), 'w', encoding='utf-8') as f:
            f.write(desc)

    # The lists run after the loop above, which rewrites manifestUrl of every package.
    # The Homebrew Channel reads apps.json and never asks for another page, so it
    # must hold the whole repository.
    save_all(APPS, packages)
    save_pages(APPS_PAGE, packages)

    category_list = []
    for cat in categories:
        members = [p for p in packages if p['category'] == cat['slug']]
        info = {'id': cat['slug'], 'title': cat['title'], 'count': len(members)}
        category_file = CATEGORY.format(category=cat['slug'])
        category_list.append({
            **info,
            'appsUrl': relative_url(category_file, CATEGORIES),
            'pagesUrl': relative_url(CATEGORY_PAGE.format(category=cat['slug'], page=1), CATEGORIES),
        })
        save_all(category_file, members, {'category': info})
        save_pages(CATEGORY_PAGE.replace('{category}', cat['slug']), members, {'category': info})
    write_json(CATEGORIES, {'categories': category_list})
    print('Generated json data for %d packages.' % len(packages))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    args = parser.parse_args()

    from repogen import conf

    generate(pkg_info.list_packages(Path(args.input_dir)), Path(args.output_dir), categories=conf.categories())
