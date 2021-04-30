import re
import sys
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests
from markdown import Markdown
from markdown.inlinepatterns import IMAGE_LINK_RE, Pattern
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
        manifest_url = urlparse(pkginfo['manifestUrl'])
        if manifest_url.scheme == 'https':
            with requests.get(pkginfo['manifestUrl']) as resp:
                if resp.status_code == 200:
                    resp.json()
                else:
                    errors.append("manifestUrl must be accessible")
        else:
            errors.append('manifestUrl must be HTTPS URL')

        description = pkginfo.get('description', '')
        mk = Markdown()
        # patch in the customized image pattern matcher with url checking
        mk.treeprocessors.register(
            self.ImageProcessor(errors), 'image_link', 1)
        mk.convert(description)
        return errors


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', required=True)
    args = parser.parse_args()

    pkginfo = parse_package_info(args.file)

    linter = PackageInfoLinter()
    print(f'Checking for {pkginfo["id"]} - {pkginfo["title"]}')
    errors = linter.lint(pkginfo)

    if len(errors):
        print('[!] Found problems:', file=sys.stderr)
        for err in errors:
            print(' * %s' % err, file=sys.stderr)
        exit(1)
    else:
        print('Check passed.')
