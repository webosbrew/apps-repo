import json
import logging
import os
from datetime import datetime
from pathlib import Path

from markdown import Markdown
from pelican import signals, Readers, PagesGenerator, StaticGenerator
from pelican.contents import Page
from pelican.readers import BaseReader

from repogen import funding, apidata, pkg_info
from repogen.icons import obtain_icon

log = logging.getLogger(__name__)

# Bump when the cached shape or parse logic changes, to invalidate stale caches.
_PKGINFO_CACHE_VERSION = 2
_PKGINFO_CACHE_DIR = Path(__file__).parent.parent / 'cache'


class PackageInfoReader(BaseReader):
    enabled = True

    file_extensions = ['yml', 'py']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._md = Markdown(**self.settings['MARKDOWN'])

    def read(self, filename: str):
        offline = 'CI' not in os.environ
        siteurl = self.settings['SITEURL']
        info, content = self._read_package(Path(filename), offline, siteurl)

        metadata = {
            'title': info['title'],
            'override_save_as': f'apps/{info["id"]}/index.html',
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
        return content, metadata

    def _read_package(self, path: Path, offline: bool, siteurl: str) -> tuple[dict, str]:
        """Return (info, rendered_description_html), reusing a disk cache when possible.

        Parsing a package (manifest read, sanitize, markdown, icon fetch) runs for
        every package on every regen. Offline (local dev) we cache the result keyed
        on the source file's mtime, so unchanged packages skip the work. CI always
        parses fresh, since offline is False there.
        """
        mtime = path.stat().st_mtime
        cache_file = _PKGINFO_CACHE_DIR / f'pkginfo_{path.stem}.json'
        if offline and cache_file.exists():
            try:
                with cache_file.open(encoding='utf-8') as f:
                    cached = json.load(f)
                if (cached.get('version') == _PKGINFO_CACHE_VERSION
                        and cached.get('mtime') == mtime and cached.get('siteurl') == siteurl):
                    info = cached['info']
                    info['lastmodified'] = datetime.fromisoformat(info['lastmodified'])
                    return info, cached['content']
            except (OSError, ValueError, KeyError):
                pass  # fall through and reparse on any cache problem

        info = pkg_info.from_package_info_file(path, offline=offline)
        info['iconUri'] = obtain_icon(info['id'], info['iconUri'], siteurl)
        info['manifest']['iconUri'] = info['iconUri']
        content = pkg_info.sanitize_description(self._md.convert(info['description']))

        serialized = dict(info)
        serialized['lastmodified'] = info['lastmodified'].isoformat()
        try:
            _PKGINFO_CACHE_DIR.mkdir(exist_ok=True)
            with cache_file.open('w', encoding='utf-8') as f:
                json.dump({'version': _PKGINFO_CACHE_VERSION, 'mtime': mtime,
                           'siteurl': siteurl, 'info': serialized, 'content': content}, f)
        except OSError:
            pass
        return info, content


def readers_init(readers: Readers):
    readers.reader_classes['yml'] = PackageInfoReader
    readers.reader_classes['py'] = PackageInfoReader


def add_app_indices(generator: PagesGenerator):
    packages = list(sorted(generator.settings['PACKAGES'].values(), key=lambda info: info['title'].lower()))

    # Categories present in the catalog, used by the /apps filter sidebar.
    filter_categories = []
    for (category, title) in generator.settings['INDEX_APP_CATEGORIES']:
        count = sum(1 for pkg in packages if pkg['category'] == category)
        if count:
            filter_categories.append({'slug': category, 'title': title, 'count': count})

    generator.hidden_pages.append(Page('', metadata={
        'title': 'Apps',
        'override_save_as': 'apps/index.html',
        'template': 'apps',
        'status': 'hidden',
        'packages': packages,
        'filter_categories': filter_categories,
    }, settings=generator.settings, source_path='apps-page.html', context=generator.context))

    def get_category_entries():
        entries = []
        for (category, title) in generator.settings['INDEX_APP_CATEGORIES']:
            entries.append({
                'slug': category,
                'title': title,
                'packages': [pkg for pkg in packages if pkg['category'] == category]
            })
        return entries

    packages_by_id = generator.settings['PACKAGES']
    featured = [packages_by_id[pkgid] for pkgid in generator.settings.get('FEATURED_APPS', [])
                if pkgid in packages_by_id]

    metadata = {
        'title': 'Apps Repository',
        'override_save_as': 'index.html',
        'template': 'repo-index',
        'status': 'hidden',
        'categories': get_category_entries(),
        'featured': featured,
    }
    generator.hidden_pages.append(Page('', metadata=metadata, settings=generator.settings,
                                       source_path=f'repo-index.html', context=generator.context))


def add_app_api_data(generator: StaticGenerator):
    packages = generator.settings['PACKAGES'].values()
    output_path = generator.settings['OUTPUT_PATH']
    host_packages = generator.settings.get('HOST_PACKAGES', None)

    def pool_list(pool: str):
        return list(sorted(filter(lambda pkg: pkg['pool'] == pool, packages), key=lambda pkg: pkg['title'].lower()))

    apidata.generate(pool_list('main'), Path(output_path, 'api'), Path(output_path, 'apps'), host_packages)
    apidata.generate(pool_list('non-free'), Path(output_path, 'api', 'non-free'))


def register():
    signals.readers_init.connect(readers_init)
    signals.page_generator_finalized.connect(add_app_indices)
    signals.static_generator_finalized.connect(add_app_api_data)
