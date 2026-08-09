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


_WEBOSBREW_PREFIX = 'org.webosbrew.'
_SOURCE_HELP = ('`pool: main` declares the app as open source, so its source must be publicly '
                'available. Point `sourceUrl` at the source repository, or set `pool: non-free`.')
_LICENSE_HELP = ('`pool: main` declares the app as open source, so its source repository should carry '
                 'a licence. Add a LICENSE file, or set `pool: non-free`.')
# A 130x130 icon does not need more than this. Anything larger is a mistake, or an
# attempt to hand the site and the PR comment something other than an icon.
_ICON_SIZE_LIMIT = 512 * 1024
# How much of an untrusted value a message repeats back. Enough to recognise a URL,
# not enough to fill a comment.
_QUOTE_LIMIT = 200


def _quote(value) -> str:
    """Repeat an untrusted value back in a report message, as inline code.

    Manifests belong to their submitter and the report becomes a comment on this
    repository. A backtick or a line break would end the code span and let the value
    add markup of its own, so neither survives.
    """
    text = str(value).replace('`', "'").replace('\r', ' ').replace('\n', ' ')
    if len(text) > _QUOTE_LIMIT:
        text = text[:_QUOTE_LIMIT] + '…'
    return f'`{text}`'


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
            warnings.append(f'Could not check the licence of {_quote(source_url)} automatically. {_LICENSE_HELP}')
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
            warnings.append(f'Could not check the licence of {_quote(source_url)}: {_quote(e)}')
            return
        if resp.status_code == 404:
            errors.append(f'sourceUrl {_quote(source_url)} is not a publicly accessible repository. {_SOURCE_HELP}')
            return
        if resp.status_code != 200:
            warnings.append(f'Could not check the licence of {_quote(source_url)}: HTTP {resp.status_code}')
            return
        spdx = ((resp.json().get('license', None) or {}).get('spdx_id', None))
        if not spdx:
            warnings.append(f'No licence found in {_quote(source_url)}. {_LICENSE_HELP}')
        elif spdx == 'NOASSERTION':
            # A licence file exists but GitHub could not identify it — custom or modified
            # terms are still a licence, so this only warrants a look, not a rejection.
            warnings.append(f'Licence of {_quote(source_url)} could not be identified, please review it manually')

    @staticmethod
    def _check_icon(icon_uri: str, errors: List[str], warnings: List[str]):
        """Confirm the icon is an image, and small enough to show.

        The PR check renders this URL in a comment on this repository, so what it
        serves has to be an image and nothing else. Size is only advisory: a heavy
        icon is a waste, not a reason to reject a package.
        """
        scheme = urlparse(icon_uri).scheme
        if scheme == 'data':
            # Inline data, nothing to fetch. The schema already checks the syntax.
            return
        if scheme != 'https':
            errors.append('iconUri must be a data URI or use HTTPS')
            return
        with requests.get(icon_uri, timeout=30) as resp:
            if resp.status_code != 200:
                errors.append(f'iconUri must be accessible (HTTP {resp.status_code})')
                return
            content_type = resp.headers.get('Content-Type', '').split(';')[0].strip()
            if not content_type.startswith('image/'):
                errors.append(f'iconUri must serve an image, but it serves {_quote(content_type)}')
            if len(resp.content) > _ICON_SIZE_LIMIT:
                warnings.append(f'iconUri is {len(resp.content) // 1024} KiB. Icons show at 130x130, '
                                f'so anything over {_ICON_SIZE_LIMIT // 1024} KiB is wasted download.')

    @staticmethod
    def _check_url_reachable(source_url: str, errors: List[str], warnings: List[str]):
        """Confirm a non-GitHub sourceUrl is publicly readable."""
        try:
            resp = requests.get(source_url, timeout=30)
        except requests.exceptions.RequestException as e:
            # Can't distinguish "gone" from "having a bad minute" — don't fail the PR.
            warnings.append(f'Could not reach sourceUrl {_quote(source_url)}: {_quote(e)}')
            return
        if 400 <= resp.status_code < 500:
            errors.append(f'sourceUrl {_quote(source_url)} is not publicly accessible '
                          f'(HTTP {resp.status_code}). {_SOURCE_HELP}')
        elif resp.status_code >= 500:
            warnings.append(f'Could not reach sourceUrl {_quote(source_url)}: HTTP {resp.status_code}')

    def _check_id_namespace(self, info: PackageInfo, new_package: bool,
                            errors: List[str], warnings: List[str]):
        """`org.webosbrew.*` is the project's own namespace.

        An app carrying it looks official in the TV's launcher and in the Homebrew
        Channel listing, so packages from outside github.com/webosbrew must not claim it.

        Only enforced on newly added packages. Several listed apps predate the rule, and
        an id is what Homebrew Channel matches an install against — renaming one orphans
        every TV that already has it, which is a worse outcome than the squatted name.
        """
        if not info['id'].startswith(_WEBOSBREW_PREFIX):
            return
        source_url = info['manifest'].get('sourceUrl', None)
        if source_url and source_url.startswith('https://github.com/webosbrew/'):
            return
        message = (f'`{info["id"]}` uses the `{_WEBOSBREW_PREFIX}` namespace, which is reserved for '
                   f'packages from github.com/webosbrew.')
        repo = self._github_repo(source_url) if source_url else None
        if repo:
            suggestion = f'com.github.{repo[0].lower()}.{info["id"][len(_WEBOSBREW_PREFIX):]}'
            message += f' Rename it to something under your own namespace, e.g. {_quote(suggestion)}.'
        else:
            message += ' Rename it to something under your own namespace, e.g. `com.github.<username>.<package>`.'
        if not new_package:
            warnings.append(message + ' It predates this rule, so it keeps the id it is '
                                      'already installed under.')
            return
        message += (' The id must be changed in the app itself (appinfo.json) and its manifest, '
                    'not just in this file.')
        errors.append(message)

    class ImageProcessor(Treeprocessor):

        def __init__(self, errors: [str]):
            super().__init__()
            self.errors = errors

        def run(self, root: ElementTree.Element):
            for img in root.findall('.//img'):
                src = img.attrib['src']
                if urlparse(src).scheme != 'https':
                    self.errors.append('Use HTTPS URL for %s' % _quote(src))
            return None

    def lint(self, info: PackageInfo, new_package: bool = False) -> Tuple[List[str], List[str]]:
        """Lint `info`. `new_package` marks a package being added by this change, which
        some rules only apply to — see _check_id_namespace."""
        errors: List[str] = []
        warnings: List[str] = []

        # Pool property
        if info['pool'] not in ['main', 'non-free']:
            errors.append('pool property must be `main` or `non-free`')

        if info['id'] != info['manifest']['id']:
            errors.append('id in manifest must match id in info')

        # Process icon
        self._check_icon(info['iconUri'], errors, warnings)

        # Process manifest
        self._check_id_namespace(info, new_package, errors, warnings)

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
    parser.add_argument('-n', '--new', action='store_true',
                        help='the package is being added, not edited — enables rules that '
                             'would orphan existing installs if applied retroactively')
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
    lint_errors, lint_warnings = linter.lint(lint_pkginfo, new_package=args.new)

    for err in lint_errors:
        print(' * :x: %s' % err)
    for warn in lint_warnings:
        print(' * :warning: %s' % warn)

    if not len(lint_errors) and not len(lint_warnings):
        print(':white_check_mark: Check passed.')
    exit(EXIT_PACKAGE_PROBLEM if len(lint_errors) else EXIT_OK)
