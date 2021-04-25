import argparse
import json
from os import makedirs
from os.path import exists, join

from repogen.common import list_packages

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input-dir', required=True)
parser.add_argument('-o', '--output-dir', required=True)
args = parser.parse_args()

pkgpath = args.input_dir
outdir = args.output_dir

packages = list_packages(pkgpath)

if not exists(outdir):
    makedirs(outdir)

with open(join(outdir, 'apps.json'), 'w') as f:
    json.dump({
        'packages': packages
    }, f, indent=2)

print('Generated for %d packages.' % len(packages))
