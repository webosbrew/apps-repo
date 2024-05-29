from pathlib import Path
from typing import Tuple, List
from urllib.parse import urlparse
from urllib.request import url2pathname
from xml.etree import ElementTree

import requests
from markdown import Markdown
from markdown.treeprocessors import Treeprocessor

from repogen import pkg_info
from repogen.pkg_info import PackageInfo


class PackageInfoLinter:

    @staticmethod
    def _assert(errors: [str], condition, message):
        if not condition:
            errors.append(message)

    class ImageProcessor(Treeprocessor):

        def __init__(self, errors: [str]):
            super().__init__()
            self.errors = errors

        def run(self, root: ElementTree.Element):
            for img in root.findall('.//img'):
                src = img.attrib['src']
                if urlparse(src).scheme != 'https':
                    self.errors.append("Use HTTPS URL for %s" % src)
            return None

    def lint(self, info: PackageInfo) -> Tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []

        # Pool property
        if info['pool'] not in ['main', 'non-free']:
            errors.append('pool property must be `main` or `non-free`')

        # Process icon
        icon_uri = urlparse(info['iconUri'])
        if icon_uri.scheme == 'data' or icon_uri.scheme == 'https':
            with requests.get(info['iconUri']) as resp:
                if resp.status_code == 200:
                    pass
                else:
                    errors.append("iconUri must be accessible")
        else:
            errors.append('iconUrl must be data URI or use HTTPS')

        # Process manifest
        manifest = info['manifest']
        if info['id'].startswith('org.webosbrew.'):
            source_url = manifest.get('sourceUrl', None)
            if not source_url or not source_url.startswith('https://github.com/webosbrew/'):
                warnings.append('Only package from github.com/webosbrew can have id starting with `org.webosbrew.`')

        description = info.get('description', '')
        mk = Markdown()
        # patch in the customized image pattern matcher with url checking
        mk.treeprocessors.register(
            self.ImageProcessor(errors), 'image_link', 1)
        mk.convert(description)
        return errors, warnings

    @staticmethod
    def _validate_manifest_url(url: str, key: str, e: [str]):
        manifest_url_pre = urlparse(url)
        match manifest_url_pre.scheme:
            case 'https':
                with requests.get(url) as resp:
                    if resp.status_code == 200:
                        resp.json()
                    else:
                        e.append(f"{key} must be accessible")
            case 'file':
                assert Path(url2pathname(manifest_url_pre.path)).exists()
            case _:
                e.append(f"{key} must be HTTPS URL")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', required=True)
    args = parser.parse_args()

    lint_pkginfo = pkg_info.from_package_info_file(Path(args.file))
    if lint_pkginfo is None:
        raise ValueError('No package info')

    linter = PackageInfoLinter()
    lint_errors, lint_warnings = linter.lint(lint_pkginfo)

    for err in lint_errors:
        print(' * :x: %s' % err)
    for warn in lint_warnings:
        print(' * :warning: %s' % warn)

    if not len(lint_errors) and not len(lint_warnings):
        print(':white_check_mark: Check passed.')
    exit(1 if len(lint_errors) else 0)
