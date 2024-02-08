import logging
import os
from pathlib import Path

from markdown import Markdown
from more_itertools import chunked
from pelican import signals, Readers, PagesGenerator, StaticGenerator
from pelican.contents import Page
from pelican.readers import BaseReader
from pelican.themes.webosbrew import pagination_data

from repogen import funding, apidata, pkg_info
from repogen.icons import obtain_icon

log = logging.getLogger(__name__)


class PackageInfoReader(BaseReader):
    enabled = True

    file_extensions = ['yml', 'py']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._md = Markdown(**self.settings['MARKDOWN'])

    def read(self, filename: str):
        info = pkg_info.from_package_info_file(Path(filename), offline='CI' not in os.environ)
        info['iconUri'] = obtain_icon(info['id'], info['iconUri'], self.settings['SITEURL'])
        metadata = {
            'title': info['title'],
            'override_save_as': f'apps/{info["id"]}.html',
            'template': 'app',
            'status': 'hidden',
            'modified': info['lastmodified'],
            'manifest': info['manifest'],
            'detailIcon': info.get('detailIconUri', info['iconUri']),
            'sponsor_links': funding.parse_links(info.get('funding', None)),
            'package_info': info
        }
        if 'PACKAGES' not in self.settings:
            self.settings['PACKAGES'] = {}
        self.settings['PACKAGES'][info['id']] = info
        return self._md.convert(info['description']), metadata


def readers_init(readers: Readers):
    readers.reader_classes['yml'] = PackageInfoReader
    readers.reader_classes['py'] = PackageInfoReader


def add_app_indices(generator: PagesGenerator):
    packages = list(sorted(generator.settings['PACKAGES'].values(), key=lambda info: info['title'].lower()))

    pages = list(chunked(packages, generator.settings['DEFAULT_PAGINATION']))
    pages_count = len(pages)
    for index, items in enumerate(pages):
        metadata = {
            'title': 'Apps',
            'override_save_as': 'apps/index.html' if index == 0 else f'apps/page/{index + 1}.html',
            'template': 'apps',
            'status': 'hidden',
            'packages': items,
            'pagination': pagination_data(index + 1, pages_count, apps_list_href) if pages_count > 1 else None,
        }
        generator.hidden_pages.append(Page('', metadata=metadata, settings=generator.settings,
                                           source_path=f'apps-page-{index + 1}.html', context=generator.context))

    def get_category_entries():
        entries = []
        for (category, title) in generator.settings['INDEX_APP_CATEGORIES']:
            entries.append({
                'title': title,
                'packages': [pkg for pkg in packages if pkg['category'] == category]
            })
        return entries

    metadata = {
        'title': 'Apps Repository',
        'override_save_as': 'index.html',
        'template': 'repo-index',
        'status': 'hidden',
        'categories': get_category_entries(),
    }
    generator.hidden_pages.append(Page('', metadata=metadata, settings=generator.settings,
                                       source_path=f'repo-index.html', context=generator.context))


def apps_list_href(page):
    return '/apps' if page <= 1 else f'/apps/page/{page}'


def add_app_api_data(generator: StaticGenerator):
    packages = generator.settings['PACKAGES'].values()

    def pool_list(pool: str):
        return list(sorted(filter(lambda pkg: pkg['pool'] == pool, packages), key=lambda pkg: pkg['title'].lower()))

    apidata.generate(pool_list('main'), Path(generator.settings['OUTPUT_PATH'], 'api'))
    apidata.generate(pool_list('non-free'), Path(generator.settings['OUTPUT_PATH'], 'api', 'non-free'))


def register():
    signals.readers_init.connect(readers_init)
    signals.page_generator_finalized.connect(add_app_indices)
    signals.static_generator_finalized.connect(add_app_api_data)
