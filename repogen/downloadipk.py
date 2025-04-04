from sys import stderr, exit
from pathlib import Path
import json.decoder

import requests.exceptions

from repogen import pkg_info
from jsonschema.exceptions import ValidationError

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--info', required=True)
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()

    try:
        pkginfo = pkg_info.from_package_info_file(Path(args.info))
    except (requests.exceptions.JSONDecodeError, json.decoder.JSONDecodeError) as e:
        print(f'Could not parse manifest: {e}')
        exit(2)
    except requests.RequestException as e:
        print(f'Could not download package info: {e}')
        exit(5)
    except IOError as e:
        print(f'Could not open package info file: {e.strerror}')
        exit(3)
    except ValidationError as e:
        print(f'Could not parse package info: {e.message}')
        exit(4)

    try:
        ipk_url = pkginfo['manifest']['ipkUrl']
    except KeyError as e:
        print(f'Invalid package info: missing key {e}')
        exit(6)

    try:
        with requests.get(ipk_url, allow_redirects=True) as resp:
            resp.raise_for_status()
            try:
                with open(args.output, 'wb') as f:
                    try:
                        f.write(resp.content)
                    except IOError as e:
                        print(f'Could not write to output IPK file: {e.strerror}')
                        exit(9)
                    else:
                        print(f'IPK file downloaded: {args.output}', file=stderr)
            except IOError as e:
                print(f'Could not open output IPK file: {e.strerror}')
                exit(8)
    except requests.exceptions.RequestException as e:
        print(f'Could not download IPK: {e}')
        exit(7)
