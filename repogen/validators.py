import json
import urllib.parse
from pathlib import Path
from typing import Any, Type

import jsonschema
from jsonschema.protocols import Validator
from jsonschema.validators import RefResolver


def schemas_dir() -> Path:
    return Path('content/schemas').resolve()


assert Path(__file__, '../content/schemas').samefile(schemas_dir())


def for_schema(rel_path: str) -> Validator:
    def schema_handler(uri: str) -> Any:
        with schemas_dir().joinpath(urllib.parse.urlparse(uri).path.removeprefix('/schemas/')).open() as rf:
            return json.load(rf)

    schema_path = schemas_dir().joinpath(rel_path)
    with schema_path.open() as f:
        schema = json.load(f)
        resolver = RefResolver(base_uri=schema_path.as_uri(), referrer=schema, handlers={'https': schema_handler})
        validator_cls: Type[jsonschema.Validator] = jsonschema.validators.validator_for(schema)
        validator = validator_cls(resolver=resolver, schema=schema)
        jsonschema.validate(schema, validator_cls.META_SCHEMA)
        return validator
