import subprocess
from pathlib import Path

import shellescape

from repogen import pkg_info
from repogen.pkg_info import PackageInfo


def check(info_file: Path, package_file: Path):
    info: PackageInfo = pkg_info.from_package_info_file(info_file)
    compat_check_args = ['--markdown', '--github-emoji', '--quiet']
    if 'requirements' in info:
        if 'webosRelease' in info['requirements']:
            compat_check_args.extend(['--os', shellescape.quote(info["requirements"]["webosRelease"])])
    p = subprocess.run(f'webosbrew-ipk-compat-checker {" ".join(compat_check_args)} {str(package_file.absolute())}',
                       shell=True)
    exit(p.returncode)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--info', required=True)
    parser.add_argument('-p', '--package', required=True)
    args = parser.parse_args()
    check(Path(args.info), Path(args.package))
