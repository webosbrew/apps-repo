import json
from os import makedirs
from os.path import exists, join

from repogen.common import list_packages


def generate(indir, outdir):
    packages = list_packages(indir)

    if not exists(outdir):
        makedirs(outdir)

    with open(join(outdir, 'apps.json'), 'w') as f:
        json.dump({
            'packages': packages
        }, f, indent=2)

    print('Generated json data for %d packages.' % len(packages))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    args = parser.parse_args()

    generate(args.input_dir, args.output_dir)
