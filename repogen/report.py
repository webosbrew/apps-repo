"""Helpers for text that goes into the PR check report.

The report becomes a comment on this repository, and most of what it shows comes
from the package under review: the title and description in appinfo.json, the URLs
in the manifest, the file and symbol names the compatibility check reads out of the
IPK. All of it belongs to the submitter, so all of it passes through here first.

The rule is the same in every form below. Text may say anything. It may not add
content of its own: no raw HTML, no image, no link, no extra table column, and no
character that makes it read as something it is not.
"""
import html
import re

# Characters that let text read as something it is not: C0 and C1 controls, bidi
# overrides and isolates, and zero-width marks. A line feed survives, nothing else.
_INVISIBLE = re.compile('[\x00-\x09\x0b-\x1f\x7f-\x9f'
                        '\\u200b-\\u200f\\u202a-\\u202e\\u2060-\\u2064\\u2066-\\u2069\\ufeff]')

# How much of a value a message repeats back. Enough to recognise a URL, not enough
# to fill a comment.
CODE_LIMIT = 200


def plain(value, limit: int | None = None) -> str:
    """Strip a value down to text, and cap it."""
    text = _INVISIBLE.sub('', str(value)).strip()
    if limit is not None and len(text) > limit:
        text = text[:limit].rstrip() + ' … (truncated)'
    return text


def as_html(value, limit: int | None = None) -> str:
    """Render a value inside a raw HTML block, keeping its line breaks.

    Every line feed becomes a `<br>`, which also keeps the block free of blank
    lines. That is what stops the renderer from reading the value as markdown, so
    keep it that way.
    """
    return html.escape(plain(value, limit), quote=False).replace('\n', '<br>')


def as_code(value, limit: int | None = CODE_LIMIT) -> str:
    """Repeat a value back as inline code.

    A backtick or a line break would end the code span and let the value carry on in
    markup of its own, so neither survives.
    """
    text = plain(value, limit).replace('`', "'").replace('\n', ' ')
    return f'`{text}`'


def as_markdown(value, limit: int | None = None) -> str:
    """Render a value as markdown text, in one line.

    Escapes what can put content in the comment: raw HTML, a link or an image, and
    a table column break. Emphasis and code spans are left alone. They can only
    change how the text looks, and the compatibility report needs them.
    """
    text = plain(value, limit).replace('\n', ' ').replace('\\', '\\\\')
    text = html.escape(text, quote=False)
    for char in '[]|':
        text = text.replace(char, f'\\{char}')
    return text
