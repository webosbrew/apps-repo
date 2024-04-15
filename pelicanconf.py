#!/usr/bin/env python
# -*- coding: utf-8 -*- #
import datetime
import os
from pathlib import Path

import pelican.themes.webosbrew
from pelican.plugins import webassets
from webassets.cache import MemoryCache

import repogen
from repogen.siteurl import siteurl

AUTHOR = 'webOS Homebrew Project'
SITENAME = 'webOS Homebrew Project'
SITEURL = siteurl() if os.environ.get('CI') else ''

THEME = 'webosbrew'
theme_dir = Path(__file__, '..', 'theme').resolve()
THEME_STATIC_PATHS = [theme_dir.joinpath('static'), pelican.themes.webosbrew.static_dir()]
WEBASSETS_SOURCE_PATHS = [theme_dir.joinpath('styles'), pelican.themes.webosbrew.scss_dir()]
THEME_TEMPLATES_OVERRIDES = ['./theme/templates']

PLUGINS = [webassets, repogen]

WEBASSETS_CONFIG = [
    ("CACHE", MemoryCache(1024)),
    ("PYSCSS_LOAD_PATHS", [pelican.themes.webosbrew.scss_dir()]),
]

PATH = 'content'

STATIC_PATHS = ['extra/CNAME', 'extra/favicon.ico', 'schemas', 'apps/icons']
ARTICLE_EXCLUDES = ['api']
PAGE_PATHS = ['pages', 'apps', '../packages']

EXTRA_PATH_METADATA = {
    'apps/icons': {'path': 'apps/icons/'},
    'extra/CNAME': {'path': 'CNAME'},
    'extra/favicon.ico': {'path': 'favicon.ico'},
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

INDEX_APP_CATEGORIES = [
    ('multimedia', 'Multimedia'),
    ('game', 'Games'),
    ('amblight', 'Ambient Light'),
    ('utility', 'Utilities'),
]

# Following packages will have their IPKs downloaded and hosted on the site
HOST_PACKAGES: set[str] = {
    'org.webosbrew.hbchannel',
    'org.webosbrew.safeupdate'
}

DEFAULT_PAGINATION = 20

# Uncomment following line if you want document-relative URLs when developing
# RELATIVE_URLS = True

COPYRIGHT_YEAR = datetime.date.today().year
