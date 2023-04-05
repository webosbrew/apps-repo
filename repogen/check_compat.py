import subprocess
import sys
from pathlib import Path

from repogen import pkg_info


def check(info_file: Path, package_file: Path):
    info = pkg_info.from_package_info_file(info_file)
    compat_check_args = ['--markdown', '--github-emoji', '--quiet']
    if 'requirements' in info:
        pass
    #     min_os =$(yq - r '.requirements.minOs // ""' ${changed_file})
    #     max_os =$(yq - r '.requirements.maxOs // ""' ${changed_file})
    #     max_os_exclusive =$(yq - r '.requirements.maxOsExclusive // ""' ${changed_file})
    #     if [ ! -z "${min_os}"]; then
    #     compat_check_args = "${compat_check_args} --min-os ${min_os}"
    #
    #
    # fi
    # if [ ! -z "${max_os}"]; then
    # compat_check_args = "${compat_check_args} --max-os ${max_os}"
    # fi
    # if [ ! -z "${max_os_exclusive}"]; then
    # compat_check_args = "${compat_check_args} --max-os-exclusive ${max_os_exclusive}"
    # fi
    check_args = ['webosbrew-ipk-compat-checker', *compat_check_args, str(package_file.absolute())]
    print(check_args, file=sys.stderr)
    p = subprocess.run(check_args, shell=True)
    exit(p.returncode)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--info', required=True)
    parser.add_argument('-p', '--package', required=True)
    args = parser.parse_args()
    check(Path(args.info), Path(args.package))
