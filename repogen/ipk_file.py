import io
import json
import tarfile
from typing import TypedDict, NotRequired

import ar
from debian_parser import PackagesParser


class Control(TypedDict):
    version: str
    installedSize: int | None


class AppInfo(TypedDict):
    id: str
    title: str
    version: str
    type: str
    appDescription: NotRequired[str]


def get_appinfo(ipk_path: str) -> tuple[Control, AppInfo]:
    with open(ipk_path, 'rb') as f:
        archive = ar.Archive(f)
        control_file = io.BytesIO(archive.open('control.tar.gz', mode='rb').read())
        with tarfile.open(fileobj=control_file, mode='r:gz') as control:
            with control.extractfile(control.getmember('control')) as cf:
                parser = PackagesParser(cf.read().decode('utf-8'))
                control_data = {entry['tag']: entry['value'] for entry in parser.parse()[0]}
                package_name = control_data['Package']
                installed_size = int(control_data['Installed-Size'])
                control_info: Control = {
                    'version': control_data['Version'],
                    'installedSize': installed_size if installed_size > 10000 else None
                }
        data_file = io.BytesIO(archive.open('data.tar.gz', mode='rb').read())
        with tarfile.open(fileobj=data_file, mode='r:gz') as data:
            with data.extractfile(data.getmember(f'usr/palm/applications/{package_name}/appinfo.json')) as af:
                return control_info, json.load(af)
