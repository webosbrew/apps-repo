import json
import urllib.parse
from pathlib import Path
from typing import Any, Type

import jsonschema
from jsonschema.protocols import Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource


def schemas_dir() -> Path:
    return Path('content/schemas').resolve()


assert Path(__file__, '../../content/schemas').resolve().samefile(schemas_dir())


class SchemaValidationError(Exception):
    """Raised with every schema violation for a document, not just the first."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__('\n'.join(errors))


def _explain(error: jsonschema.ValidationError) -> list[jsonschema.ValidationError]:
    """A oneOf/anyOf error only says that no branch matched. When the branches differ by
    type, say why the branch of the value's own type rejected it instead."""
    if error.context and any(e.validator == 'type' and not e.relative_path for e in error.context):
        relevant = [e for e in error.context if not (e.validator == 'type' and not e.relative_path)]
        if relevant:
            return relevant
    return [error]


def _format_error(error: jsonschema.ValidationError) -> str:
    location = '/'.join(str(p) for p in error.absolute_path) or '(root)'
    return f'{location}: {error.message}'


def validate(validator: Validator, instance: Any) -> None:
    """Validate `instance`, collecting every error. Raises SchemaValidationError
    listing all violations so callers can report them at once."""
    errors = sorted((e for error in validator.iter_errors(instance) for e in _explain(error)),
                    key=lambda e: list(e.absolute_path))
    if errors:
        raise SchemaValidationError([_format_error(e) for e in errors])


def for_schema(rel_path: str) -> Validator:
    """A validator for content/schemas/<rel_path>.

    Every schema has an $id under https://repo.webosbrew.org/schemas/, and relative $refs
    resolve against it, as JSON Schema specifies. Those URLs are served from content/schemas
    here, so validation never goes to the network and sees the schemas of this checkout."""

    def retrieve(uri: str) -> Resource:
        parsed = urllib.parse.urlparse(uri)
        if parsed.scheme != 'https' or not parsed.path.startswith('/schemas/'):
            raise NoSuchResource(ref=uri)
        with schemas_dir().joinpath(parsed.path.removeprefix('/schemas/')).open() as rf:
            return Resource.from_contents(json.load(rf))

    with schemas_dir().joinpath(rel_path).open() as f:
        schema = json.load(f)
    validator_cls: Type[jsonschema.Validator] = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    return validator_cls(schema, registry=Registry(retrieve=retrieve))
