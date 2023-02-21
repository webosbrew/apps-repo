# -*- coding: utf-8 -*-
import urllib
from urllib.parse import urljoin

import requests

ITEMS_PER_PAGE: int = 30


def url_fixup(u: str) -> str:
    parsed = urllib.parse.urlparse(u)
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
