from os import listdir
from os.path import basename, isfile, join

import bleach
import requests
import yaml


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
    manifest = requests.get(
        url=content['manifestUrl'], allow_redirects=True).json()
    return {
        'id': pkgid,
        'title': content['title'],
        'iconUri': content['iconUri'],
        'manifestUrl': content['manifestUrl'],
        'manifest': manifest,
        'category': content['category'],
        'description': bleach.clean(content.get('description', '')),
    }


def list_packages(pkgdir):
    paths = [join(pkgdir, f)
             for f in listdir(pkgdir) if isfile(join(pkgdir, f))]
    return sorted(filter(lambda x: x, map(parse_package_info, paths)), key=lambda x: x['title'])
