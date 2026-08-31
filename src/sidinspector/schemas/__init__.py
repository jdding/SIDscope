"""Published JSON schemas and their two-stage validation authority."""

from .catalog import (
    PublicSchemaDescriptor,
    PublicSchemaValidationError,
    get_public_schema_descriptor,
    load_public_schema_catalog,
    validate_public_document,
)
from .result_contracts import (
    CLI_RESULT_SCHEMA_IDS,
    CLIResultValidationError,
    validate_cli_result,
)

__all__ = [
    "CLI_RESULT_SCHEMA_IDS",
    "CLIResultValidationError",
    "PublicSchemaDescriptor",
    "PublicSchemaValidationError",
    "get_public_schema_descriptor",
    "load_public_schema_catalog",
    "validate_cli_result",
    "validate_public_document",
]
