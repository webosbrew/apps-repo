import os
from pathlib import Path
from typing import IO

from repogen.common import copy_signature

_approot = Path(__file__).parent.parent

assert _approot.samefile(os.getcwd())

_cachepath = _approot.joinpath('cache')


def path(name: str) -> Path:
    return _cachepath.joinpath(name)


@copy_signature(open)
def open_file(file: str, *args, **kwargs) -> IO:
    if not _cachepath.exists():
        _cachepath.mkdir()
    return open(_cachepath.joinpath(file), *args, **kwargs)
