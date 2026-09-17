from src.connections.base import StudioError
from src.utilities.dax import object_identifier, table_identifier

QUERIES = {
    "tables": "SELECT [ID], [Name], [IsHidden] FROM $SYSTEM.TMSCHEMA_TABLES",
    "columns": "SELECT [TableID], [Name], [DataType], [IsHidden] FROM $SYSTEM.TMSCHEMA_COLUMNS",
    "measures": "SELECT [TableID], [Name], [DataType], [IsHidden] FROM $SYSTEM.TMSCHEMA_MEASURES",
}
DATA_TYPES = {
    1: "Automatic",
    2: "Text",
    6: "Integer",
    8: "Decimal",
    9: "Date/time",
    10: "Fixed decimal",
    11: "Boolean",
    17: "Binary",
    19: "Variant",
}


def load_metadata(provider, spec):
    frames = {}
    for kind, query in QUERIES.items():
        result = provider.execute(spec, query, 10_000, 30)
        if result.truncated:
            raise StudioError(
                "Model metadata exceeds the MVP limit. Use focused INFO queries instead."
            )
        frames[kind] = result.frame.to_dict("records")
    tables = {}
    for row in frames["tables"]:
        tables[row["ID"]] = {
            "name": row["Name"],
            "hidden": bool(row["IsHidden"]),
            "identifier": table_identifier(row["Name"]),
            "objects": [],
        }
    for kind in ("columns", "measures"):
        for row in frames[kind]:
            table = tables.get(row["TableID"])
            if table:
                table["objects"].append(
                    {
                        "name": row["Name"],
                        "kind": "Measure" if kind == "measures" else "Column",
                        "type": DATA_TYPES.get(row["DataType"], str(row["DataType"])),
                        "hidden": bool(row["IsHidden"]),
                        "identifier": object_identifier(table["name"], row["Name"]),
                    }
                )
    return sorted(tables.values(), key=lambda table: table["name"].lower())
