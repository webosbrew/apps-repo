#!/usr/bin/env python
# -*- coding: utf-8 -*- #

AUTHOR = 'webOS Homebrew Project'
SITENAME = 'webOS Homebrew Project'
SITEURL = ''

PATH = 'content'

STATIC_PATHS = ['api', 'extra/CNAME', 'styles']
PAGE_PATHS = ['pages', 'apps']

EXTRA_PATH_METADATA = {
    'extra/CNAME': {'path': 'CNAME'},
    'styles': {'path': 'theme/css'}
}

TIMEZONE = 'Asia/Tokyo'

DEFAULT_LANG = 'en'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

MENUITEMS = (
    ('Home', '/'),
    ('Applications', '/apps'),
    ('Submit Application', '/submit'),
)

# Blogroll
LINKS = (
    ('webOS Homebrew', 'https://github.com/webosbrew/'),
    ('openlgtv', 'https://openlgtv.github.io/'),
)

# Social widget
SOCIAL = (
    ('openlgtv Discord', 'https://discord.gg/xWqRVEm'),
)

DEFAULT_PAGINATION = 30

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True
