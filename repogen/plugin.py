import json
import logging
import os
from datetime import datetime
from pathlib import Path

from markdown import Markdown
from pelican import signals, Readers, PagesGenerator, StaticGenerator
from pelican.contents import Page
from pelican.readers import BaseReader

from repogen import funding, apidata, openapi, pkg_info, screenshots, sitemap
from repogen.icons import obtain_icon

log = logging.getLogger(__name__)

# Bump when the cached shape or parse logic changes, to invalidate stale caches.
_PKGINFO_CACHE_VERSION = 6
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
        if info.get('screenshots'):
            # Outside the pkginfo cache, which lives only offline and until the package
            # file changes; sizes have their own cache keyed by URL, used in CI too.
            info['screenshots'] = screenshots.with_sizes(info['id'], info['screenshots'])

        metadata = {
            'title': info['title'],
            'override_save_as': f'apps/{info["id"]}/index.html',
            # Keep the trailing slash: GitHub Pages 301-redirects the slashless form.
            'override_url': f'apps/{info["id"]}/',
            'description': info.get('shortDescription') or info['manifest'].get('appDescription'),
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


def resolve_groups(packages: list, groups: list[dict]) -> list[dict]:
    """Gather the members of each group in conf/groups.yml, lead first, then alphabetical.

    Only groups with at least two members in the catalogue are returned: a group of one
    is shown as a plain app. Raises on a package naming an unknown group, on members in
    different categories, and on a lead that is in the catalogue but not in its group."""
    by_slug = {g['slug']: g for g in groups}
    by_id = {pkg['id']: pkg for pkg in packages}
    members: dict[str, list] = {g['slug']: [] for g in groups}
    problems = []
    for pkg in packages:
        slug = pkg.get('group')
        if slug is None:
            continue
        if slug not in by_slug:
            problems.append(f'{pkg["id"]}: group `{slug}` is not in conf/groups.yml')
            continue
        members[slug].append(pkg)

    resolved = []
    for group in groups:
        slug, in_group = group['slug'], members[group['slug']]
        categories = sorted({pkg['category'] for pkg in in_group})
        if len(categories) > 1:
            problems.append(f'group `{slug}`: members are in different categories ({", ".join(categories)})')
        lead = by_id.get(group['lead'])
        if lead is not None and lead.get('group') != slug:
            problems.append(f'group `{slug}`: lead {group["lead"]} does not set `group: {slug}`')
        if not in_group:
            continue
        if lead is None:
            lead = in_group[0]
            log.warning('Group %s: lead %s is not in the catalogue; %s leads instead',
                        slug, group['lead'], lead['id'])
        if len(in_group) < 2:
            continue
        resolved.append({
            'slug': slug,
            'title': group['title'],
            'category': categories[0],
            'lead': lead,
            'members': [lead] + [pkg for pkg in in_group if pkg is not lead],
        })
    if problems:
        raise ValueError('App groups are inconsistent:\n' + '\n'.join(problems))
    return resolved


def fold_tiles(packages: list, groups: list[dict], pinned: dict[str, int], keep_members: bool) -> list[dict]:
    """Order the tiles of a grid or shelf: pinned apps first, then by title, where each group
    is one tile titled and sorted by the group's title (and pinned where its lead is).

    Entries are `{'package': pkg, 'member': slug or None}` or `{'group': group}`. With
    `keep_members`, members stay in the list at their own position, flagged with their group
    so the page can hide them while the group is folded; otherwise they are left out."""
    by_slug = {g['slug']: g for g in groups}
    rest = len(pinned)
    keyed = []
    present = {pkg['id'] for pkg in packages}
    for group in groups:
        if group['lead']['id'] in present:
            keyed.append(((pinned.get(group['lead']['id'], rest), group['title'].lower()), {'group': group}))
    for pkg in packages:
        slug = pkg.get('group') if pkg.get('group') in by_slug else None
        if slug and not keep_members:
            continue
        keyed.append(((pinned.get(pkg['id'], rest), pkg['title'].lower()), {'package': pkg, 'member': slug}))
    keyed.sort(key=lambda item: item[0])
    return [entry for _, entry in keyed]


def add_app_indices(generator: PagesGenerator):
    packages = list(sorted(generator.settings['PACKAGES'].values(), key=lambda info: info['title'].lower()))

    by_id = {pkg['id']: pkg for pkg in packages}
    # Pinned apps lead their category, in the order conf/categories.yml lists them.
    pinned: dict[str, int] = {}
    for cat in generator.settings['APP_CATEGORIES']:
        for rank, pkgid in enumerate(cat.get('pinned', [])):
            pkg = by_id.get(pkgid)
            if pkg is None:
                log.warning('Category %s pins %s, which is not in the catalogue', cat['slug'], pkgid)
            elif pkg['category'] != cat['slug']:
                raise ValueError(f'Category `{cat["slug"]}` pins {pkgid}, which is in `{pkg["category"]}`')
            else:
                pinned[pkgid] = rank

    categories = generator.settings['APP_CATEGORIES']
    known = {cat['slug'] for cat in categories}
    unknown = sorted({pkg['category'] for pkg in packages} - known)
    if unknown:
        raise ValueError(f'Package categories missing from APP_CATEGORIES: {", ".join(unknown)}')

    # Look-alike apps folded behind one tile; members are alphabetical as `packages` is.
    groups = resolve_groups(packages, generator.settings['APP_GROUPS'])

    # Categories present in the catalog, used by the /apps filter sidebar.
    filter_categories = []
    for cat in categories:
        count = sum(1 for pkg in packages if pkg['category'] == cat['slug'])
        if count:
            filter_categories.append({'slug': cat['slug'], 'title': cat['title'], 'count': count})

    generator.hidden_pages.append(Page('', metadata={
        'title': 'Apps',
        'override_save_as': 'apps/index.html',
        'override_url': 'apps/',
        'description': f'Browse all {len(packages)} homebrew apps for LG webOS TVs, '
                       f'installable through the Homebrew Channel.',
        'template': 'apps',
        'status': 'hidden',
        'packages': packages,
        'filter_categories': filter_categories,
        'groups': groups,
        # All tiles by title (the grid's JS re-sorts pins within a category); members kept, hidden while folded.
        'tiles': fold_tiles(packages, groups, {}, keep_members=True),
        'pinned': pinned,
    }, settings=generator.settings, source_path='apps-page.html', context=generator.context))

    def get_category_entries():
        entries = []
        for cat in categories:
            if not cat['index']:
                continue
            in_category = [pkg for pkg in packages if pkg['category'] == cat['slug']]
            entries.append({
                'slug': cat['slug'],
                'title': cat['title'],
                # Pinned apps first, in conf/categories.yml order; sorted() keeps the rest alphabetical.
                'packages': sorted(in_category, key=lambda pkg: pinned.get(pkg['id'], len(pinned))),
                'tiles': fold_tiles(in_category, [g for g in groups if g['category'] == cat['slug']],
                                    pinned, keep_members=False),
            })
        return entries

    packages_by_id = generator.settings['PACKAGES']
    featured = [packages_by_id[pkgid] for pkgid in generator.settings.get('FEATURED_APPS', [])
                if pkgid in packages_by_id]

    metadata = {
        'title': 'Apps Repository',
        'override_save_as': 'index.html',
        'override_url': '',
        'description': 'Homebrew apps for LG webOS TVs. Install media players, games, '
                       'ambient light tools and utilities through the Homebrew Channel.',
        'template': 'repo-index',
        'status': 'hidden',
        'categories': get_category_entries(),
        'featured': featured,
        'groups': groups,
    }
    generator.hidden_pages.append(Page('', metadata=metadata, settings=generator.settings,
                                       source_path=f'repo-index.html', context=generator.context))


def add_app_api_data(generator: StaticGenerator):
    packages = generator.settings['PACKAGES'].values()
    output_path = generator.settings['OUTPUT_PATH']
    host_packages = generator.settings.get('HOST_PACKAGES', None)
    featured_packages = set(generator.settings.get('FEATURED_APPS', []))

    def pool_list(pool: str):
        return list(sorted(filter(lambda pkg: pkg['pool'] == pool, packages), key=lambda pkg: pkg['title'].lower()))

    categories = generator.settings['APP_CATEGORIES']
    apidata.generate(pool_list('main'), Path(output_path, 'api', apidata.POOL_DIRS['main']),
                     Path(output_path, 'apps'), host_packages, featured_packages, categories=categories)
    apidata.generate(pool_list('non-free'), Path(output_path, 'api', apidata.POOL_DIRS['non-free']),
                     categories=categories)
    openapi.generate(Path(output_path, 'api'), categories)


def add_crawler_files(generator: StaticGenerator):
    packages = list(generator.settings['PACKAGES'].values())
    output_path = Path(generator.settings['OUTPUT_PATH'])
    siteurl = generator.settings['SITEURL']
    sitemap.generate(packages, output_path, siteurl)
    sitemap.generate_robots(output_path, siteurl)


def register():
    signals.readers_init.connect(readers_init)
    signals.page_generator_finalized.connect(add_app_indices)
    signals.static_generator_finalized.connect(add_app_api_data)
    signals.static_generator_finalized.connect(add_crawler_files)
