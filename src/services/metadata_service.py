from src.connections.base import StudioError
from src.utilities.dax import object_identifier, table_identifier

QUERIES = {
    "tables": "SELECT [ID], [Name], [IsHidden] FROM $SYSTEM.TMSCHEMA_TABLES",
    "columns": (
        "SELECT [TableID], [ExplicitName], [InferredName], [ExplicitDataType], "
        "[InferredDataType], [IsHidden] FROM $SYSTEM.TMSCHEMA_COLUMNS"
    ),
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
    19: "Unknown",
    20: "Variant",
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
            if kind == "columns":
                name = row.get("ExplicitName") or row.get("InferredName")
                data_type = row.get("ExplicitDataType")
                if data_type in (None, 1):
                    data_type = row.get("InferredDataType") or data_type
            else:
                name, data_type = row["Name"], row["DataType"]
            if table and name:
                table["objects"].append(
                    {
                        "name": name,
                        "kind": "Measure" if kind == "measures" else "Column",
                        "type": DATA_TYPES.get(data_type, "Unknown"),
                        "hidden": bool(row["IsHidden"]),
                        "identifier": object_identifier(table["name"], name),
                    }
                )
    return sorted(tables.values(), key=lambda table: table["name"].lower())
