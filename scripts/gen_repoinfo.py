#!/usr/bin/env python3

from os import listdir, makedirs
from os.path import isfile, join, exists

import yaml
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input-dir', required=True)
parser.add_argument('-o', '--output-dir', required=True)
args = parser.parse_args()

pkgpath = args.input_dir
outdir = args.output_dir

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

if not exists(outdir):
    makedirs(outdir, exist_ok)

with open(join(outdir, 'apps.json'), 'w') as f:
    json.dump({
        'packages': packages
    }, f, indent=2)

print('Generated for %d packages.' % len(packages))
