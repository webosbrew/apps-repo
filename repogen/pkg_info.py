import locale
import sys
from datetime import datetime
from html import escape
from itertools import repeat
from pathlib import Path
from typing import TypedDict, List, NotRequired, Optional

import nh3

from repogen import validators
from repogen.common import url_fixup
from repogen.pkg_manifest import obtain_manifest, PackageManifest
from repogen.pkg_registery import PackageRequirements, PackageRegistry, parse_yml_package, load_py_package

locale.setlocale(locale.LC_TIME, '')

# Attributes kept when sanitizing rendered description HTML. 'class' and 'id' are
# allowed on every tag so markdown-generated heading anchors and code-highlighting
# spans survive sanitization.
_DESCRIPTION_ATTRIBUTES = {
    '*': {'class', 'id'},
    'a': {'href', 'hreflang', 'title'},
    'bdo': {'dir'},
    'blockquote': {'cite'},
    'col': {'align', 'char', 'charoff', 'span'},
    'colgroup': {'align', 'char', 'charoff', 'span'},
    'del': {'cite', 'datetime'},
    'h1': {'align'},
    'hr': {'align', 'size', 'width'},
    'img': {'align', 'alt', 'height', 'src', 'width'},
    'ins': {'cite', 'datetime'},
    'ol': {'start'},
    'p': {'align'},
    'q': {'cite'},
    'table': {'align', 'char', 'charoff', 'summary'},
    'tbody': {'align', 'char', 'charoff'},
    'td': {'align', 'char', 'charoff', 'colspan', 'headers', 'rowspan'},
    'tfoot': {'align', 'char', 'charoff'},
    'th': {'align', 'char', 'charoff', 'colspan', 'headers', 'rowspan', 'scope'},
    'thead': {'align', 'char', 'charoff'},
    'tr': {'align', 'char', 'charoff'},
}


def sanitize_description(html: str) -> str:
    """Sanitize rendered description HTML.

    Run this AFTER markdown conversion, never on the markdown source: an HTML
    sanitizer escapes markdown control characters (e.g. the '>' of a blockquote),
    which silently breaks the rendered output.
    """
    return nh3.clean(html, attributes=_DESCRIPTION_ATTRIBUTES, link_rel=None)


class Screenshot(TypedDict):
    url: str
    # None when the package file gives a bare URL.
    caption: Optional[str]
    # Pixel size, read from the image at build time (repogen.screenshots). Absent when
    # it could not be read.
    width: NotRequired[int]
    height: NotRequired[int]


def normalize_screenshots(value) -> List[Screenshot]:
    """Bring the two forms a package file may use — a bare URL, or a mapping with a
    url and optional caption — to one shape.

    Items that are neither are dropped rather than raised on: the schema reports them,
    and the linter still resolves a package that failed the schema, so a bad screenshot
    must not take the manifest checks down with it."""
    if not isinstance(value, list):
        return []
    screenshots: List[Screenshot] = []
    for item in value:
        if isinstance(item, str):
            screenshots.append({'url': item, 'caption': None})
        elif isinstance(item, dict) and isinstance(item.get('url', None), str):
            caption = item.get('caption', None)
            screenshots.append({'url': item['url'], 'caption': caption if isinstance(caption, str) else None})
    return screenshots


# Height of the screenshot strip in full_description.html, in CSS pixels.
_SCREENSHOT_HEIGHT = 240


def screenshots_html(screenshots: List[Screenshot]) -> str:
    """Screenshots as a strip for full_description.html, where clients that do not read
    the JSON field still see them.

    The inline styles are a default for webviews that bring no CSS; the classes let a
    client restyle or replace the strip. sanitize_description would strip both, so do
    not pass this through it: every value is escaped here, and the schema restricts the
    URLs to http(s).

    Clients go back to webOS 3.x webviews (Chromium 38), which know neither
    aspect-ratio nor a ratio derived from width/height attributes. So where the size is
    known the width is computed here, which reserves the box before the image loads and
    lets the caption wrap to it; where it is not, the width follows the image."""
    figures = []
    for shot in screenshots:
        url = escape(shot['url'])
        caption = escape(shot['caption'] or '')
        figcaption = f'<figcaption>{caption}</figcaption>' if caption else ''
        width, height = shot.get('width'), shot.get('height')
        if width and height:
            box_width = round(_SCREENSHOT_HEIGHT * width / height)
            figure_style = f'flex:none;margin:0;width:{box_width}px'
            img_attrs = (f'width="{width}" height="{height}" '
                         f'style="height:{_SCREENSHOT_HEIGHT}px;width:{box_width}px"')
        else:
            figure_style = 'flex:none;margin:0'
            img_attrs = f'style="height:{_SCREENSHOT_HEIGHT}px;width:auto"'
        figures.append(f'<figure class="webosbrew-screenshot" style="{figure_style}">'
                       f'<a href="{url}"><img src="{url}" alt="{caption}" '
                       f'{img_attrs} loading="lazy"></a>{figcaption}</figure>')
    return ('<div class="webosbrew-screenshots" style="display:flex;gap:8px;overflow-x:auto">\n'
            + '\n'.join(figures) + '\n</div>')


class PackageInfo(TypedDict):
    id: str
    title: str
    iconUri: str
    manifestUrl: str
    manifestUrlBeta: NotRequired[str]
    category: str
    description: str
    shortDescription: NotRequired[str]
    detailIconUri: NotRequired[str]
    funding: NotRequired[dict]
    screenshots: NotRequired[List[Screenshot]]
    pool: str
    requirements: NotRequired[PackageRequirements]
    manifest: PackageManifest
    manifestBeta: NotRequired[PackageManifest]
    lastmodified: datetime
    lastmodified_str: str
    # Only set on API output, for packages listed in FEATURED_APPS.
    featured: NotRequired[bool]


def parse_registry(info_path: Path, offline: bool = False) -> tuple[str, PackageRegistry]:
    """Read a package file, without checking it against the schema.

    Split out of load_registry so a caller that reports problems instead of aborting
    on the first one — the linter — can hold the parsed registry and keep going after
    a schema violation."""
    extension = info_path.suffix
    content: PackageRegistry
    if extension == '.yml':
        pkgid, content = parse_yml_package(info_path)
    elif extension == '.py':
        pkgid, content = load_py_package(info_path, offline)
    else:
        raise ValueError(f'Unsupported package file `{info_path.name}` — package files must be '
                         f'named `<package id>.yml`')
    return pkgid, content


def validate_registry(content: PackageRegistry) -> None:
    """Check a parsed registry against the package schema.

    Raises validators.SchemaValidationError listing every violation at once."""
    validator = validators.for_schema('packages/PackageInfo.json')
    validators.validate(validator, content)


def load_registry(info_path: Path, offline: bool = False) -> tuple[str, PackageRegistry]:
    pkgid, content = parse_registry(info_path, offline)
    validate_registry(content)
    return pkgid, content


def from_package_info_file(info_path: Path, offline=False) -> PackageInfo:
    pkgid, content = load_registry(info_path, offline)
    return from_package_info(pkgid, content, offline)


def from_package_info(pkgid: str, content: PackageRegistry, offline=False) -> PackageInfo:
    print(f'Parsing package info for {pkgid}', file=sys.stderr)
    manifest_url = url_fixup(content['manifestUrl'])
    pkginfo: PackageInfo = {
        'id': pkgid,
        'title': content['title'],
        'iconUri': content['iconUri'],
        'manifestUrl': manifest_url,
        'category': content['category'],
        # Raw markdown source; sanitized after conversion via sanitize_description().
        'description': content.get('description', ''),
    }
    if 'shortDescription' in content:
        pkginfo['shortDescription'] = content['shortDescription']
    if 'detailIconUri' in content:
        pkginfo['detailIconUri'] = content['detailIconUri']
    if 'funding' in content:
        pkginfo['funding'] = content['funding']
    if 'screenshots' in content:
        pkginfo['screenshots'] = normalize_screenshots(content['screenshots'])
    pkginfo['pool'] = valid_pool(content['pool'])
    if 'requirements' in content:
        pkginfo['requirements'] = content['requirements']
    manifest, lastmodified_r = obtain_manifest(pkgid, 'release', manifest_url, offline)
    if manifest:
        pkginfo['manifest'] = manifest
    lastmodified_b = None
    if 'manifestUrlBeta' in content:
        manifest_b, lastmodified_b = obtain_manifest(pkgid, 'beta', url_fixup(content['manifestUrlBeta']))
        if manifest_b:
            pkginfo['manifestBeta'] = manifest_b
    lastmodified = lastmodified_r, lastmodified_b
    pkginfo['lastmodified'] = max(d for d in lastmodified if d is not None)
    pkginfo['lastmodified_str'] = pkginfo['lastmodified'].strftime('%Y/%m/%d %H:%M:%S %Z')
    return pkginfo


def list_packages(pkgdir: Path, packages: List[str] | None = None, offline: bool = False) -> List[PackageInfo]:
    paths: List[Path] = [f for f in pkgdir.iterdir() if f.is_file()]

    def map_package_info(p: Path) -> PackageInfo | None:
        pkgid, content = load_registry(p, offline)
        if packages and pkgid not in packages:
            return None
        try:
            return from_package_info(pkgid, content, offline)
        except Exception as e:
            print(f'Error loading package info file {p.name}: {e}', file=sys.stderr)
            return None

    pkgs = sorted(filter(lambda x: x, map(map_package_info, paths)), key=lambda x: x['title'])
    return pkgs


def valid_pool(value: str) -> str:
    if value not in ['main', 'non-free']:
        raise ValueError(f'Unknown pool type {value}')
    return value
