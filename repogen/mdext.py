"""Python-Markdown extension: let a list start right after a paragraph line.

GitHub (CommonMark) lets a list interrupt a paragraph, Python-Markdown wants a blank
line first. Package descriptions are written GitHub-style, so without this a
``**Key Features:**`` line followed by ``* item`` lines renders as one paragraph with
literal asterisks. The preprocessor inserts the missing blank line and touches nothing else.
"""
import re

from markdown import Extension
from markdown.preprocessors import Preprocessor

_ITEM = re.compile(r'^ {0,3}(?:[*+-]|\d{1,9}[.])[ \t]+\S')
_HR = re.compile(r'^ {0,3}([*_-])(?:[ \t]*\1){2,}[ \t]*$')
_FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
_HEADING = re.compile(r'^ {0,3}#{1,6}(?:[ \t]|$)')
_SETEXT = re.compile(r'^ {0,3}(?:=+|-+)[ \t]*$')
_TABLE_SEP = re.compile(r'^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$')


def _indent(line: str) -> int:
    return len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip(' '))


class ListAfterParagraphPreprocessor(Preprocessor):
    def run(self, lines):
        out = []
        fence = None  # (char, length) of the open fenced code block
        in_html = False
        in_list = False  # inside a list item, including its lazy continuation lines
        prev_text = False  # previous line is plain paragraph text

        for line in lines:
            if fence:
                out.append(line)
                m = _FENCE.match(line)
                if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] \
                        and not line.strip().strip(fence[0]):
                    fence = None
                continue
            if not line.strip():
                out.append(line)
                in_html = False
                in_list = False
                prev_text = False
                continue

            m = _FENCE.match(line)
            if m:
                fence = (m.group(1)[0], len(m.group(1)))
                prev_text = False
                in_list = False
                out.append(line)
                continue

            is_item = bool(_ITEM.match(line)) and not _HR.match(line)
            if is_item and prev_text and not in_list and not in_html:
                out.append('')
            if is_item:
                in_list = True
                prev_text = False
            else:
                starts_block = not out or not out[-1].strip()
                if starts_block and line.lstrip().startswith('<'):
                    in_html = True
                special = (
                    in_html or _HEADING.match(line) or _HR.match(line) or _SETEXT.match(line)
                    or line.lstrip().startswith('>') or '|' in line or _indent(line) >= 4
                    or _TABLE_SEP.match(line)
                )
                prev_text = not special and not in_list
            out.append(line)
        return out


class ListAfterParagraphExtension(Extension):
    def extendMarkdown(self, md):
        # Before normalize_whitespace (30) and html_block (20): the lines are still raw.
        md.preprocessors.register(ListAfterParagraphPreprocessor(md), 'list_after_paragraph', 35)


def makeExtension(**kwargs):
    return ListAfterParagraphExtension(**kwargs)
