"""Real ADOMD.NET adapter. CLR loading is lazy so the UI works without ADOMD."""

import math
import os
import re
import sys
import threading
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter

import pandas as pd

from src.connections.base import ConnectionSpec, QueryResult, StudioError

_CLR_LOCK = threading.Lock()
MAX_BYTES = 8_000_000


def validate_server(server: str) -> str:
    match = re.fullmatch(r"(localhost|127\.0\.0\.1):([0-9]{1,5})", (server or "").strip(), re.I)
    if not match or not 1 <= int(match[2]) <= 65535:
        raise StudioError("Use localhost:PORT or 127.0.0.1:PORT, with a port from 1 to 65535.")
    return f"localhost:{int(match[2])}"


def connection_string(spec: ConnectionSpec) -> str:
    server = validate_server(spec.server)
    catalog = spec.catalog or ""
    if len(catalog) > 512 or any(ord(c) < 32 for c in catalog):
        raise StudioError("The catalog name is invalid.")
    quoted = catalog.replace('"', '""')
    return (
        f'Data Source={server};Initial Catalog="{quoted}";'
        "Connect Timeout=10;Application Name=DAX Browser Studio;"
    )


def _client_factory():
    if sys.platform != "win32":
        raise StudioError("The Desktop adapter requires Windows and 64-bit Python 3.11 or 3.12.")
    with _CLR_LOCK:
        try:
            from pythonnet import load

            load("netfx")
            import clr

            bundled = (
                Path(__file__).resolve().parents[2]
                / "vendor/adomd/Microsoft.AnalysisServices.AdomdClient.dll"
            )
            configured = os.environ.get("DAX_ADOMD_DLL") or (
                str(bundled) if bundled.is_file() else None
            )
            if configured:
                path = Path(configured).resolve()
                if not path.is_file():
                    raise FileNotFoundError
                if str(path.parent) not in sys.path:
                    sys.path.insert(0, str(path.parent))
                clr.AddReference(str(path))
            else:
                clr.AddReference("Microsoft.AnalysisServices.AdomdClient")
            from Microsoft.AnalysisServices.AdomdClient import AdomdConnection

            return AdomdConnection
        except Exception:
            raise StudioError(
                "ADOMD.NET could not load. Install 64-bit Python and .NET Framework 4.8; "
                "restore Microsoft's Microsoft.AnalysisServices.AdomdClient NuGet package "
                "with its dependencies and set DAX_ADOMD_DLL to the net472 client DLL. "
                "See README → Microsoft client setup, then restart the app."
            ) from None


def python_value(value):
    """Convert pythonnet scalars without losing large integers/decimal precision."""
    if value is None:
        return None
    net_type = str(value.GetType().FullName) if hasattr(value, "GetType") else ""
    if net_type == "System.DBNull":
        return None
    if net_type == "System.DateTime":
        return datetime.fromisoformat(str(value.ToString("o")))
    if net_type == "System.Decimal":
        from System.Globalization import CultureInfo

        return Decimal(str(value.ToString(CultureInfo.InvariantCulture)))
    if net_type == "System.Boolean":
        return str(value).lower() == "true"
    if net_type in {"System.Int16", "System.Int32", "System.Int64", "System.Byte"}:
        return int(value)
    if net_type in {"System.Double", "System.Single"}:
        return float(value)
    if isinstance(value, (str, int, float, bool, datetime, Decimal)):
        return value
    return str(value)


def unique_names(names):
    used = set()
    result = []
    for raw in names:
        name = str(raw) or "Column"
        candidate, index = name, 2
        while candidate in used:
            candidate = f"{name} ({index})"
            index += 1
        used.add(candidate)
        result.append(candidate)
    return result


def reader_to_frame(reader, limit: int, byte_limit: int = MAX_BYTES) -> QueryResult:
    count = int(reader.FieldCount)
    if count > 500:
        raise StudioError("Result exceeds 500 columns. Select fewer columns in the DAX query.")
    names = unique_names(reader.GetName(i) for i in range(count))
    rows, size = [], 0
    truncated = False
    while reader.Read():
        if len(rows) >= limit:
            truncated = True
            break
        row = [
            None if reader.IsDBNull(i) else python_value(reader.GetValue(i)) for i in range(count)
        ]
        size += sum(len(str(v).encode("utf-8")) + 16 for v in row)
        if size > byte_limit:
            truncated = True
            break
        rows.append(row)
    # object dtype prevents nullable int64 values being silently coerced to float.
    return QueryResult(pd.DataFrame(rows, columns=names, dtype=object), truncated)


class AdomdProvider:
    def __init__(self, factory=None):
        self._factory = factory

    @contextmanager
    def _connection(self, spec):
        text = connection_string(spec)
        factory = self._factory or _client_factory()
        connection = None
        try:
            connection = factory(text)
            try:
                connection.Open()
            except Exception:
                raise StudioError(
                    "Connection failed. Keep the PBIX open, refresh its port, confirm the "
                    "catalog, and run under the same Windows user as Power BI Desktop."
                ) from None
            yield connection
        finally:
            if connection is not None:
                try:
                    connection.Close()
                finally:
                    connection.Dispose()

    def catalogs(self, spec: ConnectionSpec) -> list[str]:
        result = self.execute(
            ConnectionSpec(spec.server),
            "SELECT CATALOG_NAME FROM $SYSTEM.DBSCHEMA_CATALOGS",
            100,
            15,
        )
        return [str(value) for value in result.frame.iloc[:, 0] if value is not None]

    def execute(self, spec, query, limit=1000, timeout=30):
        limit = max(1, min(int(limit), 10_000))
        timeout = max(1, min(int(timeout), 120))
        start = perf_counter()
        with self._connection(spec) as connection:
            command, reader = None, None
            try:
                command = connection.CreateCommand()
                command.CommandText = query
                command.CommandTimeout = timeout
                reader = command.ExecuteReader()
                result = reader_to_frame(reader, limit)
                result.duration = perf_counter() - start
                return result
            except StudioError:
                raise
            except Exception as exc:
                # Do not echo engine messages: these can contain formulas/data/secrets.
                message = str(exc).lower()
                if "timeout" in message or "timed out" in message:
                    summary = (
                        "Query timed out. Reduce its scope or raise the timeout (maximum 120s)."
                    )
                elif "calcdependency" in message or "permission" in message:
                    summary = (
                        "Dependency metadata is unavailable. Use a current Power BI Desktop "
                        "version and a local model with write permission; live connections "
                        "may not support INFO.CALCDEPENDENCY()."
                    )
                else:
                    summary = (
                        "DAX execution failed. Check syntax, table/column names and function "
                        "availability. If the model closed, refresh the connection. "
                        "Engine details are withheld because they can include model data."
                    )
                raise StudioError(summary) from None
            finally:
                try:
                    if reader is not None:
                        reader.Close()
                finally:
                    if command is not None:
                        command.Dispose()


def browser_value(value):
    value = python_value(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal) or (
        isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53 - 1
    ):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
