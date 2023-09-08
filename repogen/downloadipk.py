from pathlib import Path

import requests

from repogen import pkg_info

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--info', required=True)
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()

    pkginfo = pkg_info.from_package_info_file(Path(args.info))
    with requests.get(pkginfo['manifest']['ipkUrl'], allow_redirects=True) as resp:
        with open(args.output, 'wb') as f:
            f.write(resp.content)
            print(f'IPK file downloaded: {args.output}')
