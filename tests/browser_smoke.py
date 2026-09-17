"""Explicit browser smoke test using installed Chrome's DevTools protocol.

Run: python -m tests.browser_smoke
The fake model is injected only here, and is labelled TEST MODEL in the browser.
Screenshots contain only synthetic data. No live model query is executed.
"""

import base64
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

import requests
import websocket
from werkzeug.serving import make_server

from app import create_app
from tests.fakes import FakeProvider


class Browser:
    def __init__(self, port):
        endpoint = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                pages = requests.get(endpoint + "/json", timeout=1).json()
                page = next(item for item in pages if item["type"] == "page")
                self.socket = websocket.create_connection(page["webSocketDebuggerUrl"],
                                                          suppress_origin=True, timeout=10)
                break
            except (requests.RequestException, StopIteration):
                time.sleep(0.1)
        else:
            raise RuntimeError("Chrome DevTools did not start")
        self.counter = 0
        self.errors = []
        self.call("Runtime.enable")
        self.call("Page.enable")
        self.call("Log.enable")
        self.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000,
                                                        "deviceScaleFactor": 1, "mobile": False})

    def call(self, method, params=None):
        self.counter += 1
        self.socket.send(json.dumps({"id": self.counter, "method": method, "params": params or {}}))
        while True:
            result = json.loads(self.socket.recv())
            if result.get("method") == "Runtime.exceptionThrown":
                self.errors.append(result)
            if result.get("id") == self.counter:
                assert "error" not in result, result
                return result.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression,
                                               "returnByValue": True, "awaitPromise": True})
        assert "exceptionDetails" not in result, result
        return result.get("result", {}).get("value")

    def wait(self, expression, timeout=15):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if self.evaluate(f"Boolean({expression})"):
                return
            time.sleep(0.1)
        raise AssertionError(f"Browser timed out: {expression}")

    def click(self, identifier):
        self.evaluate(f"document.getElementById({json.dumps(identifier)}).click()")

    def set_props(self, identifier, props):
        self.evaluate(f"window.dash_clientside.set_props({json.dumps(identifier)}, {json.dumps(props)})")
        time.sleep(0.15)

    def screenshot(self, name):
        result = self.call("Page.captureScreenshot", {"captureBeyondViewport": False})
        Path("test-results", name).write_bytes(base64.b64decode(result["data"]))


def main():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    Path("test-results").mkdir(exist_ok=True)
    chrome = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
    if not chrome.exists():
        chrome = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    process = subprocess.Popen([
        str(chrome), "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--remote-debugging-port=9227",
        f"--user-data-dir={Path('test-results/browser-profile').resolve()}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    servers = []
    try:
        for port, provider in [(8051, None), (8052, FakeProvider())]:
            server = make_server("127.0.0.1", port, create_app(provider).server, threaded=True)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            servers.append(server)
        browser = Browser(9227)
        browser.call("Page.navigate", {"url": "http://127.0.0.1:8051"})
        browser.wait("document.getElementById('editor') && document.querySelector('.ag-root')")
        browser.wait("document.getElementById('hydrated') === null && document.getElementById('model-tree').textContent.includes('No model')")
        browser.screenshot("startup-dark.png")
        browser.click("run-query")
        browser.wait("document.getElementById('query-status').textContent.includes('Connect to a model')")
        browser.set_props("server", {"value": "localhost:1"})
        browser.click("connect")
        browser.wait("document.getElementById('connection-message').textContent.includes('Failed')")
        browser.set_props("theme", {"value": True})
        browser.wait("document.getElementById('app-shell').dataset.theme === 'light'")
        browser.screenshot("startup-light.png")

        browser.call("Page.navigate", {"url": "http://127.0.0.1:8052"})
        browser.wait("document.getElementById('editor') && document.querySelector('.ag-root')")
        browser.set_props("server", {"value": "localhost:1234"})
        browser.click("connect")
        browser.wait("document.getElementById('connection-badge').textContent.includes('TEST MODEL')")
        browser.wait("document.getElementById('model-tree').textContent.includes('Test Sales')")
        browser.click("expand-model")
        browser.wait("document.querySelector('#model-tree details').open")
        browser.click("run-query")
        browser.wait("document.getElementById('query-status').textContent.includes('Success')")
        browser.wait("document.querySelector('#query-grid .ag-row')")
        browser.screenshot("query-test-data.png")
        browser.set_props("tabs", {"active_tab": "dependencies"})
        browser.click("load-dependencies")
        browser.wait("document.getElementById('dependency-status').textContent.includes('Success')")
        browser.wait("document.querySelector('#dependency-grid .ag-cell')")
        browser.evaluate("document.querySelector('#dependency-grid .ag-cell').click()")
        browser.wait("document.getElementById('editor').value.includes('[TABLE]')")
        browser.wait("document.getElementById('query-pane').style.display === 'block'")
        browser.set_props("tabs", {"active_tab": "history"})
        browser.wait("document.querySelector('#history-grid .ag-cell')")
        browser.evaluate("document.querySelector('#history-grid .ag-cell').click()")
        browser.wait("document.getElementById('editor').value.includes('TOPN(')")
        browser.set_props("editor", {"value": "EVALUATE EMPTY"})
        browser.click("run-query")
        browser.wait("document.getElementById('query-status').textContent.includes('zero rows')")
        browser.set_props("editor", {"value": "EVALUATE BROKEN"})
        browser.click("run-query")
        browser.wait("document.getElementById('query-status').textContent.includes('Synthetic query error')")
        browser.click("clear-query")
        browser.wait("document.getElementById('editor').value === ''")
        browser.evaluate("document.querySelector('#model-tree .object-button').click()")
        browser.wait("document.getElementById('editor').value === \"'Test Sales'\"")
        browser.click("disconnect")
        browser.wait("document.getElementById('connection-badge').textContent === 'Disconnected'")
        assert not browser.errors, browser.errors
        print("PASS: real-adapter startup/error; dark/light themes; fake-model connection, metadata, "
              "queries, dependency and history row clicks, empty/error states, insertion, disconnect.")
        browser.socket.close()
    finally:
        for server in servers:
            server.shutdown()
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    main()
