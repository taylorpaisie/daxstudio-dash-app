from datetime import datetime
from decimal import Decimal

import pytest

from src.connections.adomd_provider import (
    AdomdProvider,
    browser_value,
    connection_string,
    reader_to_frame,
    unique_names,
    validate_server,
)
from src.connections.base import ConnectionSpec, StudioError
from src.connections.desktop_discovery import discover_instances, workspace_roots
from tests.fakes import FakeConnection, FakeReader


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-16-le"])
def test_discovery_encodings(tmp_path, encoding):
    path = tmp_path / "AnalysisServicesWorkspace123" / "Data"
    path.mkdir(parents=True)
    (path / "msmdsrv.port.txt").write_text("54321", encoding=encoding)
    items = discover_instances([tmp_path], probe=lambda p: p == 54321, processes=[])
    assert len(items) == 1
    assert items[0].server == "localhost:54321"
    assert items[0].workspace == "AnalysisServicesWorkspace123"


def test_discovery_store_stale_malformed_and_duplicate(tmp_path):
    package = tmp_path / "Packages/Microsoft.MicrosoftPowerBIDesktop_8wekyb3d8bbwe"
    package.mkdir(parents=True)
    roots = workspace_roots(tmp_path, tmp_path / "profile")
    assert len(roots) == 6
    for root, port in zip(roots, ["1234", "1234", "bad", "65536", "2345"]):
        path = root / "Workspace" / "Data"
        path.mkdir(parents=True)
        (path / "msmdsrv.port.txt").write_text(port)
    result = discover_instances(roots, probe=lambda p: p == 1234, processes=[])
    assert len(result) == 1


def test_discovery_process_workspace(tmp_path):
    path = tmp_path / "outside" / "Workspace42" / "Data"
    path.mkdir(parents=True)
    (path / "msmdsrv.port.txt").write_text("3456")
    result = discover_instances(
        [],
        probe=lambda _: True,
        processes=[{"pid": 42, "cmdline": ["msmdsrv.exe", "-s", str(path)]}],
    )
    assert result[0].pid == 42


@pytest.mark.parametrize(
    "server",
    [
        "remote:1234",
        "localhost",
        "localhost:0",
        "localhost:65536",
        "localhost:123;Password=x",
        "http://localhost:123",
        "",
        None,
    ],
)
def test_invalid_servers(server):
    with pytest.raises(StudioError):
        validate_server(server)


def test_connection_string_quotes_catalog():
    result = connection_string(ConnectionSpec("127.0.0.1:1234", 'name";Password=abc'))
    assert 'Initial Catalog="name"";Password=abc";' in result
    assert "Data Source=localhost:1234" in result
    assert "Connect Timeout=10" in result


def test_reader_conversion_null_precision_dates_duplicate_names():
    reader = FakeReader(
        ["x", "x", "x (2)", "date", "decimal", "bool"],
        [[2**60, None, "text", datetime(2026, 1, 1), Decimal("1.123456789123456789"), True]],
    )
    frame = reader_to_frame(reader, 10).frame
    assert list(frame.columns) == ["x", "x (2)", "x (2) (2)", "date", "decimal", "bool"]
    assert frame.iloc[0, 0] == 2**60
    assert frame.iloc[0, 1] is None
    assert browser_value(frame.iloc[0, 0]) == str(2**60)
    assert browser_value(frame.iloc[0, 4]) == "1.123456789123456789"
    assert browser_value(frame.iloc[0, 3]) == "2026-01-01T00:00:00"
    assert unique_names(["", "", "Column (2)"]) == ["Column", "Column (2)", "Column (2) (2)"]


def test_empty_result_preserves_schema():
    result = reader_to_frame(FakeReader(["Value"], []), 100)
    assert result.frame.empty and list(result.frame.columns) == ["Value"]
    assert not result.truncated


def test_row_and_byte_limit():
    result = reader_to_frame(FakeReader(["x"], [[1], [2], [3]]), 2)
    assert len(result.frame) == 2 and result.truncated
    assert not reader_to_frame(FakeReader(["x"], [[1], [2]]), 2).truncated
    assert reader_to_frame(FakeReader(["x"], [["x" * 100]]), 10, byte_limit=20).truncated


@pytest.mark.parametrize("mode", ["success", "connection", "reader"])
def test_adapter_closes_resources(mode):
    reader = FakeReader(["x"], [[1]], error=mode == "reader")
    connection = FakeConnection(reader, fail=mode == "connection")
    provider = AdomdProvider(factory=lambda _: connection)
    if mode == "success":
        assert (
            provider.execute(ConnectionSpec("localhost:1234"), "EVALUATE ROW()", 5, 20).frame.iloc[
                0, 0
            ]
            == 1
        )
        assert connection.command.CommandTimeout == 20
    else:
        with pytest.raises(StudioError) as error:
            provider.execute(ConnectionSpec("localhost:1234"), "EVALUATE ROW()", 5, 20)
        assert "Secret" not in str(error.value)
    assert connection.closed and connection.disposed
    if mode != "connection":
        assert reader.closed and connection.command.disposed


def test_missing_client_is_actionable(monkeypatch):
    monkeypatch.setenv("DAX_ADOMD_DLL", "Z:/does-not-exist.dll")
    from src.connections.adomd_provider import _client_factory

    with pytest.raises(StudioError, match="ADOMD.NET|Windows"):
        _client_factory()
