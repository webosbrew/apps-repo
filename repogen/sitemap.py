"""Write the crawler files, sitemap.xml and robots.txt.

Crawlers already reach every app page through the links on /apps/, so the sitemap
is here for one reason: lastmod. Packages get version bumps often, and lastmod is
the only signal that tells a crawler to come back for an updated app page.

Both files need the site URL, which comes from content/extra/CNAME. Generating
them keeps that domain in one place instead of hardcoding it in a static file.
"""
import logging
from datetime import date
from pathlib import Path
from typing import List
from xml.sax.saxutils import escape

from repogen.pkg_info import PackageInfo

log = logging.getLogger(__name__)

_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n' \
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'


def _entry(url: str, lastmod: date = None) -> str:
    parts = [f'    <loc>{escape(url)}</loc>']
    if lastmod:
        parts.append(f'    <lastmod>{lastmod.isoformat()}</lastmod>')
    return '  <url>\n' + '\n'.join(parts) + '\n  </url>\n'


def generate(packages: List[PackageInfo], output_path: Path, siteurl: str):
    """Write output_path/sitemap.xml. Needs an absolute siteurl to build <loc>."""
    if not siteurl:
        log.info('SITEURL is empty, skipping sitemap.xml.')
        return

    base = siteurl.removesuffix('/')
    # Dates, not datetimes: lastmod needs no better precision, and package
    # timestamps mix naive and timezone-aware values that cannot be compared.
    modified = {pkg['id']: pkg['lastmodified'].date() for pkg in packages}
    # The index and the app list change whenever any package does.
    newest = max(modified.values(), default=None)

    entries = [_entry(f'{base}/', newest), _entry(f'{base}/apps/', newest), _entry(f'{base}/submit')]
    entries += [_entry(f'{base}/apps/{pkg_id}/', pkg_modified)
                for pkg_id, pkg_modified in sorted(modified.items())]

    with Path(output_path, 'sitemap.xml').open('w', encoding='utf-8') as f:
        f.write(_HEADER)
        f.writelines(entries)
        f.write('</urlset>\n')
    print('Generated sitemap.xml with %d urls.' % len(entries))


def generate_robots(output_path: Path, siteurl: str):
    """Write output_path/robots.txt. Every bot is welcome, assets are not."""
    lines = [
        '# Every crawler is welcome here, search engines and AI agents alike.',
        '# The content signals grant all three uses: search indexing, AI grounding',
        '# and model training. See https://contentsignals.org.',
        'User-agent: *',
        'Content-Signal: search=yes, ai-input=yes, ai-train=yes',
        'Allow: /',
        '',
        '# Read the JSON API instead of the pages: /api/apps.json holds every',
        '# package in one response. See /llms.txt.',
        '',
        '# Stylesheets stay open. Search engines render the pages to rank them,',
        '# and a page without its CSS renders wrong.',
        'Allow: /theme/styles/*.css',
        '',
        '# Assets carry no content worth crawling. The app pages and the API do.',
        'Disallow: /theme/',
        'Disallow: /apps/icons/',
        'Disallow: /apps/*/releases/',
        '',
    ]
    if siteurl:
        lines.append(f'Sitemap: {siteurl.removesuffix("/")}/sitemap.xml')
        lines.append('')

    with Path(output_path, 'robots.txt').open('w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('Generated robots.txt.')
