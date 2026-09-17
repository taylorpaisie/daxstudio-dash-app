import dash_ag_grid as dag

from src.connections.adomd_provider import browser_value


def grid(identifier, height=360):
    options = {"getRowId": "params.data._row_id"} if identifier != "query-grid" else {}
    return dag.AgGrid(
        **options,
        id=identifier,
        rowData=[],
        columnDefs=[],
        className="ag-theme-quartz studio-grid",
        defaultColDef={"sortable": True, "filter": True, "resizable": True, "minWidth": 130},
        dashGridOptions={
            "theme": {"function": "studioTheme(themeQuartz)"},
            "pagination": True,
            "paginationPageSize": 50,
            "paginationPageSizeSelector": [25, 50, 100, 250],
            "enableCellTextSelection": True,
            "ensureDomOrder": True,
            "animateRows": False,
            "suppressFieldDotNotation": True,
            "localeText": {"noRowsToShow": "No rows to display"},
        },
        style={"height": height, "width": "100%"},
    )


def grid_payload(frame, semantic=False):
    keys = list(frame.columns) if semantic else [f"c{i}" for i in range(len(frame.columns))]
    rows = [
        dict(zip(keys, [browser_value(v) for v in row]))
        for row in frame.itertuples(index=False, name=None)
    ]
    columns = []
    for index, (key, name) in enumerate(zip(keys, frame.columns)):
        values = [row[key] for row in rows if row[key] is not None]
        kind = "text"
        if values and all(isinstance(v, bool) for v in values):
            kind = "boolean"
        elif values and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in values
        ):
            kind = "number"
        column = {"field": key, "headerName": str(name), "cellDataType": kind}
        if kind == "number":
            column["filter"] = "agNumberColumnFilter"
            column["valueFormatter"] = {"function": "formatNumber(params.value)"}
        columns.append(column)
    return rows, columns
