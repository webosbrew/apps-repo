import os
import sys
from pathlib import Path
from typing import Tuple, List, Optional
from urllib.parse import urlparse
from urllib.request import url2pathname
from xml.etree import ElementTree

import requests
from markdown import Markdown
from markdown.treeprocessors import Treeprocessor

from repogen import pkg_info, validators
from repogen.common import EXIT_OK, EXIT_PACKAGE_PROBLEM, EXIT_TOOL_PROBLEM
from repogen.pkg_info import PackageInfo


_SOURCE_HELP = ('`pool: main` declares the app as open source, so its source must be publicly '
                'available. Point `sourceUrl` at the source repository, or set `pool: non-free`.')
_LICENSE_HELP = ('`pool: main` declares the app as open source, so its source repository should carry '
                 'a licence. Add a LICENSE file, or set `pool: non-free`.')


class PackageInfoLinter:

    @staticmethod
    def _assert(errors: [str], condition, message):
        if not condition:
            errors.append(message)

    @staticmethod
    def _github_repo(source_url: str) -> Optional[Tuple[str, str]]:
        """Return (owner, repo) if source_url points at a GitHub repository."""
        parsed = urlparse(source_url)
        if parsed.hostname not in ('github.com', 'www.github.com'):
            return None
        parts = [p for p in parsed.path.split('/') if p]
        if len(parts) < 2:
            return None
        return parts[0], parts[1].removesuffix('.git')

    def _check_source_license(self, info: PackageInfo, errors: List[str], warnings: List[str]):
        """Packages in the `main` pool claim to be open source. Hold them to it.

        Publicly reachable source is a hard requirement of that claim, so a missing or
        unreachable `sourceUrl` is an error. Whether the licence itself is present and
        recognisable is advisory: vendored code, forks and custom terms all need a human
        to judge, and several already-listed packages would fail an automated verdict.
        """
        if info['pool'] != 'main':
            return
        source_url = info['manifest'].get('sourceUrl', None)
        if not source_url:
            errors.append(f'sourceUrl is missing from the manifest. {_SOURCE_HELP}')
            return
        repo = self._github_repo(source_url)
        if not repo:
            # Elsewhere only reachability can be checked; the licence needs a manual look.
            self._check_url_reachable(source_url, errors, warnings)
            warnings.append(f'Could not check the licence of {source_url} automatically. {_LICENSE_HELP}')
            return
        owner, name = repo
        headers = {'Accept': 'application/vnd.github+json'}
        # Unauthenticated GitHub API allows 60 requests/hour per IP, which shared CI
        # runners burn through quickly. Use the workflow token when one is available.
        token = os.environ.get('GITHUB_TOKEN', None)
        if token:
            headers['Authorization'] = f'Bearer {token}'
        try:
            resp = requests.get(f'https://api.github.com/repos/{owner}/{name}', headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            warnings.append(f'Could not check the licence of {source_url}: {e}')
            return
        if resp.status_code == 404:
            errors.append(f'sourceUrl {source_url} is not a publicly accessible repository. {_SOURCE_HELP}')
            return
        if resp.status_code != 200:
            warnings.append(f'Could not check the licence of {source_url}: HTTP {resp.status_code}')
            return
        spdx = ((resp.json().get('license', None) or {}).get('spdx_id', None))
        if not spdx:
            warnings.append(f'No licence found in {source_url}. {_LICENSE_HELP}')
        elif spdx == 'NOASSERTION':
            # A licence file exists but GitHub could not identify it — custom or modified
            # terms are still a licence, so this only warrants a look, not a rejection.
            warnings.append(f'Licence of {source_url} could not be identified, please review it manually')

    @staticmethod
    def _check_url_reachable(source_url: str, errors: List[str], warnings: List[str]):
        """Confirm a non-GitHub sourceUrl is publicly readable."""
        try:
            resp = requests.get(source_url, timeout=30)
        except requests.exceptions.RequestException as e:
            # Can't distinguish "gone" from "having a bad minute" — don't fail the PR.
            warnings.append(f'Could not reach sourceUrl {source_url}: {e}')
            return
        if 400 <= resp.status_code < 500:
            errors.append(f'sourceUrl {source_url} is not publicly accessible '
                          f'(HTTP {resp.status_code}). {_SOURCE_HELP}')
        elif resp.status_code >= 500:
            warnings.append(f'Could not reach sourceUrl {source_url}: HTTP {resp.status_code}')

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

        if info['id'] != info['manifest']['id']:
            errors.append('id in manifest must match id in info')

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

        self._check_source_license(info, errors, warnings)

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

    try:
        lint_pkginfo = pkg_info.from_package_info_file(Path(args.file))
    except validators.SchemaValidationError as e:
        # Report every schema violation at once, not just the first.
        for msg in e.errors:
            print(' * :x: %s' % msg)
        exit(EXIT_PACKAGE_PROBLEM)
    except ValueError as e:
        # Bad filename/extension, unparseable YAML — report it in the PR comment
        # instead of dying with an empty report section.
        print(' * :x: %s' % e)
        exit(EXIT_PACKAGE_PROBLEM)
    except requests.exceptions.HTTPError as e:
        # The server answered, and said no: a deleted release or a wrong URL is the
        # submitter's to fix.
        print(' * :x: %s' % e)
        exit(EXIT_PACKAGE_PROBLEM)
    except requests.exceptions.RequestException as e:
        # Timeout, DNS, connection reset — nothing the submitter can act on.
        print(f'Could not download package info: {e}', file=sys.stderr)
        exit(EXIT_TOOL_PROBLEM)
    except IOError as e:
        print(f'Could not open package info file: {e.strerror}', file=sys.stderr)
        exit(EXIT_TOOL_PROBLEM)

    linter = PackageInfoLinter()
    lint_errors, lint_warnings = linter.lint(lint_pkginfo)

    for err in lint_errors:
        print(' * :x: %s' % err)
    for warn in lint_warnings:
        print(' * :warning: %s' % warn)

    if not len(lint_errors) and not len(lint_warnings):
        print(':white_check_mark: Check passed.')
    exit(EXIT_PACKAGE_PROBLEM if len(lint_errors) else EXIT_OK)
