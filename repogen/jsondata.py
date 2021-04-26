import json
import math
from os import makedirs
from os.path import exists, join

import more_itertools

from repogen.common import list_packages


def generate(indir, outdir):
    packages = list_packages(indir)

    if not exists(outdir):
        makedirs(outdir)

    def package_item(item):
        return {k: item[k] for k in ('id', 'title', 'iconUri', 'manifestUrl') if k in item}

    items_per_page = 30
    packages_length = len(packages)
    total_pages = math.ceil(packages_length / items_per_page)
    for page, items in enumerate(more_itertools.chunked(packages, items_per_page)):
        json_name = 'apps_%d.json' % page if page > 0 else 'apps.json'
        with open(join(outdir, json_name), 'w') as f:

            json.dump({
                'paging': {
                    'page': page,
                    'pageMax': total_pages - 1,
                    'pageTotal': total_pages,
                    'itemsTotal': packages_length,
                },
                'packages': list(map(package_item, items))
            }, f, indent=2)

    print('Generated json data for %d packages.' % len(packages))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    args = parser.parse_args()

    generate(args.input_dir, args.output_dir)
