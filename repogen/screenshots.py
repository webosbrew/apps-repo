"""Pixel sizes of package screenshots, so pages can reserve each image's box before it
loads, and so full_description.html can give old webviews an explicit width."""
import json
import logging
from pathlib import Path
from typing import List, Optional

import requests
from PIL import ImageFile

from repogen.pkg_info import Screenshot

log = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent / 'cache' / 'screenshot_sizes.json'
# Bump when the cached shape or the way sizes are read changes.
_CACHE_VERSION = 1

# Stop reading a response that has not revealed a size after this much. Image headers
# sit in the first few KiB; a JPEG with a large EXIF block pushes its frame header
# further, but nowhere near this.
_MAX_HEADER_BYTES = 2 * 1024 * 1024

_session = requests.Session()
_sizes: Optional[dict[str, list[int]]] = None


def _load_cache() -> dict[str, list[int]]:
    global _sizes
    if _sizes is None:
        _sizes = {}
        try:
            with _CACHE_FILE.open(encoding='utf-8') as f:
                cached = json.load(f)
            if cached.get('version') == _CACHE_VERSION:
                _sizes = cached['sizes']
        except (OSError, ValueError, KeyError, AttributeError):
            pass  # no cache, or an unreadable one: start empty
    return _sizes


def _save_cache(sizes: dict[str, list[int]]):
    try:
        _CACHE_FILE.parent.mkdir(exist_ok=True)
        with _CACHE_FILE.open('w', encoding='utf-8') as f:
            json.dump({'version': _CACHE_VERSION, 'sizes': sizes}, f, indent=1, sort_keys=True)
    except OSError:
        pass


def fetch_size(url: str) -> tuple[int, int]:
    """Read the image at `url` only until its header gives the size, then drop the
    connection. Follows redirects, which GitHub's `blob/...?raw=true` links rely on.
    Raises on any network, HTTP or decoding failure."""
    with _session.get(url, stream=True, timeout=30) as resp:
        resp.raise_for_status()
        parser = ImageFile.Parser()
        read = 0
        for chunk in resp.iter_content(chunk_size=16 * 1024):
            parser.feed(chunk)
            if parser.image:
                return parser.image.size
            read += len(chunk)
            if read >= _MAX_HEADER_BYTES:
                break
    raise ValueError(f'no image size in the first {read} bytes')


def with_sizes(pkgid: str, screenshots: List[Screenshot]) -> List[Screenshot]:
    """Copies of `screenshots` with `width` and `height` added where the size is known.

    Sizes are cached by URL across builds. A screenshot whose size cannot be read keeps
    no size, and so renders as it did before sizes existed; the failure is not cached,
    so the next build tries again."""
    sizes = _load_cache()
    result: List[Screenshot] = []
    changed = False
    for shot in screenshots:
        shot = {k: v for k, v in shot.items() if k not in ('width', 'height')}
        url = shot['url']
        size = sizes.get(url)
        if size is None:
            try:
                size = list(fetch_size(url))
            except Exception as e:  # anything at all: a screenshot must not fail the build
                log.warning('%s: cannot read size of screenshot %s: %s', pkgid, url, e)
            else:
                sizes[url] = size
                changed = True
        if size:
            shot['width'], shot['height'] = size
        result.append(shot)
    if changed:
        _save_cache(sizes)
    return result
