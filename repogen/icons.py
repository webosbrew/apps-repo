import os
from pathlib import Path

import requests

_approot = Path(__file__).parent.parent

assert _approot.samefile(os.getcwd())

_iconspath = _approot.joinpath('content', 'apps', 'icons')

_iconspath.mkdir(parents=True, exist_ok=True)


def obtain_icon(pkg_id: str, uri: str, siteurl: str) -> str:
    resp = requests.get(uri, allow_redirects=True)
    extension = uri[uri.rfind('.') + 1:]
    icon_name = f'{pkg_id}.{extension}'
    icon_path = _iconspath.joinpath(icon_name)
    out_uri = f'{siteurl.removesuffix("/")}/apps/icons/{icon_name}'
    if icon_path.exists():
        return out_uri
    with icon_path.open('wb') as icon_f:
        icon_f.write(resp.content)
    return out_uri
