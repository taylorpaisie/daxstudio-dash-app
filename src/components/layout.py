import dash_bootstrap_components as dbc
from dash import dcc, html

from src.components.examples import EXAMPLES
from src.components.grids import grid


def button(text, identifier, primary=False, **kwargs):
    return dbc.Button(
        text,
        id=identifier,
        color="primary" if primary else "secondary",
        outline=not primary,
        size="sm",
        **kwargs,
    )


def field(label, control):
    return html.Div([html.Label(label), control], className="field")


def layout():
    return html.Div(
        id="app-shell",
        **{"data-theme": "dark"},
        children=[
            dcc.Location(id="page", refresh=False),
            dcc.Store(id="hydrated"),
            dcc.Store(id="events"),
            dcc.Store(id="model-version", data=0),
            dcc.Store(id="insert-object"),
            dcc.Download(id="download"),
            html.Header(
                [
                    html.Div(
                        [
                            html.Span("D", className="brand-icon"),
                            html.Div(
                                [
                                    html.Strong("DAX Browser Studio"),
                                    html.Small("LOCAL MODEL WORKSPACE"),
                                ]
                            ),
                        ],
                        className="brand",
                    ),
                    html.Div(
                        [
                            html.Span(id="busy-state", role="status"),
                            html.Span(id="elapsed"),
                            html.Span(
                                "Disconnected", id="connection-badge", className="status-badge"
                            ),
                            button("Connection", "toggle-connection"),
                            dbc.Switch(id="theme", label="Light theme", value=False),
                        ],
                        className="toolbar",
                    ),
                ],
                className="topbar",
            ),
            dbc.Collapse(
                id="connection-panel",
                is_open=True,
                children=html.Section(
                    [
                        html.Div(
                            [
                                html.H2("Connect to Power BI Desktop"),
                                html.P(
                                    "Open a PBIX locally, discover its engine, then select a "
                                    "catalog."
                                ),
                            ]
                        ),
                        html.Div(
                            [
                                field(
                                    "Discovered instances",
                                    dcc.Dropdown(
                                        id="instances",
                                        options=[],
                                        placeholder="Refresh to find open models",
                                        className="dropdown",
                                    ),
                                ),
                                button("Refresh", "discover"),
                                field(
                                    "Local server",
                                    dbc.Input(
                                        id="server", placeholder="localhost:12345", debounce=True
                                    ),
                                ),
                                button("Find catalogs", "catalogs"),
                                field(
                                    "Initial catalog",
                                    dcc.Dropdown(
                                        id="catalog",
                                        options=[],
                                        placeholder="Find catalogs first",
                                        className="dropdown",
                                    ),
                                ),
                                button("Connect", "connect", True),
                                button("Disconnect", "disconnect"),
                            ],
                            className="connection-fields",
                        ),
                        html.Div(
                            "Manual server entry is always available.",
                            id="connection-message",
                            className="message",
                            role="status",
                        ),
                    ],
                    className="connection-content",
                ),
            ),
            html.Div(
                [
                    html.Aside(
                        [
                            html.Div(
                                [html.H2("Model explorer"), button("Reload", "reload-model")],
                                className="section-heading",
                            ),
                            dbc.Input(
                                id="model-search",
                                placeholder="Search tables, columns, measures…",
                                debounce=True,
                                size="sm",
                            ),
                            html.Div(
                                [
                                    button("Expand all", "expand-model"),
                                    button("Collapse all", "collapse-model"),
                                ],
                                className="toolbar tree-tools",
                            ),
                            html.Small("Click an object to insert its DAX name."),
                            html.Div(
                                "Connect to load model metadata.",
                                id="model-message",
                                className="message",
                            ),
                            html.Div(id="model-tree", className="model-tree"),
                        ],
                        className="sidebar",
                    ),
                    html.Main(
                        [
                            dbc.Tabs(
                                id="tabs",
                                active_tab="query",
                                children=[
                                    dbc.Tab(label="Query", tab_id="query"),
                                    dbc.Tab(label="Dependencies", tab_id="dependencies"),
                                    dbc.Tab(label="Query History", tab_id="history"),
                                    dbc.Tab(label="About", tab_id="about"),
                                ],
                            ),
                            html.Section(
                                id="query-pane",
                                className="pane",
                                children=[
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.H1("Query workspace"),
                                                    html.P(
                                                        "Write DAX. Inspect results. Explore "
                                                        "your model."
                                                    ),
                                                ]
                                            ),
                                            html.Span("DAX · READ ONLY", className="eyebrow"),
                                        ],
                                        className="section-heading",
                                    ),
                                    html.Div(
                                        [
                                            button("▶  Run query", "run-query", True),
                                            button("Clear", "clear-query"),
                                            dcc.Dropdown(
                                                id="examples",
                                                options=list(EXAMPLES),
                                                value=None,
                                                placeholder="Example queries",
                                                className="example-dropdown",
                                            ),
                                            field(
                                                "Max rows",
                                                dbc.Input(
                                                    id="row-limit",
                                                    type="number",
                                                    value=1000,
                                                    min=1,
                                                    max=10000,
                                                    step=1,
                                                ),
                                            ),
                                            field(
                                                "Timeout (s)",
                                                dbc.Input(
                                                    id="timeout",
                                                    type="number",
                                                    value=30,
                                                    min=1,
                                                    max=120,
                                                    step=1,
                                                ),
                                            ),
                                        ],
                                        className="toolbar editor-toolbar",
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Span("QUERY 01"),
                                                    html.Span("Ctrl + Enter to run"),
                                                ],
                                                className="editor-caption",
                                            ),
                                            dcc.Textarea(
                                                id="editor",
                                                value=EXAMPLES["Dependency preview"],
                                                spellCheck=False,
                                                className="code-editor",
                                                title="DAX query editor",
                                                placeholder="EVALUATE …",
                                            ),
                                        ],
                                        className="editor-box",
                                    ),
                                    html.Div(
                                        "Ready. Connect to a model to execute DAX.",
                                        id="query-status",
                                        role="status",
                                        className="message query-status",
                                    ),
                                    html.Div(
                                        [
                                            html.H2("Results"),
                                            html.Div(
                                                [
                                                    button("Export CSV", "query-csv"),
                                                    button("Export Excel", "query-xlsx"),
                                                ],
                                                className="toolbar",
                                            ),
                                        ],
                                        className="section-heading",
                                    ),
                                    grid("query-grid"),
                                    html.Small(
                                        "Select cell text to copy. Exports include the "
                                        "bounded result set;"
                                        "grid sorting and filters are display-only."
                                    ),
                                ],
                            ),
                            html.Section(
                                id="dependencies-pane",
                                className="pane",
                                style={"display": "none"},
                                children=[
                                    html.H1("Dependency explorer"),
                                    html.P(
                                        "Trace model objects to the tables, columns and "
                                        "measures they reference."
                                    ),
                                    html.Div(
                                        [
                                            field(
                                                "Referenced table contains",
                                                dbc.Input(id="dep-table", placeholder="e.g. GFEBS"),
                                            ),
                                            field(
                                                "Measure / object name contains",
                                                dbc.Input(
                                                    id="dep-measure", placeholder="e.g. Total"
                                                ),
                                            ),
                                            field(
                                                "Object type",
                                                dbc.Input(
                                                    id="dep-type", placeholder="e.g. MEASURE"
                                                ),
                                            ),
                                            field(
                                                "Referenced type",
                                                dbc.Input(
                                                    id="dep-ref-type", placeholder="e.g. COLUMN"
                                                ),
                                            ),
                                        ],
                                        className="dependency-filters",
                                    ),
                                    html.Div(
                                        [
                                            button("Find dependencies", "load-dependencies", True),
                                            button("Export CSV", "dependency-csv"),
                                            button("Export Excel", "dependency-xlsx"),
                                        ],
                                        className="toolbar",
                                    ),
                                    html.Div(
                                        "Search uses INFO.CALCDEPENDENCY(). Click a row to "
                                        "create a focused query.",
                                        id="dependency-status",
                                        role="status",
                                        className="message",
                                    ),
                                    grid("dependency-grid", 500),
                                    html.Small(
                                        "Up to 10,000 rows / 8 MB. Filters apply to the model "
                                        "before limiting."
                                        "Use MEASURE as object type to restrict the search to "
                                        "measures."
                                    ),
                                ],
                            ),
                            html.Section(
                                id="history-pane",
                                className="pane",
                                style={"display": "none"},
                                children=[
                                    html.Div(
                                        [
                                            html.H1("Query history"),
                                            button("Clear history", "clear-history"),
                                        ],
                                        className="section-heading",
                                    ),
                                    html.P(
                                        "Last 50 executions in this browser session. Click a "
                                        "row to restore its query."
                                    ),
                                    grid("history-grid", 520),
                                ],
                            ),
                            html.Section(
                                id="about-pane",
                                className="pane about",
                                style={"display": "none"},
                                children=[
                                    html.Span("A FOCUSED LOCAL WORKSPACE", className="eyebrow"),
                                    html.H1("DAX Browser Studio"),
                                    html.P(
                                        "A read-only query and model exploration tool for "
                                        "Power BI Desktop."
                                    ),
                                    html.H2("Your data stays local"),
                                    html.P(
                                        "Served on 127.0.0.1. No telemetry, external fonts, "
                                        "or cloud services."
                                        "Queries, metadata and results live in "
                                        "process/browser memory. Exports"
                                        "are written only when you request a download."
                                    ),
                                    html.H2("MVP boundaries"),
                                    html.P(
                                        "The editor uses a dependable plain-text fallback. "
                                        "Only the first result"
                                        "set is shown. Cancellation is not offered; use the "
                                        "command timeout."
                                        "No model writes, profiling, autocomplete or "
                                        "published-model login yet."
                                    ),
                                    html.P(
                                        "INFO.CALCDEPENDENCY requires supported engine "
                                        "versions and model write"
                                        "permission, even though this app does not modify models. "
                                        "Live-connected reports may not expose this metadata."
                                    ),
                                    html.P(
                                        "Connections open per operation. The status badge "
                                        "records the last"
                                        "successful connection, not a continuous health "
                                        "check. Sessions expire"
                                        "after 30 minutes of inactivity and are cleared when "
                                        "the server stops."
                                    ),
                                ],
                            ),
                        ],
                        className="workspace",
                    ),
                ],
                className="workbench",
            ),
            html.Footer(
                [html.Span("LOCALHOST ONLY"), html.Span("Bounded results · Read-only DAX · MVP")]
            ),
        ],
    )
