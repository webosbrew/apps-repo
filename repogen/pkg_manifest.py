import json
import os
from datetime import datetime
from email.utils import parsedate_to_datetime
from json import JSONDecodeError
from os import path
from typing import Tuple, TypedDict, Optional
from urllib.parse import urljoin

import requests

from repogen.common import url_fixup, url_size


class PackageManifest(TypedDict):
    id: str
    title: str
    version: str
    type: str
    appDescription: Optional[str]
    ipkUrl: str
    ipkSize: int


def obtain_manifest(pkgid: str, channel: str, url: str, offline: bool = False) -> Tuple[PackageManifest, datetime]:
    if not path.exists('cache'):
        os.mkdir('cache')
    cache_file = path.join('cache', f'manifest_{pkgid}_{channel}.json')
    try:
        if offline:
            raise requests.exceptions.ConnectionError('Offline')
        url = url_fixup(url)
        resp = requests.get(url=url, allow_redirects=True)
        manifest = resp.json()
        manifest['ipkUrl'] = urljoin(url, manifest['ipkUrl'])
        manifest['ipkSize'] = url_size(manifest['ipkUrl'])
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f)
        last_modified = datetime.now()
        if 'last-modified' in resp.headers:
            last_modified = parsedate_to_datetime(
                resp.headers['last-modified'])
            os.utime(cache_file, (last_modified.timestamp(), last_modified.timestamp()))
        return manifest, last_modified
    except requests.exceptions.RequestException as e:
        if path.exists(cache_file):
            try:
                with open(cache_file, encoding='utf-8') as f:
                    return json.load(f), datetime.fromtimestamp(os.stat(cache_file).st_mtime)
            except IOError or JSONDecodeError:
                os.unlink(cache_file)
        raise e
