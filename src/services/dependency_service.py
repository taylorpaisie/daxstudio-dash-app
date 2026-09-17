import pandas as pd

from src.utilities.dax import string_literal

FIELDS = [
    "OBJECT_TYPE",
    "TABLE",
    "OBJECT",
    "REFERENCED_OBJECT_TYPE",
    "REFERENCED_TABLE",
    "REFERENCED_OBJECT",
]


def dependency_query(table="", measure="", object_type="", referenced_type="", limit=10_000):
    conditions = []
    for field, value, partial in [
        ("REFERENCED_TABLE", table, True),
        ("OBJECT", measure, True),
        ("OBJECT_TYPE", object_type, False),
        ("REFERENCED_OBJECT_TYPE", referenced_type, False),
    ]:
        if value:
            value = str(value)[:500].upper()
            if partial:
                value = value.replace("~", "~~").replace("*", "~*").replace("?", "~?")
            literal = string_literal(value)
            expression = f'UPPER(COALESCE([{field}], ""))'
            conditions.append(
                f"CONTAINSSTRING({expression}, {literal})"
                if partial
                else f"{expression} = {literal}"
            )
    source = "INFO.CALCDEPENDENCY()"
    if conditions:
        source = f"FILTER({source}, " + " && ".join(conditions) + ")"
    # Apply filters before limiting so table search covers the whole model.
    return f"EVALUATE\nTOPN({int(limit) + 1}, {source})"


def normalize_dependencies(frame):
    renamed = {name: str(name).split("[")[-1].rstrip("]").upper() for name in frame.columns}
    result = frame.rename(columns=renamed)
    return result.reindex(columns=FIELDS).where(pd.notna(result.reindex(columns=FIELDS)), None)


def filter_dependencies(frame, table="", measure="", object_type="", referenced_type=""):
    frame = normalize_dependencies(frame)
    for field, value, partial in [
        ("REFERENCED_TABLE", table, True),
        ("OBJECT", measure, True),
        ("OBJECT_TYPE", object_type, False),
        ("REFERENCED_OBJECT_TYPE", referenced_type, False),
    ]:
        if value:
            values = frame[field].fillna("").astype(str).str.upper()
            mask = (
                values.str.contains(value.upper(), regex=False)
                if partial
                else values.eq(value.upper())
            )
            frame = frame[mask]
    return frame


def query_for_dependency(row):
    return (
        "EVALUATE\nFILTER(\n    INFO.CALCDEPENDENCY(),\n"
        f"    [TABLE] = {string_literal(row.get('TABLE') or '')} &&\n"
        f"    [OBJECT] = {string_literal(row.get('OBJECT') or '')}\n)"
    )
