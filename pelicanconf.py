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

STATIC_PATHS = ['extra/CNAME', 'extra/favicon.ico', 'extra/llms.txt', 'schemas', 'apps/icons']
# App pages come from ../packages through the repogen reader. content/apps only
# holds generated icons, so it is not a page path.
PAGE_PATHS = ['pages', '../packages']

# The repo has no articles, so Pelican's article-driven templates would only emit
# empty tags/categories/authors/archives pages for crawlers to index. The plugin
# writes index.html itself.
DIRECT_TEMPLATES = []

EXTRA_PATH_METADATA = {
    'apps/icons': {'path': 'apps/icons/'},
    'extra/CNAME': {'path': 'CNAME'},
    'extra/favicon.ico': {'path': 'favicon.ico'},
    'extra/llms.txt': {'path': 'llms.txt'},
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

# Home/logo link target and top-nav items, consumed by the theme navbar.
HOME_URL = '/'

# Directory pages keep the trailing slash. GitHub Pages 301-redirects the
# slashless form, so linking it directly saves a round trip.
MENUITEMS = (
    ('Apps', '/apps/'),
    ('Develop', 'https://www.webosbrew.org/develop'),
)

LINKS = (
    ('Github Organization', 'https://github.com/webosbrew/'),
    ('Join us on Discord', 'https://discord.gg/xWqRVEm'),
    ('RootMy.TV', 'https://rootmy.tv/'),
    ('openlgtv', 'https://openlgtv.github.io/'),
)

# Footer columns, consumed by the theme footer.
FOOTER_SECTIONS = [
    {'title': 'Guides', 'links': [
        {'text': 'Rooting', 'href': 'https://www.webosbrew.org/rooting'},
        {'text': 'Dev Mode', 'href': 'https://www.webosbrew.org/devmode'},
    ]},
    {'title': 'Resources', 'links': [
        {'text': 'Develop', 'href': 'https://www.webosbrew.org/develop'},
        {'text': 'Submit an App', 'href': '/submit'},
    ]},
    {'title': 'Links', 'links': [
        {'text': 'webosbrew', 'href': 'https://github.com/webosbrew/', 'icon': 'bi-github'},
        {'text': 'OpenLGTV', 'href': 'https://github.com/OpenLGTV', 'icon': 'bi-github'},
        {'text': 'Discord', 'href': 'https://discord.gg/xWqRVEm', 'icon': 'bi-discord'},
    ]},
]

INDEX_APP_CATEGORIES = [
    ('multimedia', 'Multimedia'),
    ('game', 'Games'),
    ('amblight', 'Ambient Light'),
    ('screensaver', 'Screensavers'),
    ('utility', 'Utilities'),
]

# App IDs featured on the homepage, in display order. The blurb for each is
# taken from the package's manifest (appDescription).
FEATURED_APPS = [
    'org.webosbrew.hbchannel',
    'org.xbmc.kodi',
    'com.limelight.webos',
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
