import logging
import os
from itertools import chain

from markdown import Markdown
from more_itertools import chunked
from pelican import signals, Readers, PagesGenerator
from pelican.contents import Page
from pelican.readers import BaseReader
from pelican.themes.webosbrew import pagination_data

from repogen import funding
from repogen.common import parse_package_info

log = logging.getLogger(__name__)


class PackageInfoReader(BaseReader):
    enabled = True

    file_extensions = ['yml', 'py']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._md = Markdown(**self.settings['MARKDOWN'])

    def read(self, filename):
        info = parse_package_info(filename, offline='CI' not in os.environ)
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
        return self._md.convert(info['description']), metadata


def readers_init(readers: Readers):
    readers.reader_classes['yml'] = PackageInfoReader
    readers.reader_classes['py'] = PackageInfoReader


def add_app_indices(generator: PagesGenerator):
    packages = list(
        sorted(filter(lambda x: x is not None, map(lambda page: page.metadata.get('package_info', None),
                                                   chain(generator.pages, generator.hidden_pages))),
               key=lambda info: info['title'].lower()))

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


def apps_list_href(page):
    return '/apps' if page <= 1 else f'/apps/page/{page}'


def register():
    signals.readers_init.connect(readers_init)
    signals.page_generator_finalized.connect(add_app_indices)
    pass
