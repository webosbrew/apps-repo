import sys
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests
from markdown import Markdown
from markdown.treeprocessors import Treeprocessor

from repogen.common import parse_package_info


class PackageInfoLinter:

    @staticmethod
    def _assert(errors: [str], condition, message):
        if not condition:
            errors.append(message)

    class ImageProcessor(Treeprocessor):

        def __init__(self, errors: [str]):
            self.errors = errors

        def run(self, root: ElementTree.Element):
            for img in root.findall('.//img'):
                src = img.attrib['src']
                if urlparse(src).scheme != 'https':
                    self.errors.append("Use HTTPS URL for %s" % src)
            return None

    def lint(self, pkginfo) -> [str]:
        errors: [str] = []

        # Pool property
        if pkginfo.get('nopool', False):
            errors.append('pool property is required (`main` or `non-free`)')
        elif pkginfo['pool'] not in['main', 'non-free']:
            errors.append('pool property must be `main` or `non-free`')

        # Process icon
        icon_uri = urlparse(pkginfo['iconUri'])
        if icon_uri.scheme == 'data' or icon_uri.scheme == 'https':
            with requests.get(pkginfo['iconUri']) as resp:
                if resp.status_code == 200:
                    pass
                else:
                    errors.append("iconUri must be accessible")
        else:
            errors.append('iconUrl must be data URI or use HTTPS')

        # Process manifest
        PackageInfoLinter._validate_manifest_url(pkginfo['manifestUrl'], 'manifestUrl', errors)

        if 'manifestUrlBeta' in pkginfo:
            PackageInfoLinter._validate_manifest_url(pkginfo['manifestUrlBeta'], 'manifestUrlBeta', errors)

        description = pkginfo.get('description', '')
        mk = Markdown()
        # patch in the customized image pattern matcher with url checking
        mk.treeprocessors.register(
            self.ImageProcessor(errors), 'image_link', 1)
        mk.convert(description)
        return errors

    @staticmethod
    def _validate_manifest_url(url: str, key: str, e: [str]):
        manifest_url_pre = urlparse(url)
        if manifest_url_pre.scheme == 'https':
            with requests.get(url) as resp:
                if resp.status_code == 200:
                    resp.json()
                else:
                    e.append(f"{key} must be accessible")
        else:
            e.append(f"{key} must be HTTPS URL")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', required=True)
    args = parser.parse_args()

    pkginfo = parse_package_info(args.file)

    linter = PackageInfoLinter()
    errors = linter.lint(pkginfo)

    if len(errors):
        print('#### Issue:')
        for err in errors:
            print(' * %s' % err)
        exit(1)
    else:
        print('Check passed.')
