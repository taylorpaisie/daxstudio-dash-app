import re

from src.connections.base import StudioError


def table_identifier(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def object_identifier(table: str, name: str) -> str:
    return table_identifier(table) + "[" + name.replace("]", "]]") + "]"


def string_literal(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def validate_query(query: str) -> str:
    """Allow DAX table queries only, never XMLA/MDX/DMV user commands.

    Strip quoted strings/identifiers and comments before scanning. DEFINE is
    query-scoped; model mutations (including preview DEFINE FUNCTION) are excluded.
    This is an application guard, not a replacement for server permissions.
    """
    if not query or len(query) > 100_000:
        raise StudioError("Enter a DAX query of at most 100,000 characters.")
    cleaned = re.sub(
        r'"(?:""|[^"])*"|\'(?:\'\'|[^\'])*\'|\[(?:\]\]|[^\]])*\]|'
        r"/\*[\s\S]*?\*/|//[^\n]*|--[^\n]*",
        " ",
        query,
    )
    if not re.match(r"^\s*(EVALUATE|DEFINE)\b", cleaned, re.I):
        raise StudioError("Only read-only DAX EVALUATE queries (optionally DEFINE) are accepted.")
    if not re.search(r"\bEVALUATE\b", cleaned, re.I) or re.search(
        r"\b(CREATE|ALTER|DELETE|DROP|INSERT|UPDATE|PROCESS|REFRESH|FUNCTION)\b|[<>]?[?]xml",
        cleaned,
        re.I,
    ):
        raise StudioError("Model-writing and procedural commands are not supported.")
    return query
