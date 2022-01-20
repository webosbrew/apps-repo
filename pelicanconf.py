#!/usr/bin/env python
# -*- coding: utf-8 -*- #
import datetime
from os.path import join, dirname, abspath

import repogen
from pelican.plugins import webassets
import pelican.themes.webosbrew

AUTHOR = 'webOS Homebrew Project'
SITENAME = 'webOS Homebrew Project'
SITEURL = ''

THEME = 'webosbrew'
THEME_STATIC_PATHS = [join(dirname(abspath(__file__)), 'theme/static'), pelican.themes.webosbrew.static_dir()]
THEME_TEMPLATES_OVERRIDES = ['./theme/templates']

PLUGINS = [webassets, repogen]

WEBASSETS_CONFIG = [
    ("PYSCSS_LOAD_PATHS", [pelican.themes.webosbrew.scss_dir()])
]

PATH = 'content'

STATIC_PATHS = ['extra/CNAME', 'extra/favicon.ico']
ARTICLE_EXCLUDES = []
PAGE_PATHS = ['pages', 'apps', '../packages']

EXTRA_PATH_METADATA = {
    'extra/CNAME': {'path': 'CNAME'},
    'extra/favicon.ico': {'path': 'favicon.ico'}
}

MARKDOWN = {
    'extension_configs': {
        'markdown.extensions.codehilite': {'css_class': 'highlight'},
        'markdown.extensions.extra': {},
        'markdown.extensions.meta': {},
        'markdown.extensions.toc': {
            'permalink': True,
        },
    },
    'output_format': 'html5',
}

TIMEZONE = 'Asia/Tokyo'

DEFAULT_LANG = 'en'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None
CACHE_CONTENT = False
LOAD_CONTENT_CACHE = False

MENUITEMS = (
    ('Applications', '/apps'),
    ('Submit', '/submit'),
)

LINKS = (
    ('Github Organization', 'https://github.com/webosbrew/'),
    ('Join us on Discord', 'https://discord.gg/xWqRVEm'),
    ('RootMy.TV', 'https://rootmy.tv/'),
    ('openlgtv', 'https://openlgtv.github.io/'),
)

DEFAULT_PAGINATION = 20

# Uncomment following line if you want document-relative URLs when developing
# RELATIVE_URLS = True

COPYRIGHT_YEAR = datetime.date.today().year
