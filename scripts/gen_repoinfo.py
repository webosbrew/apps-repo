#!/usr/bin/env python3

from os import listdir
from os.path import isfile, join

import yaml
import json

pkgpath = 'packages'

manifest_files = [f for f in listdir(pkgpath) if isfile(join(pkgpath, f))]


def parse_package_info(filename: str):
    with open(join(pkgpath, filename)) as f:
        content = yaml.safe_load(f)
    suffixidx = filename.rfind('.yml')
    if suffixidx < 0:
        return None
    pkgid = filename[:suffixidx]
    if not ('title' in content) and ('iconUri' in content) and ('manifestUrl' in content):
        return None
    return {
        'id': pkgid,
        'title': content['title'],
        'iconUri': content['iconUri'],
        'manifestUrl': content['manifestUrl'],
    }


packages = list(filter(lambda x: x, map(parse_package_info, manifest_files)))

print(json.dumps({
    'packages': packages
}, indent=2))
