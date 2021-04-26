import json
from os import makedirs
from os.path import dirname, exists, join

import pystache

from repogen.common import list_packages


def generate(indir, outdir):
    packages = list_packages(indir)

    with open(join(dirname(__file__), 'templates', 'apps', 'detail.md')) as f:
        details_template = f.read()

    with open(join(dirname(__file__), 'templates', 'apps', 'index.html')) as f:
        index_template = f.read()

    if not exists(outdir):
        makedirs(outdir)

    for pkg in packages:
        with open(join(outdir, '%s.md' % pkg['id']), 'w') as f:
            f.write(pystache.render(details_template, pkg))

    with open(join(outdir, 'index.html'), 'w') as f:
        f.write(pystache.render(index_template, {'packages': packages}))

    print('Generated application page for %d packages.' % len(packages))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    args = parser.parse_args()

    generate(args.input_dir, args.output_dir)
