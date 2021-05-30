import json
import locale
import os
from datetime import datetime
from os import listdir, mkdir, path
from os.path import basename, isfile, join
from urllib.parse import urljoin
from email.utils import parsedate_to_datetime
import bleach
import requests
import yaml

locale.setlocale(locale.LC_TIME, '')


def obtain_manifest(pkgid, url: str):
    if not path.exists('cache'):
        mkdir('cache')
    cache_file = path.join('cache', 'manifest_%s.json' % pkgid)
    try:
        resp = requests.get(url=url, allow_redirects=True)
        manifest = resp.json()
        manifest['ipkUrl'] = urljoin(url, manifest['ipkUrl'])
        with open(cache_file, 'w') as f:
            json.dump(manifest, f)
        last_modified = datetime.now()
        if 'last-modified' in resp.headers:
            last_modified = parsedate_to_datetime(
                resp.headers['last-modified'])
            os.utime(cache_file, (last_modified.timestamp(), last_modified.timestamp()))
        return manifest, last_modified
    except requests.exceptions.RequestException:
        if (path.exists(cache_file)):
            with open(cache_file) as f:
                return json.load(f), datetime.fromtimestamp(os.stat(cache_file).st_mtime)
    return None


def parse_package_info(path: str):
    filename = basename(path)
    with open(path) as f:
        content = yaml.safe_load(f)
    suffixidx = filename.rfind('.yml')
    if suffixidx < 0:
        return None
    pkgid = filename[:suffixidx]
    if not ('title' in content) and ('iconUri' in content) and ('manifestUrl' in content):
        return None
    pkginfo = {
        'id': pkgid,
        'title': content['title'],
        'iconUri': content['iconUri'],
        'manifestUrl': content['manifestUrl'],
        'category': content['category'],
        'description': bleach.clean(content.get('description', '')),
    }
    manifest, lastmodified = obtain_manifest(pkgid, content['manifestUrl'])
    pkginfo['lastmodified'] = lastmodified.strftime('%Y/%m/%d %H:%M:%S')
    if manifest:
        pkginfo['manifest'] = manifest
    return pkginfo


def list_packages(pkgdir):
    paths = [join(pkgdir, f)
             for f in listdir(pkgdir) if isfile(join(pkgdir, f))]
    return sorted(filter(lambda x: x, map(parse_package_info, paths)), key=lambda x: x['title'])
