# -*- coding: utf-8 -*-
"""Writes api/openapi.json, an OpenAPI 3.1 definition of the JSON API.

It is built from the path templates and pools in repogen/apidata.py and the categories in
conf/categories.yml, the same values the API files are written from, so it cannot describe
a file the build does not write."""
import json
from pathlib import Path
from typing import List

from repogen import apidata
from repogen.common import ensure_open
from repogen.siteurl import siteurl

# Relative to api/openapi.json, so they resolve to the schemas deployed with the same build,
# wherever the site is hosted. OpenAPI 3.1 resolves a Schema Object's relative $ref against
# the URL the definition was fetched from.
SCHEMAS = '../schemas/api/'

PAGE = {
    'name': 'page',
    'in': 'path',
    'required': True,
    'description': 'Page number, starting at 1. Page 1 always exists; `paging.maxPage` is the last.',
    'schema': {'type': 'integer', 'minimum': 1},
}
APP_ID = {
    'name': 'id',
    'in': 'path',
    'required': True,
    'description': 'Package id, as in `packages[].id`.',
    'schema': {'type': 'string'},
}


def _camel(name: str) -> str:
    """non-free-listApps -> nonFreeListApps"""
    first, *rest = name.split('-')
    return first + ''.join(word[0].upper() + word[1:] for word in rest)


def _json(schema: str, description: str) -> dict:
    return {'description': description, 'content': {'application/json': {'schema': {'$ref': SCHEMAS + schema}}}}


def _operations(categories: List[dict]) -> list[tuple[str, str, str, list, dict]]:
    """(path template, operationId, summary, parameters, 200 response) per file of a pool."""
    category = {
        'name': 'category',
        'in': 'path',
        'required': True,
        'description': 'Category id, as in `categories[].id` of categories.json.',
        'schema': {'type': 'string', 'enum': [cat['slug'] for cat in categories]},
    }
    return [
        (apidata.APPS, 'listApps', 'Every package, in one response', [],
         _json('PackagesPage.json', 'All packages, by title. Reported as page 1 of 1.')),
        (apidata.APPS_PAGE, 'listAppsPage', 'One page of packages', [PAGE],
         _json('PackagesPage.json', 'The packages on this page. Follow `paging.nextUrl` for the next.')),
        (apidata.RELEASE_LATEST, 'getLatestRelease', 'Latest release of one package', [APP_ID],
         _json('PackageInfo.json', 'The package with its latest manifest.')),
        (apidata.FULL_DESCRIPTION, 'getFullDescription', 'Full description of one package', [APP_ID],
         {'description': 'An HTML fragment, screenshots first, without a stylesheet.',
          'content': {'text/html': {'schema': {'type': 'string'}}}}),
        (apidata.CATEGORIES, 'listCategories', 'Every category, in display order', [],
         _json('CategoryList.json', 'All categories, including those without packages.')),
        (apidata.CATEGORY, 'listCategoryApps', 'Every package of one category, in one response', [category],
         _json('CategoryPage.json', 'The packages of the category, by title. Reported as page 1 of 1.')),
        (apidata.CATEGORY_PAGE, 'listCategoryAppsPage', 'One page of packages of one category', [category, PAGE],
         _json('CategoryPage.json', 'The packages on this page. Follow `paging.nextUrl` for the next.')),
    ]


def definition(categories: List[dict]) -> dict:
    site = siteurl()
    paths = {}
    for pool, pool_dir in apidata.POOL_DIRS.items():
        prefix = f'/{pool_dir}' if pool_dir else ''
        for template, operation_id, summary, parameters, ok in _operations(categories):
            operation = {
                'tags': [pool],
                # listApps in the main pool, nonFreeListApps in non-free.
                'operationId': operation_id if pool == 'main' else _camel(f'{pool}-{operation_id}'),
                'summary': summary,
                'responses': {'200': ok},
            }
            if parameters:
                operation['parameters'] = parameters
                operation['responses']['404'] = {'description': 'No such package, category or page.'}
            paths[f'{prefix}/{template}'] = {'get': operation}
    return {
        'openapi': '3.1.0',
        'info': {
            'title': 'webOS Homebrew Apps Repository',
            'version': '1.0.0',
            'description': 'Static JSON files listing the homebrew apps for LG webOS TVs. Each pool has the same '
                           'files: the main pool at the root, packages that are not open source under /non-free. '
                           'URLs inside responses (paging, fullDescriptionUrl, category URLs) are relative to the '
                           'file they appear in.',
        },
        # The pools are different data, not alternative hosts for the same data, so they are
        # paths under one server rather than two servers.
        'servers': [{'url': f'{site}/api' if site else '/api'}],
        'tags': [
            {'name': 'main', 'description': 'Open source packages.'},
            {'name': 'non-free', 'description': 'Packages that are not open source.'},
        ],
        'paths': paths,
    }


def generate(api_dir: Path, categories: List[dict]):
    with ensure_open(api_dir.joinpath('openapi.json'), 'w', encoding='utf-8') as f:
        json.dump(definition(categories), f, indent=2)
