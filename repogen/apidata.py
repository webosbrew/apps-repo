# -*- coding: utf-8 -*-
import json
import math
from os import makedirs
from os.path import exists, join

import more_itertools

from repogen.common import list_packages
from markdown import Markdown

MANIFEST_KEYS = ('id', 'title', 'iconUri', 'manifestUrl', 'manifest', 'manifestUrlBeta', 'manifestBeta', 'pool')


def generate(packages, outdir):
    markdown = Markdown()

    if not exists(outdir):
        makedirs(outdir)
    appsdir = join(outdir, 'apps')
    if not exists(appsdir):
        makedirs(appsdir)

    def package_item(item, in_apps_dir):
        package = {k: item[k] for k in MANIFEST_KEYS if k in item}
        package['shortDescription'] = item['manifest'].get(
            'appDescription', None)
        if in_apps_dir:
            package['fullDescriptionUrl'] = f'{item["id"]}-full_description.html'
        else:
            package['fullDescriptionUrl'] = f'apps/{item["id"]}-full_description.html'
        return package

    items_per_page = 30
    packages_length = len(packages)
    max_page = math.ceil(packages_length / items_per_page)
    for index, items in enumerate(more_itertools.chunked(packages, items_per_page)):
        page = index + 1
        json_file = join(appsdir, '%d.json' %
                         page) if page > 1 else join(outdir, 'apps.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'paging': {
                    'page': page,
                    'count': len(items),
                    'maxPage': max_page,
                    'itemsTotal': packages_length,
                },
                'packages': list(map(lambda x: package_item(x, page > 1), items))
            }, f, indent=2)
        for item in items:
            app_info = join(appsdir, f'{item["id"]}.json')
            with open(app_info, 'w', encoding='utf-8') as f:
                json.dump(package_item(item, True), f)
            desc_html = join(appsdir, f'{item["id"]}-full_description.html')
            with open(desc_html, 'w', encoding='utf-8') as f:
                f.write(markdown.convert(item['description']))
    print('Generated json data for %d packages.' % len(packages))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    args = parser.parse_args()

    generate(list_packages(args.input_dir), args.output_dir)
