import html
import json.decoder
import tarfile
from pathlib import Path
from sys import stderr, exit

import requests.exceptions
from ar.archive import ArchiveError
from jsonschema.exceptions import ValidationError

from repogen import ipk_file, pkg_info, report
from repogen.common import EXIT_OK, EXIT_PACKAGE_PROBLEM, EXIT_TOOL_PROBLEM
from repogen.ipk_file import AppInfo

# Width of the icon preview, in pixels. It sits on the title line, so keep it near
# the line height. App icons are 130x130.
_ICON_WIDTH = 28

# How much app-supplied text the report shows. Long enough for a real description,
# short enough that a padded one cannot bury the rest of the comment.
_TITLE_LIMIT = 80
_DESCRIPTION_LIMIT = 600


def verify_ipk_id(appinfo: AppInfo, expected_id: str) -> str | None:
    """Return an error message if the IPK does not install as `expected_id`.

    The manifest is a separate file from the package it points at, so an id renamed
    there does not follow into the IPK. When the two disagree the TV installs the id
    baked into appinfo.json, which is what Homebrew Channel then matches against for
    updates — an app listed under one id and installed under another never registers
    as installed.
    """
    actual_id = appinfo.get('id', None)
    if not actual_id:
        return 'The IPK has no id in its appinfo.json'
    if actual_id != expected_id:
        return (f'The IPK installs as `{actual_id}`, but this package is `{expected_id}`. '
                f'Rebuild the IPK with the id set in appinfo.json, so the listed app and the '
                f'installed app are the same — otherwise updates will never be offered.')
    return None


def print_appinfo_table(appinfo: AppInfo, icon_uri: str):
    """Print what the app says about itself, for a reviewer to read.

    The title and the description come from appinfo.json in the IPK. Those are what
    the TV and Homebrew Channel show, and nothing in the package file overrides them,
    so a reviewer cannot see them without opening the package.

    Written as raw HTML, not a markdown table: the icon belongs on the title line the
    way a launcher shows it, and a markdown cell cannot hold a heading.
    """
    icon = ''
    if icon_uri.startswith('https://'):
        icon = f'<img src="{html.escape(icon_uri)}" width="{_ICON_WIDTH}" align="absmiddle" alt=""> '
    # A data: URI never renders in a comment, so that case shows the title alone.
    print('## App Info')
    print()
    print('<table><tr><td>')
    print(f'<h3>{icon}{report.as_html(appinfo.get("title", ""), _TITLE_LIMIT)}</h3>')
    description = appinfo.get('appDescription', '')
    if description:
        print(report.as_html(description, _DESCRIPTION_LIMIT))
    print('</td></tr></table>')
    print()


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
        exit(EXIT_PACKAGE_PROBLEM)
    except ValidationError as e:
        print(f'Could not parse package info: {e.message}')
        exit(EXIT_PACKAGE_PROBLEM)
    except requests.exceptions.HTTPError as e:
        # The server answered and said no — a wrong URL or a deleted release.
        print(f'Could not download package info: {e}')
        exit(EXIT_PACKAGE_PROBLEM)
    except requests.RequestException as e:
        print(f'Could not download package info: {e}', file=stderr)
        exit(EXIT_TOOL_PROBLEM)
    except IOError as e:
        print(f'Could not open package info file: {e.strerror}', file=stderr)
        exit(EXIT_TOOL_PROBLEM)

    try:
        ipk_url = pkginfo['manifest']['ipkUrl']
    except KeyError as e:
        print(f'Invalid package info: missing key {e}')
        exit(EXIT_PACKAGE_PROBLEM)

    try:
        with requests.get(ipk_url, allow_redirects=True) as resp:
            resp.raise_for_status()
            try:
                with open(args.output, 'wb') as f:
                    f.write(resp.content)
            except IOError as e:
                print(f'Could not write the IPK to {args.output}: {e.strerror}', file=stderr)
                exit(EXIT_TOOL_PROBLEM)
    except requests.exceptions.HTTPError as e:
        print(f'Could not download IPK: {e}')
        exit(EXIT_PACKAGE_PROBLEM)
    except requests.exceptions.RequestException as e:
        print(f'Could not download IPK: {e}', file=stderr)
        exit(EXIT_TOOL_PROBLEM)

    print(f'IPK file downloaded: {args.output}', file=stderr)

    try:
        _, ipk_appinfo = ipk_file.get_appinfo(args.output)
    except (ArchiveError, KeyError, ValueError, tarfile.TarError, OSError) as e:
        print(' * :x: Could not read appinfo.json from the IPK: %s' % e)
        exit(EXIT_PACKAGE_PROBLEM)

    print_appinfo_table(ipk_appinfo, pkginfo['iconUri'])

    id_error = verify_ipk_id(ipk_appinfo, pkginfo['id'])
    if id_error:
        print(' * :x: %s' % id_error)
        exit(EXIT_PACKAGE_PROBLEM)

    exit(EXIT_OK)
