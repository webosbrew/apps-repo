import io
import json
import re
import tarfile
from typing import TypedDict, NotRequired

import ar


class AppInfo(TypedDict):
    id: str
    title: str
    version: str
    type: str
    appDescription: NotRequired[str]


def get_appinfo(ipk_path: str) -> AppInfo:
    with open(ipk_path, 'rb') as f:
        archive = ar.Archive(f)
        control_file = io.BytesIO(archive.open('control.tar.gz', mode='rb').read())
        with tarfile.open(fileobj=control_file, mode='r:gz') as control:
            with control.extractfile(control.getmember('control')) as cf:
                package_name = re.compile(r'Package: (.+)\n').match(cf.readline().decode('utf-8')).group(1)
        data_file = io.BytesIO(archive.open('data.tar.gz', mode='rb').read())
        with tarfile.open(fileobj=data_file, mode='r:gz') as data:
            with data.extractfile(data.getmember(f'usr/palm/applications/{package_name}/appinfo.json')) as af:
                return json.load(af)
