# -*- coding: utf-8 -*-
import importlib.util
import json
import locale
import os
import urllib
from datetime import datetime
from email.utils import parsedate_to_datetime
from json import JSONDecodeError
from os import listdir, mkdir, path
from os.path import basename, isfile, join
from urllib.parse import urljoin

import bleach
import requests
import yaml

locale.setlocale(locale.LC_TIME, '')


def url_fixup(u):
    parsed = urllib.parse.urlparse(u)
    segs = parsed.path.split('/')
    if parsed.hostname == 'github.com' and len(segs) == 7 and segs[3] == 'releases' and segs[4] == 'latest':
        resp = requests.get(u, allow_redirects=False)
        if resp.is_redirect:
            return resp.headers['location']
    return u


def url_size(u):
    content_length = requests.head(u, allow_redirects=True).headers.get('content-length', None)
    if not content_length:
        return 0
    return int(content_length)


def obtain_manifest(pkgid, type, url: str, offline=False):
    if not path.exists('cache'):
        mkdir('cache')
    cache_file = path.join('cache', f'manifest_{pkgid}_{type}.json')
    try:
        if offline:
            raise requests.exceptions.ConnectionError('Offline')
        url = url_fixup(url)
        resp = requests.get(url=url, allow_redirects=True)
        manifest = resp.json()
        manifest['ipkUrl'] = urljoin(url, manifest['ipkUrl'])
        manifest['ipkSize'] = url_size(manifest['ipkUrl'])
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        last_modified = datetime.now()
        if 'last-modified' in resp.headers:
            last_modified = parsedate_to_datetime(
                resp.headers['last-modified'])
            os.utime(cache_file, (last_modified.timestamp(), last_modified.timestamp()))
        return manifest, last_modified
    except requests.exceptions.RequestException as e:
        if path.exists(cache_file):
            try:
                with open(cache_file, encoding='utf-8') as f:
                    return json.load(f), datetime.fromtimestamp(os.stat(cache_file).st_mtime)
            except IOError or JSONDecodeError:
                os.unlink(cache_file)
        else:
            raise e
    return None


def valid_pool(value):
    if value not in ['main', 'non-free']:
        raise ValueError(f'Unknown pool type {value}')
    return value


def parse_package_info(path: str, offline=False):
    extension = os.path.splitext(path)[1]
    if extension == '.yml':
        content = parse_yml_package(path)
    elif extension == '.py':
        content = load_py_package(path)
    else:
        return None
    if not ('title' in content) and ('iconUri' in content) and ('manifestUrl' in content):
        return None
    pkgid = os.path.splitext(basename(path))[0]
    manifest_url = url_fixup(content['manifestUrl'])
    pkginfo = {
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


def parse_yml_package(path):
    with open(path, encoding='utf-8') as f:
        content = yaml.safe_load(f)
    return content


# noinspection PyUnresolvedReferences
def load_py_package(path):
    pkgid = os.path.splitext(basename(path))[0]
    spec = importlib.util.spec_from_file_location(f"pkg.{pkgid}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load()


def list_packages(pkgdir, offline=False):
    paths = [join(pkgdir, f)
             for f in listdir(pkgdir) if isfile(join(pkgdir, f))]
    return sorted(filter(lambda x: x, map(lambda p: parse_package_info(p, offline), paths)), key=lambda x: x['title'])
