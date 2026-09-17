import io
import uuid
from time import monotonic

from dash import ALL, Input, Output, State, ctx, dcc, html, no_update, set_props
from dash.exceptions import PreventUpdate
from flask import session as browser_session

from src.components.examples import EXAMPLES
from src.components.grids import grid_payload
from src.connections.adomd_provider import browser_value, validate_server
from src.connections.base import ConnectionSpec, StudioError
from src.connections.desktop_discovery import discover_instances
from src.services.dependency_service import (
    dependency_query,
    normalize_dependencies,
    query_for_dependency,
)
from src.services.metadata_service import load_metadata
from src.services.query_service import run_with_history

ACTIONS = [
    "discover",
    "catalogs",
    "connect",
    "disconnect",
    "reload-model",
    "run-query",
    "load-dependencies",
    "clear-history",
    "query-csv",
    "query-xlsx",
    "dependency-csv",
    "dependency-xlsx",
]


def safe_export(frame):
    """Neutralize formula injection in spreadsheet applications, preserving numeric cells."""

    def clean(value):
        value = browser_value(value)
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    result = frame.map(clean)
    result.columns = [clean(str(name)) for name in result.columns]
    return result


def register_callbacks(app, provider, registry):
    def current():
        return registry.get(browser_session["studio_id"])

    def update_grid(identifier, frame, semantic=False):
        rows, columns = grid_payload(frame, semantic)
        if semantic:
            for row, key in zip(rows, frame.index):
                row["_row_id"] = str(key)
        set_props(identifier, {"rowData": rows, "columnDefs": columns})

    def update_history(session):
        rows = [
            {
                "timestamp": item["timestamp"],
                "status": item["status"],
                "duration": item["duration"],
                "rows": item["rows"],
                "error": item["error"],
                "query": item["query"][:160],
                "_row_id": item["id"],
            }
            for index, item in enumerate(session.history)
        ]
        columns = [
            {"field": key, "headerName": title}
            for key, title in [
                ("timestamp", "Executed (UTC)"),
                ("status", "Status"),
                ("duration", "Duration (s)"),
                ("rows", "Rows received"),
                ("query", "Query preview"),
                ("error", "Error summary"),
            ]
        ]
        set_props("history-grid", {"rowData": rows, "columnDefs": columns})

    def clear_results(session):
        session.results.clear()
        for identifier in ("query-grid", "dependency-grid"):
            set_props(identifier, {"rowData": [], "columnDefs": []})
        set_props("query-status", {"children": "Ready. Run a query against the selected model."})
        set_props("dependency-status", {"children": "Find dependencies in the selected model."})

    @app.callback(Output("hydrated", "data"), Input("page", "pathname"))
    def hydrate(_):
        state = current()
        with state.lock:
            update_history(state)
            if state.spec:
                set_props("server", {"value": state.spec.server})
                set_props("catalog", {"options": [state.spec.catalog], "value": state.spec.catalog})
                set_props(
                    "connection-badge",
                    {
                        "children": f"Connected · {state.spec.server} · {state.spec.catalog}",
                        "className": "status-badge connected",
                    },
                )
                set_props(
                    "model-message", {"children": f"{len(state.metadata)} tables · cached metadata"}
                )
                set_props("model-version", {"data": str(uuid.uuid4())})
            for kind, frame in state.results.items():
                update_grid(f"{kind}-grid", frame, semantic=kind == "dependency")
                set_props(
                    f"{kind}-status",
                    {"children": f"Restored last bounded result · {len(frame):,} rows"},
                )
        instances = discover_instances()
        set_props("instances", {"options": [item.as_option() for item in instances]})
        return True

    @app.callback(
        Output("events", "data"),
        *[Input(action, "n_clicks") for action in ACTIONS],
        State("server", "value"),
        State("catalog", "value"),
        State("editor", "value"),
        State("row-limit", "value"),
        State("timeout", "value"),
        State("dep-table", "value"),
        State("dep-measure", "value"),
        State("dep-type", "value"),
        State("dep-ref-type", "value"),
        prevent_initial_call=True,
        running=[(Output(action, "disabled"), True, False) for action in ACTIONS]
        + [(Output("busy-state", "children"), "Working…", "")],
    )
    def dispatch(*args):
        action = ctx.triggered_id
        server, catalog, query, limit, timeout, table, measure, objtype, reftype = args[-9:]
        target = (
            "query-status"
            if action.startswith("query-") or action == "run-query"
            else (
                "dependency-status"
                if action.startswith("dependency-") or action == "load-dependencies"
                else "connection-message"
            )
        )
        if action == "reload-model":
            target = "model-message"
        session = current()
        if not session.lock.acquire(blocking=False):
            set_props(target, {"children": "An operation is already running in this session."})
            return no_update
        try:
            if action == "discover":
                instances = discover_instances()
                set_props("instances", {"options": [item.as_option() for item in instances]})
                set_props(
                    target,
                    {
                        "children": f"Found {len(instances)} local engine(s). "
                        "Select one or enter its port manually."
                    },
                )
            elif action == "catalogs":
                names = provider.catalogs(ConnectionSpec(validate_server(server)))
                set_props(
                    "catalog", {"options": names, "value": names[0] if len(names) == 1 else None}
                )
                set_props(
                    target, {"children": f"Found {len(names)} catalog(s). Select one and connect."}
                )
            elif action == "connect":
                # A failed target switch must never leave queries aimed at an old model.
                session.spec = None
                session.metadata = []
                clear_results(session)
                set_props(
                    "connection-badge", {"children": "Disconnected", "className": "status-badge"}
                )
                set_props("model-message", {"children": "Connect to load model metadata."})
                set_props("model-version", {"data": str(uuid.uuid4())})
                set_props(
                    "query-status", {"children": "Connect to a model before running a query."}
                )
                spec = ConnectionSpec(validate_server(server), catalog or "")
                names = provider.catalogs(spec)
                if not spec.catalog:
                    if len(names) != 1:
                        set_props("catalog", {"options": names, "value": None})
                        raise StudioError("Choose an initial catalog, then connect again.")
                    spec = ConnectionSpec(spec.server, names[0])
                if spec.catalog not in names:
                    raise StudioError("Catalog not found on this server. Find catalogs again.")
                provider.execute(spec, 'EVALUATE ROW("Connected", TRUE())', 1, 15)
                session.spec = spec
                session.metadata = []
                clear_results(session)
                set_props("catalog", {"options": names, "value": spec.catalog})
                set_props(
                    "connection-badge",
                    {
                        "children": f"Connected · {spec.server} · {spec.catalog}",
                        "className": "status-badge connected",
                    },
                )
                set_props(target, {"children": f"Connected to {spec.catalog}."})
                try:
                    session.metadata = load_metadata(provider, spec)
                    message = f"{len(session.metadata)} tables · metadata loaded"
                except StudioError as exc:
                    message = f"Connected; metadata unavailable. {exc}"
                set_props("model-message", {"children": message})
                set_props("model-version", {"data": str(uuid.uuid4())})
            elif action == "disconnect":
                session.spec = None
                session.metadata = []
                clear_results(session)
                set_props(
                    "connection-badge", {"children": "Disconnected", "className": "status-badge"}
                )
                set_props("model-message", {"children": "Connect to load model metadata."})
                set_props("model-version", {"data": str(uuid.uuid4())})
                set_props(
                    "query-status", {"children": "Disconnected. Results cleared; history retained."}
                )
                set_props(target, {"children": "Disconnected. No ADOMD connections are held open."})
            elif action == "reload-model":
                if not session.spec:
                    raise StudioError("Connect before loading metadata.")
                session.metadata = load_metadata(provider, session.spec)
                set_props("model-version", {"data": str(uuid.uuid4())})
                set_props(
                    "model-message",
                    {"children": f"{len(session.metadata)} tables · metadata loaded"},
                )
            elif action == "run-query":
                session.results.pop("query", None)
                set_props("query-grid", {"rowData": [], "columnDefs": []})
                try:
                    result = run_with_history(provider, session, query, limit, timeout)
                finally:
                    update_history(session)
                session.results["query"] = result.frame
                update_grid("query-grid", result.frame)
                suffix = (
                    " · TRUNCATED at row/byte limit; narrow your query." if result.truncated else ""
                )
                empty = " · Query returned zero rows." if result.frame.empty else ""
                set_props(
                    target,
                    {
                        "children": f"Success · {len(result.frame):,} rows received · "
                        f"{result.duration:.3f} s{suffix}{empty}"
                    },
                )
            elif action == "load-dependencies":
                session.results.pop("dependency", None)
                set_props("dependency-grid", {"rowData": [], "columnDefs": []})
                if not session.spec:
                    raise StudioError("Connect before loading dependencies.")
                query_text = dependency_query(table, measure, objtype, reftype)
                result = provider.execute(session.spec, query_text, 10_000, 60)
                result.frame = normalize_dependencies(result.frame)
                result.frame.index = [str(uuid.uuid4()) for _ in range(len(result.frame))]
                session.results["dependency"] = result.frame
                update_grid("dependency-grid", result.frame, semantic=True)
                suffix = " · TRUNCATED; refine filters." if result.truncated else ""
                set_props(
                    target,
                    {
                        "children": f"Success · {len(result.frame):,} dependencies · "
                        f"{result.duration:.3f} s{suffix}"
                    },
                )
            elif action == "clear-history":
                session.history.clear()
                update_history(session)
            elif action.endswith(("-csv", "-xlsx")):
                source, extension = action.rsplit("-", 1)
                frame = session.results.get(source)
                if frame is None:
                    raise StudioError("Run a successful query before exporting results.")
                frame = safe_export(frame)
                if extension == "csv":
                    download = dcc.send_string(frame.to_csv(index=False), f"{source}.csv")
                else:
                    stream = io.BytesIO()
                    # Write every string as a literal. Formula-like strings were neutralized above.
                    frame.to_excel(stream, index=False, engine="openpyxl")
                    download = dcc.send_bytes(stream.getvalue(), f"{source}.xlsx")
                set_props("download", {"data": download})
        except StudioError as exc:
            set_props(target, {"children": f"Failed · {exc}"})
        except Exception:
            # Deliberately avoid raw exception or request logging (may include model data).
            set_props(
                target,
                {
                    "children": "Operation failed unexpectedly. Reconnect and retry. "
                    "Check the setup and limitations in README."
                },
            )
        finally:
            session.touched = monotonic()
            session.lock.release()
        return str(uuid.uuid4())

    @app.callback(Output("server", "value"), Input("instances", "value"), prevent_initial_call=True)
    def choose_instance(server):
        return server or no_update

    @app.callback(
        Output("connection-panel", "is_open"),
        Input("toggle-connection", "n_clicks"),
        State("connection-panel", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_connection(_, opened):
        return not opened

    @app.callback(
        *[
            Output(f"{name}-pane", "style")
            for name in ("query", "dependencies", "history", "about")
        ],
        Input("tabs", "active_tab"),
    )
    def select_tab(tab):
        return [
            {"display": "block" if name == tab else "none"}
            for name in ("query", "dependencies", "history", "about")
        ]

    @app.callback(
        Output("app-shell", "data-theme"),
        Output("query-grid", "className"),
        Output("dependency-grid", "className"),
        Output("history-grid", "className"),
        Input("theme", "value"),
    )
    def theme(light):
        name = "ag-theme-quartz studio-grid" if light else "ag-theme-quartz-dark studio-grid"
        return ("light" if light else "dark", name, name, name)

    @app.callback(
        Output("model-tree", "children"),
        Input("model-version", "data"),
        Input("model-search", "value"),
        Input("expand-model", "n_clicks"),
        Input("collapse-model", "n_clicks"),
    )
    def model_tree(_, search, expand, collapse):
        search = (search or "").casefold()
        expand = bool(search) or ctx.triggered_id == "expand-model"
        nodes = []
        for table in current().metadata:
            matches = search in table["name"].casefold()
            objects = [
                obj for obj in table["objects"] if matches or search in obj["name"].casefold()
            ]
            if search and not objects and not matches:
                continue
            hidden = " · hidden" if table["hidden"] else ""
            nodes.append(
                html.Details(
                    [
                        html.Summary(f"{table['name']}{hidden}"),
                        html.Button(
                            "Insert table name",
                            id={"type": "model-object", "name": table["identifier"]},
                            n_clicks=0,
                            className="object-button table-insert",
                        ),
                        *[
                            html.Button(
                                [
                                    html.Span(
                                        "ƒ" if obj["kind"] == "Measure" else "▤",
                                        className="object-kind",
                                    ),
                                    html.Span(obj["name"]),
                                    html.Small(
                                        f"{obj['type']}" + (" · hidden" if obj["hidden"] else "")
                                    ),
                                ],
                                id={"type": "model-object", "name": obj["identifier"]},
                                n_clicks=0,
                                title=f"{obj['kind']} · {obj['identifier']}",
                                className="object-button",
                            )
                            for obj in objects
                        ],
                    ],
                    open=expand,
                )
            )
        return nodes or html.Small("No matching objects." if search else "No model loaded.")

    @app.callback(
        Output("editor", "value"),
        Input("examples", "value"),
        Input("clear-query", "n_clicks"),
        Input("history-grid", "cellClicked"),
        Input("dependency-grid", "cellClicked"),
        prevent_initial_call=True,
    )
    def replace_editor(example, clear, history_click, dependency_click):
        trigger = ctx.triggered_id
        if trigger == "clear-query":
            return ""
        if trigger == "examples":
            return EXAMPLES.get(example, no_update)
        state = current()
        if trigger == "history-grid" and history_click:
            try:
                value = next(
                    item["query"] for item in state.history if item["id"] == history_click["rowId"]
                )
            except (KeyError, StopIteration):
                raise PreventUpdate from None
            set_props("tabs", {"active_tab": "query"})
            return value
        if trigger == "dependency-grid" and dependency_click:
            try:
                row = state.results["dependency"].loc[dependency_click["rowId"]].to_dict()
            except (KeyError, ValueError, IndexError):
                raise PreventUpdate from None
            set_props("tabs", {"active_tab": "query"})
            return query_for_dependency(row)
        raise PreventUpdate

    @app.callback(
        Output("insert-object", "data"),
        Input({"type": "model-object", "name": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def insert_object(clicks):
        if not any(clicks) or not ctx.triggered_id:
            raise PreventUpdate
        return {"text": ctx.triggered_id["name"], "nonce": str(uuid.uuid4())}

    app.clientside_callback(
        """function(data) {
            if (!data) return window.dash_clientside.no_update;
            const el = document.getElementById('editor');
            if (!el) return window.dash_clientside.no_update;
            const start = el.selectionStart, end = el.selectionEnd;
            const value = el.value.slice(0, start) + data.text + el.value.slice(end);
            window.dash_clientside.set_props('editor', {value: value});
            window.dash_clientside.set_props('tabs', {active_tab: 'query'});
            setTimeout(() => {el.focus(); el.setSelectionRange(start + data.text.length,
                                                             start + data.text.length);}, 100);
            return window.dash_clientside.no_update;
        }""",
        Output("insert-object", "clear_data"),
        Input("insert-object", "data"),
        prevent_initial_call=True,
    )
