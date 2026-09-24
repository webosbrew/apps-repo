import os
import sys
from pathlib import Path
from typing import Tuple, List, Optional
from urllib.parse import urlparse
from urllib.request import url2pathname
from xml.etree import ElementTree

import requests
import yaml
from markdown import Markdown
from markdown.treeprocessors import Treeprocessor

from repogen import pkg_info, report, validators
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


def _manifest_of(info: PackageInfo) -> Optional[dict]:
    """The package's manifest, or None when it could not be fetched.

    The linter also runs on a partial info built straight from the package file, so
    every manifest-dependent check has to cope with it being absent."""
    manifest = info.get('manifest', None)
    return manifest if isinstance(manifest, dict) else None


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

    def _check_source_license(self, info: PackageInfo, errors: List[str], warnings: List[str],
                              skipped: List[str]):
        """Packages in the `main` pool claim to be open source. Hold them to it.

        Publicly reachable source is a hard requirement of that claim, so a missing or
        unreachable `sourceUrl` is an error. Whether the licence itself is present and
        recognisable is advisory: vendored code, forks and custom terms all need a human
        to judge, and several already-listed packages would fail an automated verdict.
        """
        if info.get('pool', None) != 'main':
            return
        manifest = _manifest_of(info)
        if manifest is None:
            # No manifest, so nothing to read a sourceUrl out of. Whatever stopped it
            # from being fetched is already reported.
            skipped.append('source licence')
            return
        source_url = manifest.get('sourceUrl', None)
        if not source_url:
            errors.append(f'sourceUrl is missing from the manifest. {_SOURCE_HELP}')
            return
        repo = self._github_repo(source_url)
        if not repo:
            # Elsewhere only reachability can be checked; the licence needs a manual look.
            self._check_url_reachable(source_url, errors, warnings)
            warnings.append(f'Could not check the licence of {report.as_code(source_url)} automatically. '
                            f'{_LICENSE_HELP}')
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
            warnings.append(f'Could not check the licence of {report.as_code(source_url)}: {report.as_code(e)}')
            return
        if resp.status_code == 404:
            errors.append(f'sourceUrl {report.as_code(source_url)} is not a publicly accessible repository. '
                          f'{_SOURCE_HELP}')
            return
        if resp.status_code != 200:
            warnings.append(f'Could not check the licence of {report.as_code(source_url)}: HTTP {resp.status_code}')
            return
        spdx = ((resp.json().get('license', None) or {}).get('spdx_id', None))
        if not spdx:
            warnings.append(f'No licence found in {report.as_code(source_url)}. {_LICENSE_HELP}')
        elif spdx == 'NOASSERTION':
            # A licence file exists but GitHub could not identify it — custom or modified
            # terms are still a licence, so this only warrants a look, not a rejection.
            warnings.append(f'Licence of {report.as_code(source_url)} could not be identified, '
                            f'please review it manually')

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
        try:
            resp = requests.get(icon_uri, timeout=30)
        except requests.exceptions.RequestException as e:
            # Can't distinguish "gone" from "having a bad minute" — don't fail the PR.
            warnings.append(f'Could not reach iconUri {report.as_code(icon_uri)}: {report.as_code(e)}')
            return
        with resp:
            if resp.status_code != 200:
                errors.append(f'iconUri must be accessible (HTTP {resp.status_code})')
                return
            content_type = resp.headers.get('Content-Type', '').split(';')[0].strip()
            if not content_type.startswith('image/'):
                errors.append(f'iconUri must serve an image, but it serves {report.as_code(content_type)}')
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
            warnings.append(f'Could not reach sourceUrl {report.as_code(source_url)}: {report.as_code(e)}')
            return
        if 400 <= resp.status_code < 500:
            errors.append(f'sourceUrl {report.as_code(source_url)} is not publicly accessible '
                          f'(HTTP {resp.status_code}). {_SOURCE_HELP}')
        elif resp.status_code >= 500:
            warnings.append(f'Could not reach sourceUrl {report.as_code(source_url)}: HTTP {resp.status_code}')

    def _check_id_namespace(self, info: PackageInfo, new_package: bool,
                            errors: List[str], warnings: List[str], skipped: List[str]):
        """`org.webosbrew.*` is the project's own namespace.

        An app carrying it looks official in the TV's launcher and in the Homebrew
        Channel listing, so packages from outside github.com/webosbrew must not claim it.

        Only enforced on newly added packages. Several listed apps predate the rule, and
        an id is what Homebrew Channel matches an install against — renaming one orphans
        every TV that already has it, which is a worse outcome than the squatted name.
        """
        if not info.get('id', '').startswith(_WEBOSBREW_PREFIX):
            return
        manifest = _manifest_of(info)
        if manifest is None:
            # Whether the package may claim the namespace depends on the manifest's
            # sourceUrl, which is not here. Refusing it on that basis would be a guess.
            skipped.append('id namespace')
            return
        source_url = manifest.get('sourceUrl', None)
        if source_url and source_url.startswith('https://github.com/webosbrew/'):
            return
        message = (f'`{info["id"]}` uses the `{_WEBOSBREW_PREFIX}` namespace, which is reserved for '
                   f'packages from github.com/webosbrew.')
        repo = self._github_repo(source_url) if source_url else None
        if repo:
            suggestion = f'com.github.{repo[0].lower()}.{info["id"][len(_WEBOSBREW_PREFIX):]}'
            message += f' Rename it to something under your own namespace, e.g. {report.as_code(suggestion)}.'
        else:
            message += ' Rename it to something under your own namespace, e.g. `com.github.<username>.<package>`.'
        if not new_package:
            warnings.append(message + ' It predates this rule, so it keeps the id it is '
                                      'already installed under.')
            return
        message += (' The id must be changed in the app itself (appinfo.json) and its manifest, '
                    'not just in this file.')
        errors.append(message)

    @staticmethod
    def _check_screenshots(info: PackageInfo, warnings: List[str]):
        """Screenshots are suggested, not required, so their absence is only a warning.

        Their shape is the schema's job. What is left is the scheme: the schema admits
        plain HTTP, but the site is served over HTTPS and hotlinks them."""
        if 'screenshots' not in info:
            warnings.append('No `screenshots`. A few screenshots help users see what the app does '
                            'before installing it, and are shown at the top of its page.')
            return
        screenshots = info['screenshots']
        if not isinstance(screenshots, list):
            return
        for shot in screenshots:
            url = shot.get('url', None) if isinstance(shot, dict) else shot
            if isinstance(url, str) and urlparse(url).scheme == 'http':
                warnings.append('Use HTTPS URL for screenshot %s' % report.as_code(url))

    class ImageProcessor(Treeprocessor):

        def __init__(self, errors: [str]):
            super().__init__()
            self.errors = errors

        def run(self, root: ElementTree.Element):
            for img in root.findall('.//img'):
                src = img.attrib['src']
                if urlparse(src).scheme != 'https':
                    self.errors.append('Use HTTPS URL for %s' % report.as_code(src))
            return None

    def lint(self, info: PackageInfo, new_package: bool = False,
             skipped: Optional[List[str]] = None) -> Tuple[List[str], List[str]]:
        """Lint `info`. `new_package` marks a package being added by this change, which
        some rules only apply to — see _check_id_namespace.

        `info` may be partial: when the manifest could not be fetched, or the file does
        not match the schema, the caller still runs every rule it can on what it has. A
        rule whose input is missing appends its name to `skipped` and does nothing, so
        the caller can say the report is incomplete rather than let it read as a pass.
        """
        errors: List[str] = []
        warnings: List[str] = []
        if skipped is None:
            skipped = []

        # Pool property
        pool = info.get('pool', None)
        if pool is None:
            skipped.append('pool')
        elif pool not in ['main', 'non-free']:
            errors.append('pool property must be `main` or `non-free`')

        manifest = _manifest_of(info)
        if manifest is None:
            skipped.append('manifest id')
        elif info.get('id', None) != manifest.get('id', None):
            errors.append('id in manifest must match id in info')

        # Process icon
        icon_uri = info.get('iconUri', None)
        if isinstance(icon_uri, str) and icon_uri:
            self._check_icon(icon_uri, errors, warnings)
        else:
            skipped.append('iconUri')

        # Process manifest
        self._check_id_namespace(info, new_package, errors, warnings, skipped)

        self._check_source_license(info, errors, warnings, skipped)

        self._check_screenshots(info, warnings)

        description = info.get('description', '')
        if isinstance(description, str):
            mk = Markdown()
            # patch in the customized image pattern matcher with url checking
            mk.treeprocessors.register(
                self.ImageProcessor(errors), 'image_link', 1)
            mk.convert(description)
        else:
            skipped.append('description')
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


def _describe_load_failure(e: Exception) -> str:
    """One line for a package file that parsed, but could not be turned into a package."""
    if isinstance(e, KeyError):
        key = e.args[0] if e.args else e
        return f'Missing field {report.as_code(key)} in the package file or its manifest'
    return report.as_markdown(e)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', required=True)
    parser.add_argument('-n', '--new', action='store_true',
                        help='the package is being added, not edited — enables rules that '
                             'would orphan existing installs if applied retroactively')
    args = parser.parse_args()

    # One report per run: every stage below appends here, and nothing is printed until
    # all of them have had their turn. A submitter fixing one problem at a time because
    # the check stops at the first one waits a CI round trip for each.
    lint_errors: List[str] = []
    lint_warnings: List[str] = []
    # Checks that could not run. What stopped them is already in lint_errors (or on
    # stderr), so these only decide whether the report admits to being partial.
    lint_skipped: List[str] = []
    # Set when something on our side failed — an unreachable host, an unreadable file.
    # Not the submitter's to fix, so it must not fail the PR, but it is not a pass either.
    tool_problem = False

    # Stage A: read the file. Terminal, and the only stage that is: there is nothing to
    # lint if the file will not parse.
    try:
        lint_pkgid, lint_registry = pkg_info.parse_registry(Path(args.file))
    except yaml.YAMLError as e:
        # YAMLError is not a ValueError, so this needs its own arm. The message carries
        # the line and column, which is the whole value of reporting it — collapsed to
        # one line to stay a single markdown bullet.
        detail = ' '.join(str(e).split())
        print(' * :x: Could not parse the package file: %s' % report.as_code(detail))
        exit(EXIT_PACKAGE_PROBLEM)
    except ValueError as e:
        # Bad filename/extension — report it in the PR comment instead of dying with an
        # empty report section.
        print(' * :x: %s' % e)
        exit(EXIT_PACKAGE_PROBLEM)
    except IOError as e:
        print(f'Could not open package info file: {e.strerror}', file=sys.stderr)
        exit(EXIT_TOOL_PROBLEM)

    # Stage B: schema. Every violation at once, and then carry on — the lint rules see
    # things the schema cannot.
    try:
        pkg_info.validate_registry(lint_registry)
    except validators.SchemaValidationError as e:
        # The messages quote the offending values, which are the submitter's.
        lint_errors.extend(report.as_markdown(message) for message in e.errors)
    schema_failed = bool(lint_errors)

    # Stage C: resolve the package, which fetches the manifest over the network.
    lint_pkginfo: Optional[PackageInfo] = None
    try:
        lint_pkginfo = pkg_info.from_package_info(lint_pkgid, lint_registry)
    except requests.exceptions.HTTPError as e:
        # The server answered, and said no: a deleted release or a wrong URL is the
        # submitter's to fix.
        lint_errors.append(report.as_markdown(e))
    except (KeyError, ValueError) as e:
        # A field is missing or unusable. If the schema already said so, saying it again
        # in different words only sends the submitter looking for a second problem.
        if not schema_failed:
            lint_errors.append(_describe_load_failure(e))
    except requests.exceptions.RequestException as e:
        # Timeout, DNS, connection reset — nothing the submitter can act on.
        print(f'Could not download package info: {e}', file=sys.stderr)
        tool_problem = True
    except IOError as e:
        # A manifest we were told to read locally, and could not.
        print(f'Could not read package manifest: {e}', file=sys.stderr)
        tool_problem = True

    if lint_pkginfo is None:
        # Best effort: lint what the file itself says, with no network. Fields that are
        # absent stay absent so the rules that need them report as skipped rather than
        # inventing a second complaint about a value the earlier stages already covered.
        registry = lint_registry if isinstance(lint_registry, dict) else {}
        partial: dict = {'id': lint_pkgid}
        for field in ('title', 'iconUri', 'pool', 'description', 'screenshots'):
            if field in registry:
                partial[field] = registry[field]
        # Deliberately partial; every rule copes with missing keys.
        # noinspection PyTypeChecker
        lint_pkginfo = partial

    # Stage D: the lint rules, always.
    linter = PackageInfoLinter()
    stage_errors, stage_warnings = linter.lint(lint_pkginfo, new_package=args.new, skipped=lint_skipped)
    lint_errors.extend(stage_errors)
    lint_warnings.extend(stage_warnings)

    for err in lint_errors:
        print(' * :x: %s' % err)
    for warn in lint_warnings:
        print(' * :warning: %s' % warn)

    if lint_skipped:
        # Say which checks did not run, so a short report is never mistaken for a clean
        # one. Who has to act depends on what stopped them: a bad package is the
        # submitter's, an unreachable host is ours.
        if lint_errors:
            print(' * :information_source: Could not check %s. Fix the problems above and push '
                  'again for the rest of the report.' % ', '.join(lint_skipped))
        else:
            print(' * :information_source: Could not check %s — the check itself could not '
                  'complete, see the job log. Nothing here for you to fix.' % ', '.join(lint_skipped))
    elif not lint_errors and not lint_warnings:
        print(':white_check_mark: Check passed.')

    if lint_errors:
        exit(EXIT_PACKAGE_PROBLEM)
    exit(EXIT_TOOL_PROBLEM if tool_problem else EXIT_OK)
