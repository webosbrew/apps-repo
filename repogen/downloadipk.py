import requests

from repogen.common import parse_package_info

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--info', required=True)
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()

    pkginfo = parse_package_info(args.info)
    with requests.get(pkginfo['manifest']['ipkUrl'], allow_redirects=True) as resp:
        with open(args.output, 'wb') as f:
            f.write(resp.content)
            print(f'IPK file downloaded: {args.output}')
