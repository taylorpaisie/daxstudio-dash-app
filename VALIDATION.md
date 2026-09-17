# MVP validation — 2026-09-17

## Completed

- Inspected the workspace before implementation: it was empty and not an initialized Git repository. No pre-existing project files were overwritten.
- Installed dependencies in a project-local Python **3.11** virtual environment. Runtime package versions are pinned in `requirements.txt`.
- `python -m black --check app.py src tests`: passed (26 files).
- `python -m flake8 app.py src tests --jobs 1`: passed, no findings.
- `python -m pytest -q`: **46 passed**.
- `python -m pip check`: no broken requirements.
- `python -m tests.browser_smoke`: passed with installed Chrome in headless mode. Checked for browser JavaScript exceptions and console errors.
- Visually inspected captured dark/light layouts and populated grids using explicitly labelled synthetic test data. Fixed AG Grid v35 theme integration and Dash v4 dropdown styling.
- Launched the actual `python app.py` Waitress entry point. `/`, `/_dash-layout`, `/_dash-dependencies` and application CSS returned HTTP 200. Windows TCP inspection confirmed the listener was **127.0.0.1:8050**, not a public interface.

The browser smoke exercised real-adapter disconnected startup and missing-client errors, then an explicitly injected `FakeProvider` on a separate test server for connection, metadata expansion, query execution, Ctrl+Enter, grid sorting/filtering, dependency-row query generation, history restoration, zero-row/error states, identifier insertion and disconnect. CSV and XLSX payloads were verified through real Dash callback requests; XLSX was reopened with openpyxl.

Unit/integration coverage includes mocked discovery paths/encodings/process arguments, stale and invalid ports, connection-string escaping and loopback validation, DAX identifier escaping/read-only guards, ADOMD reader conversion, duplicate column names, nulls, empty results, large integers/decimals/dates, row/byte bounds, resource closure on success and failures, dependency filtering, metadata joins, bounded history, session isolation, Host/Origin guards and failed-target-switch cleanup.

Screenshots are under ignored `test-results/` and contain only disconnected UI or synthetic data. No real model data, credentials or tokens were used. Runtime code never imports the test fake.

## Environment limitations

- No running `PBIDesktop.exe` or `msmdsrv.exe` was present during inspection. No live PBIX query was executed.
- The Microsoft ADOMD.NET client was not installed. Missing-client behavior was verified; the real adapter's connection/command/reader interfaces were tested with explicit mocks.
- `dotnet build tools/adomd-client/Client.csproj ...` could not restore the client because **no .NET SDK** was installed. The provided project uses the official current NuGet package and documented target framework; its restore/build still needs execution on a machine with an SDK.
- Managed Windows blocked the Ruff executable and Playwright's bundled Node executable. Black/Flake8 ran successfully instead, and the browser smoke used installed Chrome directly through DevTools. These were executable-startup restrictions, not test failures.
- Python 3.12 was not available for a separate test run.

## Remaining live-model acceptance checks

1. Install/restore the Microsoft client and confirm CLR dependency loading using the README commands.
2. Open a local PBIX and verify discovery for standard and Store Desktop installations; check report-title/process matching and manually entered ports.
3. Connect to a selected catalog and run the supplied connection check and both dependency examples through the real engine.
4. Compare model tables, columns, measures, types and hidden flags against Power BI Desktop.
5. Verify `INFO.CALCDEPENDENCY()` permissions, supported engine versions and model-side filter results.
6. Exercise real engine errors/timeouts, PBIX closure/restart, multi-catalog selection, large/empty results and native scalar conversion.
7. Verify CSV/XLSX exports against real model values, particularly date/time, currency and high-precision numbers.

The app's interface and mocked workflows are working; these checks remain necessary before claiming live Power BI compatibility is verified.
