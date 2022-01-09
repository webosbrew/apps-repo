#!/usr/bin/env python
# -*- coding: utf-8 -*- #
import datetime
from os.path import join, dirname, abspath

import repogen
from pelican.plugins import webassets

AUTHOR = 'webOS Homebrew Project'
SITENAME = 'webOS Homebrew Project'
SITEURL = ''

THEME = './theme'
THEME_STATIC_PATHS = [join(dirname(abspath(__file__)), 'website/theme/static')]
THEME_TEMPLATES_OVERRIDES = ['./website/theme/templates']

PLUGINS = [webassets, repogen]

WEBASSETS_SOURCE_PATHS = ['static']

PATH = 'content'

STATIC_PATHS = ['api', 'extra/CNAME', 'styles']
ARTICLE_EXCLUDES = ['api']
PAGE_PATHS = ['pages', 'apps', '../packages']

EXTRA_PATH_METADATA = {
    'extra/CNAME': {'path': 'CNAME'},
    'styles': {'path': 'theme/css'}
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

DEFAULT_PAGINATION = 30

# Uncomment following line if you want document-relative URLs when developing
# RELATIVE_URLS = True

COPYRIGHT_YEAR = datetime.date.today().year
