# -*- coding: utf-8 -*-
import urllib
from os import PathLike
from pathlib import Path
from typing import Callable, TypeVar
from urllib.parse import urljoin

import requests

ITEMS_PER_PAGE: int = 50

F = TypeVar("F", bound=Callable)


def copy_signature(_: F) -> Callable[..., F]:
    return lambda f: f


def url_fixup(u: str) -> str:
    parsed = urllib.parse.urlparse(u)
    if parsed.scheme != 'https':
        return u
    segs = parsed.path.split('/')
    if parsed.hostname == 'github.com' and len(segs) == 7 and segs[3] == 'releases' and segs[4] == 'latest':
        resp = requests.get(u, allow_redirects=False)
        if resp.is_redirect:
            return resp.headers['location']
    return u


def url_size(u):
    content_length = requests.head(u, allow_redirects=True).headers.get('content-length', None)
    if not content_length:
        return 0
    return int(content_length)


@copy_signature(open)
def ensure_open(file: str | PathLike[str], *args, **kwargs):
    if not isinstance(file, Path):
        file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    return open(file, *args, **kwargs)
