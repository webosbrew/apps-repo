"""Editorial settings kept as data in conf/: categories, homepage picks, app groups.

Each file is validated against its schema in content/schemas/conf/ when it is loaded,
so a mistake there stops the build instead of quietly changing the site."""
import json
from pathlib import Path
from typing import Any

import yaml

from repogen import validators

conf_dir = Path(__file__, '..', '..', 'conf').resolve()


def load(name: str, schema: str) -> Any:
    """Load conf/<name>.yml and validate it against content/schemas/conf/<schema>."""
    path = conf_dir.joinpath(f'{name}.yml')
    with path.open(encoding='utf-8') as f:
        data = yaml.safe_load(f)
    try:
        validators.validate(validators.for_schema(f'conf/{schema}'), data)
    except validators.SchemaValidationError as e:
        raise ValueError(f'{path}:\n' + '\n'.join(e.errors)) from e
    return data


def categories() -> list[dict]:
    """conf/categories.yml, checked to cover every category in Category.json exactly once."""
    entries = load('categories', 'Categories.json')
    with validators.schemas_dir().joinpath('packages/Category.json').open() as f:
        defined = [c['const'] for c in json.load(f)['anyOf']]
    listed = [c['slug'] for c in entries]
    duplicated = sorted({slug for slug in listed if listed.count(slug) > 1})
    missing = [slug for slug in defined if slug not in listed]
    if duplicated or missing:
        raise ValueError(f'conf/categories.yml must list every category once; '
                         f'duplicated: {duplicated or "none"}, missing: {missing or "none"}')
    return entries


def home() -> dict:
    return load('home', 'Home.json')
