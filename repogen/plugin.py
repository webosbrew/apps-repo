import logging
import os

from markdown import Markdown
from pelican import signals, Readers
from pelican.readers import BaseReader

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
            'detailIcon': info.get('detailIconUri', info['iconUri'])
        }
        return self._md.convert(info['description']), metadata


def readers_init(readers: Readers):
    readers.reader_classes['yml'] = PackageInfoReader
    readers.reader_classes['py'] = PackageInfoReader


def register():
    signals.readers_init.connect(readers_init)
    pass
