EXAMPLES = {
    "Dependency preview": "EVALUATE\nTOPN(\n    100,\n    INFO.CALCDEPENDENCY()\n)",
    "GFEBS dependencies": """EVALUATE
VAR Dependencies =
    SELECTCOLUMNS(
        INFO.CALCDEPENDENCY(),
        "Object Type", [OBJECT_TYPE],
        "Measure Table", [TABLE],
        "Measure", [OBJECT],
        "Referenced Type", [REFERENCED_OBJECT_TYPE],
        "Referenced Table", [REFERENCED_TABLE],
        "Referenced Object", [REFERENCED_OBJECT]
    )
RETURN
    FILTER(
        Dependencies,
        CONTAINSSTRING(
            UPPER(COALESCE([Referenced Table], "")),
            "GFEBS"
        )
    )
ORDER BY
    [Measure],
    [Referenced Object]""",
    "Connection check": 'EVALUATE ROW("Connection", "Ready", "Value", 1)',
    "Model tables": "EVALUATE INFO.TABLES()",
    "Model measures": "EVALUATE INFO.MEASURES()",
}
