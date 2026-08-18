import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict

from repogen import pkg_info, report
from repogen.common import EXIT_OK, EXIT_PACKAGE_PROBLEM, EXIT_TOOL_PROBLEM
from repogen.pkg_info import PackageInfo

# Cells of the markdown compatibility table, e.g. '| ES2015 support | :x: | :ok: |'.
_TABLE_ROW = re.compile(r'^\|(.+)\|$')

# Shapes webosbrew-ipk-verify writes: headings, bullets, tables, and collapsible
# sections. Everything else in its output is plain text.
_HEADING = re.compile(r'^(#{1,6}) +(.*)$')
_BULLET = re.compile(r'^([*+-] +)(.*)$')
_SUMMARY = re.compile(r'^<summary>(.*)</summary>$')
_DETAILS = ('<details>', '</details>')

# webosbrew-ipk-verify exit codes. Only INCOMPATIBLE and MALFORMED say anything
# about the package; the rest mean the tool itself could not do its job.
_VERIFY_OK = 0
_VERIFY_INCOMPATIBLE = 1
_VERIFY_BAD_ARGS = 2
_VERIFY_BAD_INPUT = 3
_VERIFY_NO_FW_DATA = 4
_VERIFY_WRITE_FAILED = 5
_VERIFY_MALFORMED = 6

_VERIFY_REASONS = {
    _VERIFY_BAD_ARGS: 'the tool rejected its command line',
    _VERIFY_BAD_INPUT: 'the IPK is missing, unreadable, or not in the expected format',
    _VERIFY_NO_FW_DATA: 'no firmware data is available',
    _VERIFY_WRITE_FAILED: 'the tool could not write its output',
}


def sanitize(output: str) -> str:
    """Rebuild the compatibility report from shapes this code recognises.

    webosbrew-ipk-verify reads names out of the package and writes them into its
    report: the app and service ids, the file names of the binaries, the symbols
    they import, the URLs a web app loads. All of that belongs to the submitter, and
    the report becomes a comment on this repository, so keep the structure the tool
    produced and escape everything it carries.

    A value holding a line break can still forge a line of its own, and a forged
    line that looks like a heading stays a heading. It cannot carry content, which
    is what matters, and telling the two apart from out here is not possible.
    """
    lines: List[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append('')
            continue
        if stripped in _DETAILS:
            lines.append(stripped)
            continue
        summary = _SUMMARY.match(stripped)
        if summary:
            lines.append(f'<summary>{report.as_markdown(summary.group(1))}</summary>')
            continue
        heading = _HEADING.match(stripped)
        if heading:
            lines.append(f'{heading.group(1)} {report.as_markdown(heading.group(2))}')
            continue
        row = _TABLE_ROW.match(stripped)
        if row:
            cells = row.group(1).split('|')
            if set(''.join(cells)) <= set('-: '):
                lines.append(stripped)  # separator row, nothing to escape
            else:
                lines.append('| %s |' % ' | '.join(report.as_markdown(c.strip()) for c in cells))
            continue
        bullet = _BULLET.match(stripped)
        if bullet:
            lines.append(f'{bullet.group(1)}{report.as_markdown(bullet.group(2))}')
            continue
        text = report.as_markdown(stripped)
        if text[:1] in '#>=~`+-0123456789':
            # Plain text, so nothing here may start a block of its own.
            text = f'\\{text}'
        lines.append(text)
    return '\n'.join(lines)


def _split_row(line: str) -> Optional[List[str]]:
    match = _TABLE_ROW.match(line.strip())
    if not match:
        return None
    return [cell.strip() for cell in match.group(1).split('|')]


def earliest_supported_release(report: str) -> Optional[str]:
    """Find the oldest webOS release every feature row marks as supported.

    The compatibility report renders one column per tested release and one ':ok:'/':x:'
    row per required feature. The oldest release no row marks ':x:' is the floor the
    package should declare. Returns None if no table can be read or nothing passes.

    A report holds one table per component (app, service, ...) and those tables do not
    have to share columns, so results are keyed by release rather than column position.
    """
    order: List[str] = []
    supported: Dict[str, bool] = {}
    releases: List[str] = []
    for line in report.splitlines():
        cells = _split_row(line)
        if not cells or set(''.join(cells)) <= set('-: '):
            continue  # separator row, or nothing to read
        if ':ok:' not in cells and ':x:' not in cells:
            if not cells[0]:
                # Header of a new table: empty corner cell, then the release versions.
                releases = cells[1:]
                for release in releases:
                    if release not in supported:
                        supported[release] = True
                        order.append(release)
            continue  # descriptive row, e.g. the web engine versions
        for release, cell in zip(releases, cells[1:]):
            if cell == ':x:':
                supported[release] = False
    return next((release for release in order if supported[release]), None)


def check(info_file: Path, package_file: Path):
    info: PackageInfo = pkg_info.from_package_info_file(info_file)
    declared_release = info.get('requirements', {}).get('webosRelease', None)
    compat_check_args = ['--format', 'markdown', '--details']
    if declared_release:
        compat_check_args.extend(['--fw-releases', declared_release])
    p = subprocess.run(args=['webosbrew-ipk-verify', *compat_check_args, str(package_file.absolute())],
                       shell=False, stdout=subprocess.PIPE, universal_newlines=True)
    # The package id is already the section this report sits in.
    verify_report = sanitize('\n'.join(line for line in p.stdout.splitlines()
                                       if not line.startswith('## Package')))
    print(verify_report)
    if p.returncode == _VERIFY_OK:
        exit(EXIT_OK)

    if p.returncode == _VERIFY_INCOMPATIBLE:
        _print_release_tip(verify_report, declared_release)
        exit(EXIT_PACKAGE_PROBLEM)

    if p.returncode == _VERIFY_MALFORMED:
        # No release tip here: no `webosRelease` makes such a package installable.
        # Point at a packager that does not produce one instead.
        _print_packager_tip()
        exit(EXIT_PACKAGE_PROBLEM)

    if p.returncode == _VERIFY_NO_FW_DATA and declared_release:
        # --fw-releases matched nothing. With a declared range that is the input we can
        # attribute, so report it as the submitter's to fix rather than a broken runner.
        print()
        print(f' * :x: `webosRelease: \'{declared_release}\'` matches no known webOS release')
        exit(EXIT_PACKAGE_PROBLEM)

    reason = _VERIFY_REASONS.get(p.returncode, f'it exited with status {p.returncode}')
    print()
    print('> [!NOTE]')
    print(f'> The compatibility check could not run — {reason}. This is not a problem with the submission.')
    exit(EXIT_TOOL_PROBLEM)


def _print_packager_tip():
    """Name a packager that does not produce a package the TV refuses.

    Every such package seen so far came out of `@webosose/ares-cli`, the old
    package name. Its node-tar 2 takes the file timestamps from a stat object
    that fstream fills with `Object.keys`, and Node 22 moved those fields to the
    prototype, so every file ends up dated 1970-01-01. Its successor and
    `ares-cli-rs` both read the timestamps themselves and are unaffected.

    Worded as a maybe: the exit code says the package will not install, not what
    built it.
    """
    print()
    print('> [!TIP]')
    print('> If this package was built with `@webosose/ares-cli`, that is the likely cause — on '
          'Node.js 22 and later it dates every file 1970-01-01. Build it with the successor to '
          'that package, which takes the same `ares-package` command:')
    print('>')
    print('> ```sh')
    print('> npm uninstall @webosose/ares-cli && npm install --save-dev @webos-tools/cli')
    print('> ```')
    print('>')
    print('> [`ares-cli-rs`](https://github.com/webosbrew/ares-cli-rs) works too. Building in CI '
          'rather than by hand keeps the toolchain pinned.')


def _print_release_tip(report: str, declared_release: Optional[str]):
    floor = earliest_supported_release(report)
    print()
    print('> [!TIP]')
    if not floor:
        print('> If the package is not meant to support the releases listed above, declare the oldest one '
              'it does support as `requirements.webosRelease` in the package file.')
        return
    if declared_release:
        print(f'> `webosRelease: \'{declared_release}\'` is declared, but the oldest tested release this '
              f'package runs on is **{floor}**. Raise the requirement to match what it supports:')
    else:
        print(f'> The oldest tested release this package runs on is **{floor}**. If it is not meant to '
              f'support anything older, declare that and this check will pass:')
    print('>')
    print('> ```yaml')
    print('> requirements:')
    print(f'>   webosRelease: \'>={".".join(floor.split(".")[:2])}\'')
    print('> ```')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--info', required=True)
    parser.add_argument('-p', '--package', required=True)
    args = parser.parse_args()
    check(Path(args.info), Path(args.package))
