import base64
import io

from openpyxl import load_workbook

from app import create_app
from src.callbacks.workspace import ACTIONS
from tests.fakes import FakeProvider


def dispatch(client, action, **values):
    state = {"server": "localhost:1234", "catalog": "TEST MODEL", "editor": "EVALUATE ROW()",
             "row-limit": 1000, "timeout": 30, "dep-table": "", "dep-measure": "",
             "dep-type": "", "dep-ref-type": ""}
    state.update(values)
    response = client.post("/_dash-update-component", json={
        "output": "events.data", "outputs": {"id": "events", "property": "data"},
        "inputs": [{"id": name, "property": "n_clicks", "value": 1 if name == action else 0}
                   for name in ACTIONS],
        "state": [{"id": key, "property": "value", "value": value} for key, value in state.items()],
        "changedPropIds": [f"{action}.n_clicks"],
    })
    assert response.status_code == 200, response.data
    return response.json.get("sideUpdate", {})


def test_layout_endpoints_and_host_origin_guards():
    app = create_app(FakeProvider())
    client = app.server.test_client()
    assert client.get("/").status_code == 200
    response = client.get("/_dash-layout")
    assert response.status_code == 200
    for name in ["editor", "query-grid", "dependency-grid", "history-grid", "model-tree"]:
        assert name.encode() in response.data
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert client.post("/_dash-update-component", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/_dash-dependencies").status_code == 200


def test_full_callback_flow_and_session_isolation():
    provider = FakeProvider()
    app = create_app(provider)
    client = app.server.test_client()
    client.get("/")
    result = dispatch(client, "connect")
    assert "Connected" in result["connection-badge"]["children"]
    assert "1 tables" in result["model-message"]["children"]
    result = dispatch(client, "run-query")
    assert len(result["query-grid"]["rowData"]) == 2
    assert result["history-grid"]["rowData"][0]["status"] == "Success"
    history_id = result["history-grid"]["rowData"][0]["_row_id"]
    response = client.post("/_dash-update-component", json={
        "output": "editor.value", "outputs": {"id": "editor", "property": "value"},
        "inputs": [{"id": "examples", "property": "value", "value": None},
                   {"id": "clear-query", "property": "n_clicks", "value": 0},
                   {"id": "history-grid", "property": "cellClicked", "value": {"rowId": history_id}},
                   {"id": "dependency-grid", "property": "cellClicked", "value": None}],
        "state": [], "changedPropIds": ["history-grid.cellClicked"],
    })
    assert response.json["response"]["editor"]["value"] == "EVALUATE ROW()"
    exported = dispatch(client, "query-csv")["download"]["data"]
    assert "Value,Blank" in exported["content"]
    exported = dispatch(client, "query-xlsx")["download"]["data"]
    workbook = load_workbook(io.BytesIO(base64.b64decode(exported["content"])))
    assert workbook.active["A2"].value == 1
    assert "dependencies" in dispatch(client, "load-dependencies")["dependency-status"]["children"]
    assert "INFO.CALCDEPENDENCY" in provider.queries[-1]
    result = dispatch(client, "run-query", editor="EVALUATE EMPTY")
    assert "zero rows" in result["query-status"]["children"]
    result = dispatch(client, "run-query", editor="EVALUATE BROKEN")
    assert result["query-grid"]["rowData"] == []
    assert result["history-grid"]["rowData"][0]["status"] == "Failed"
    other = app.server.test_client()
    other.get("/")
    assert "Connect to a model" in dispatch(other, "run-query")["query-status"]["children"]
    assert dispatch(client, "disconnect")["connection-badge"]["children"] == "Disconnected"
    assert dispatch(client, "clear-history")["history-grid"]["rowData"] == []


def test_real_default_never_substitutes_fake(monkeypatch):
    monkeypatch.setenv("DAX_ADOMD_DLL", "Z:/missing.dll")
    client = create_app().server.test_client()
    client.get("/")
    response = dispatch(client, "connect")
    assert "ADOMD.NET could not load" in response["connection-message"]["children"]
    assert "query-grid" not in response
