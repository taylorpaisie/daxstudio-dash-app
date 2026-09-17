# DAX Browser Studio

A local, read-only browser workspace for querying an open Power BI Desktop semantic model and exploring its metadata and dependencies. Built with Python, Dash, Dash Bootstrap Components, Dash AG Grid, pandas, and Microsoft's real ADOMD.NET client through pythonnet.

**Status:** first MVP. The interface and mocked connection workflows are tested on Windows with Python 3.11. No Power BI Desktop engine was running during development; live-model execution, metadata compatibility, discovery against a real installation, and engine timeouts still require validation with your PBIX. Normal startup always uses the real adapter. There is no automatic demo mode.

## Features

- Automatic best-effort discovery on page load and refresh, including standard/Store workspace paths and engine process workspace arguments. Shows local endpoint, workspace, process ID, and report window title when available.
- Manual `localhost:PORT` entry, catalog discovery/selection, connect/disconnect, and actionable missing-library errors.
- Large plain-text DAX editor, Ctrl+Enter (Cmd+Enter also works), Tab indentation, example queries, execution timer, configurable timeout and row limit.
- Sortable, filterable, resizable, paginated AG Grid results, persistent headers, cell text selection/copy, and CSV/XLSX downloads without an AG Grid Enterprise license.
- Searchable, expandable model explorer with tables, columns, measures, data types, hidden flags and correctly escaped DAX name insertion at the editor cursor.
- Dependency table powered by `INFO.CALCDEPENDENCY()`, with model-side table/name/type filters, exports and click-to-generate queries.
- Last 50 query executions with UTC timestamp, duration, rows, success/failure and error summary; click to restore a query.
- Dark/light themes, collapsible connection panel and compact laptop layout. All runtime scripts/styles are served locally.

## Prerequisites

- Windows 10/11, **64-bit Python 3.11 or 3.12**, and a current Power BI Desktop installation.
- A PBIX open under the same Windows account, with a local semantic model. Thin/live-connected reports can lack local metadata.
- .NET Framework **4.8** (or 4.8.1) for pythonnet's `netfx` runtime.
- Microsoft ADOMD.NET and its dependencies (setup below). Python packages do **not** bundle Microsoft's client.
- For the reproducible client restore below, install a Microsoft **.NET SDK**, not just the runtime. Check `dotnet --list-sdks`; it must print an SDK. The project targets `net472` and supplies reference assemblies through NuGet, so a separate targeting pack is unnecessary.

## Install Python dependencies

Run these commands from the project directory.

PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Git Bash:

```bash
py -3.11 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Use `py -3.12` instead for Python 3.12. If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` in place of `python`; activation is optional, and no execution-policy change is required.

## Microsoft client setup

Microsoft distributes current Analysis Services clients through **NuGet**, rather than the retired MSI installer. This project uses `Microsoft.AnalysisServices.AdomdClient` **19.117.0**, targeting .NET Framework 4.7.2 with the .NET Framework 4.8 runtime. Do not mix the `net6.0` DLL with the `netfx` runtime.

With a .NET SDK installed, run this in either PowerShell or Git Bash:

```text
dotnet build tools/adomd-client/Client.csproj --configuration Release --output vendor/adomd
```

This restores the official package and its transitive dependencies and copies the runtime files into `vendor/adomd`. Keep the **whole output directory**, including subdirectories and dependency DLLs. Do not copy just the main DLL. The app automatically looks for:

```text
vendor/adomd/Microsoft.AnalysisServices.AdomdClient.dll
```

The SDK is needed only for setup. `vendor/`, build output and NuGet intermediates are ignored by Git. The Microsoft package has its own license; it is not included in this repository.

Alternatively, point to a compatible client installed by your organization, with all its dependencies alongside it:

PowerShell:

```powershell
$env:DAX_ADOMD_DLL = 'C:\path\to\Microsoft.AnalysisServices.AdomdClient.dll'
python app.py
```

Git Bash:

```bash
export DAX_ADOMD_DLL='C:/path/to/Microsoft.AnalysisServices.AdomdClient.dll'
python app.py
```

Resolution order is explicit `DAX_ADOMD_DLL`, project `vendor/adomd`, then a registered .NET assembly (GAC). Restart after changing the path. The UI loads even if the library is missing; connecting displays setup guidance. The documented SDK restore could not be run in the development environment because it had .NET runtimes but no SDK.

## Launch

After activating the virtual environment, both shells use:

```text
python app.py
```

Without activation, PowerShell uses:

```powershell
.\.venv\Scripts\python.exe app.py
```

Without activation, Git Bash uses:

```bash
./.venv/Scripts/python.exe app.py
```

Open **http://127.0.0.1:8050**. Stop with Ctrl+C. Startup uses Waitress, binds explicitly to `127.0.0.1`, and does not enable Dash debug mode. There is no public-host option or credential prompt in this release.

## Connect and query

1. Open a PBIX in Power BI Desktop and wait for the model to finish loading.
2. In the app, click **Refresh** and select the matching discovered instance. Discovery also runs when the page opens.
3. If nothing appears, enter the local server manually, for example `localhost:54321`.
4. Click **Find catalogs**, choose an initial catalog, then **Connect**. Connect can choose automatically when exactly one catalog exists. Catalog names can be generated GUIDs rather than report names.
5. Try the **Connection check** example, then click **Run query** or press Ctrl+Enter.
6. Expand the model explorer; click a table, column or measure to insert its quoted DAX identifier. A single quote in a table is doubled; a closing bracket in an object name is doubled.
7. Open **Dependencies** and enter filter text. Use object type `MEASURE` to restrict the dependent objects to measures; leave types blank to include calculated columns and other objects. Click **Find dependencies**. Click any result row to generate a focused metadata query in the editor.

The connection badge records the last successful validation; it is not a continuous heartbeat. Each operation opens its own connection and reliably closes the reader, command and connection. **Disconnect** clears the active target, metadata and results, retaining history until you clear it or the session expires.

## Find the Desktop port manually

Discovery checks these workspace locations:

```text
%LOCALAPPDATA%\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces
%LOCALAPPDATA%\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces
%USERPROFILE%\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces
%LOCALAPPDATA%\Packages\Microsoft.MicrosoftPowerBIDesktop_*\LocalCache\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces
%LOCALAPPDATA%\Packages\Microsoft.MicrosoftPowerBIDesktop_*\LocalCache\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces
%LOCALAPPDATA%\Packages\Microsoft.MicrosoftPowerBIDesktop_*\LocalState\AnalysisServicesWorkspaces
```

Within a workspace, look in `Data\msmdsrv.port.txt`. The file contains the port (sometimes UTF-16). Only listening ports are displayed automatically. Stale, inaccessible, malformed and duplicate workspaces are skipped. Process `-s` workspace paths supplement directory discovery. Store and future Desktop releases can use different locations; manual entry remains available.

PowerShell, standard/Store common locations:

```powershell
$roots = @(
  "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces",
  "$env:LOCALAPPDATA\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces",
  "$env:USERPROFILE\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces"
)
Get-ChildItem -LiteralPath $roots -Filter msmdsrv.port.txt -Recurse -ErrorAction SilentlyContinue |
  ForEach-Object { $_.FullName; Get-Content -LiteralPath $_.FullName }
```

Git Bash (uses the discovery module, which handles encodings):

```bash
python -c "from src.connections.desktop_discovery import discover_instances; [print(x.as_dict()) for x in discover_instances()]"
```

If directory discovery fails, inspect the engine's local listening TCP port. PowerShell:

```powershell
$engineIds = @(Get-Process msmdsrv -ErrorAction SilentlyContinue).Id
Get-NetTCPConnection -State Listen |
  Where-Object { $_.OwningProcess -in $engineIds } |
  Select-Object LocalAddress, LocalPort, OwningProcess
```

You can also use Windows Resource Monitor → Network → Listening Ports and locate `msmdsrv.exe`. Enter `localhost:<LocalPort>` in the app. Ports change when Desktop restarts; keep the report open.

## Results and limits

- Default 1,000 rows; configurable from 1 to **10,000**. The adapter reads at most the selected limit plus one row to detect truncation. It also stops at an approximate **8 MB** value budget and rejects more than **500 columns**. A clear truncation notice indicates an incomplete result; the displayed count is received rows, not the total server count.
- Limits protect transfer and browser rendering; they do not make an expensive DAX query cheap for the engine. Use `TOPN`, filters and explicit column selection. A single very large engine value may still allocate memory before the client can reject its row.
- Timeout defaults to 30 seconds, configurable up to 120. Connection establishment has a separate 10-second timeout. Metadata uses 30 seconds per rowset; dependencies use 60 seconds. Cancellation is intentionally absent because safe in-flight cancellation has not been validated. A stalled native driver is not forcibly terminated.
- Only the **first result set** is shown. Use separate runs for multiple `EVALUATE` statements.
- Numbers use locale-aware display formatting; blank values remain blank, booleans use boolean cells, dates use ISO text. Decimal values and integers outside JavaScript's exact integer range are preserved as strings, so those columns sort as text. Full precision is available in their text values and exports.
- Exports include the whole **bounded result**, not AG Grid's current sorting/filtering/page. No unlimited export runs in the background. CSV/XLSX neutralize formula-like text and header values with a leading apostrophe; numeric negative values remain numbers. Dates and high-precision values are exported as text to preserve values and avoid Excel timezone/precision problems.
- DAX history is process-memory only and capped at 50 entries. Browser tabs share their cookie session and active connection; avoid switching models in another tab during a query. Reload restores the last results/history. Idle sessions are discarded on a subsequent request after 30 minutes; at most 16 are retained. Stopping the server clears all sessions.
- The editor is a polished textarea fallback, **without syntax highlighting or autocomplete**. The older `dash-ace` wrapper was not adopted as a dependency for this MVP.
- INFO dependency data describes model calculation references, not a complete Power Query/data-source lineage graph. It may omit references outside its supported scope. Unsupported functions or permissions produce errors, never fake rows.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `ADOMD.NET could not load` | Use 64-bit Python; confirm .NET Framework 4.8; restore the `net472` client and dependencies; check `DAX_ADOMD_DLL` and restart. Do not install the unrelated Python `clr` package. |
| `No .NET SDKs were found` | Install a .NET SDK from Microsoft; a runtime alone cannot run `dotnet build`. Restart your shell, then run `dotnet --list-sdks`. |
| No instances discovered | Keep a local PBIX open, refresh, inspect workspace paths/Resource Monitor and enter the port manually. A thin report may have no usable local model. |
| Connection failed | Refresh after reopening Desktop; verify port and selected catalog, Windows user and local firewall policy. Close/reopen the PBIX if its engine is stale. |
| Catalog not found / multiple catalogs | Click Find catalogs again and explicitly select the current model. A previous model's catalog is not reused automatically on another server. |
| Metadata unavailable | Some server versions/connection types restrict `TMSCHEMA_*` rowsets. Querying can still work when explorer loading fails. Try Reload or focused `INFO.TABLES()` / `INFO.MEASURES()` queries. |
| `INFO.CALCDEPENDENCY` unavailable | Update Desktop. Microsoft requires model write permission for this read operation, and does not support it in some live-connection contexts. The application itself performs no model writes. |
| Query failed | Check DAX syntax, identifier quoting and engine function support. Try the Connection check example. Raw engine messages are withheld because they can include formulas/data; retry in Desktop's DAX query view for detailed engine diagnostics. |
| Query timed out / result truncated | Narrow filters, select fewer columns and use TOPN. Raise the timeout within the UI limit if appropriate. |
| Empty grid | Read the status: successful zero-row queries are distinct from failed queries; failed queries clear stale result rows. |
| Port 8050 already in use | Stop the earlier app process with Ctrl+C. This release uses a fixed loopback application port. The Desktop engine port is a separate value. |
| Stale or expired session | Reconnect. Server restart intentionally invalidates previous session cookies. |
| Ruff executable blocked on managed Windows | Use the Black/Flake8 commands below. Browser smoke uses an already-installed Chrome/Edge executable, without downloading a driver. |

## Privacy and security

This is a **single-user local tool**, not a hosted multi-user service. Do not expose it through a reverse proxy or port-forward it. Loopback binding, Host/Origin checks, same-site HTTP-only session cookies, no-store responses and frame blocking reduce accidental exposure. They do not isolate the app from other trusted/untrusted processes running under your Windows account.

The app accepts only local server addresses, uses Windows identity and has no token/password UI. Connection strings quote catalog values; browser input never becomes a shell command. The query service permits DAX `EVALUATE`/query-scoped `DEFINE`, rejecting procedural/model-writing commands. This is a UI guard, not a database authorization boundary; use appropriate server permissions. Custom metadata queries are fixed service code.

No queries, results, credentials or tokens are logged by application code. Only short, sanitized error categories enter history. Queries themselves can contain sensitive literals: avoid embedding credentials/tokens in DAX. History necessarily retains the query you entered until cleared. Nothing is automatically written to disk; browser downloads, OS paging and browser memory remain subject to local security policy. Internet access is needed for package setup, but not for normal local operation. Bootstrap is vendored with its license; there are no runtime CDN requests.

## Development and tests

Activate the environment, then use the same commands in either shell:

```text
python -m pip install -r requirements-dev.txt
python -m black --check app.py src tests
python -m flake8 app.py src tests --jobs 1
python -m pytest -q
python -m tests.browser_smoke
```

`tests.browser_smoke` starts temporary loopback servers on 8051/8052 and installed Chrome (or Edge) headlessly with DevTools on 9227. It checks the real adapter's disconnected startup, then **explicitly injects `tests.fakes.FakeProvider`** into a separate app for synthetic query/model workflows. Screenshots and browser profile data go to ignored `test-results/`. The fake is never imported by `app.py` or any normal startup path. Close anything using these test ports first.

Tests cover directory/process discovery, port encodings, stale files, connection validation/quoting, DAX escaping/read-only guards, ADOMD conversion, nulls, duplicate names, empty results, row/byte limits, exact numeric preservation, connection/query failures and cleanup, dependency filters, metadata joins, session isolation, callback flows, history restoration and exports. See [VALIDATION.md](VALIDATION.md) for the recorded development results and remaining live checks.

## Architecture

```text
app.py                         # factory, local request guards, Waitress entry point
src/components/                # layout, examples, grid serialization
src/callbacks/                 # UI events and export handling
src/connections/base.py        # ConnectionProvider protocol and data contracts
src/connections/desktop_discovery.py
src/connections/adomd_provider.py
src/services/                  # read-only query, metadata and dependency services
src/models/                    # bounded, locked in-memory sessions
src/utilities/                 # DAX escaping/validation
assets/                        # local Bootstrap, application CSS and keyboard/grid JS
tests/                         # unit/callback tests, explicit fake, browser smoke
tools/adomd-client/             # official NuGet dependency restore project
```

The provider contract accepts a target and returns a bounded pandas result; it owns resource lifetimes. Adapters can later implement Power BI Execute Queries REST, Fabric/Power BI XMLA and SSAS. Remote authentication and capability-specific metadata will require additional provider settings/services; the current Desktop adapter intentionally validates only loopback endpoints.

Planned: maintained editor integration with DAX syntax/autocomplete, safe cancellation, richer engine diagnostics, dependency network visualization using the existing source/reference fields, query plans/timings, published-model adapters and optional saved query files. Model editing is outside this release's scope.

## API references

Implementation references checked during development:

- [Dash callbacks and running state](https://dash.plotly.com/advanced-callbacks)
- [Dash AG Grid](https://dash.plotly.com/dash-ag-grid) and [current theming API](https://dash.plotly.com/dash-ag-grid/styling-themes)
- [Dash Bootstrap Components](https://www.dash-bootstrap-components.com/)
- [pythonnet runtime loading](https://pythonnet.github.io/pythonnet/pyreference.html)
- [Microsoft Analysis Services client libraries](https://learn.microsoft.com/en-us/analysis-services/client-libraries?view=sql-analysis-services-2025)
- [Official ADOMD.NET NuGet package](https://www.nuget.org/packages/Microsoft.AnalysisServices.AdomdClient/19.117.0)
- [ADOMD reader/resource usage](https://learn.microsoft.com/en-us/analysis-services/adomd/multidimensional-models-adomd-net-client/retrieving-data-using-the-adomddatareader?view=sql-analysis-services-2025)
- [TMSCHEMA_COLUMNS explicit/inferred fields](https://learn.microsoft.com/en-us/openspecs/sql_server_protocols/ms-ssas-t/1e4a1f57-367a-45e1-b982-4685fb3bafba) and [TOM type codes](https://learn.microsoft.com/en-us/dotnet/api/microsoft.analysisservices.tabular.datatype?view=analysisservices-dotnet)
- [INFO.CALCDEPENDENCY requirements](https://learn.microsoft.com/en-us/dax/info-calcdependency-function-dax)

MIT licensed; see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
