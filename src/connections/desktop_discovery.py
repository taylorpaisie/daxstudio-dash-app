"""Best-effort local discovery; stale/inaccessible workspaces are skipped."""

import os
import re
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import psutil


@dataclass(frozen=True)
class DesktopInstance:
    server: str
    workspace: str
    name: str = "Power BI Desktop"
    pid: int | None = None

    def as_option(self):
        suffix = f" · PID {self.pid}" if self.pid else ""
        return {
            "label": f"{self.name} · {self.server} · {self.workspace}{suffix}",
            "value": self.server,
        }

    def as_dict(self):
        return asdict(self)


def workspace_roots(
    local_app_data: Path | None = None, user_profile: Path | None = None
) -> list[Path]:
    local = local_app_data or Path(os.environ.get("LOCALAPPDATA", ""))
    roots = [
        local / "Microsoft/Power BI Desktop/AnalysisServicesWorkspaces",
        local / "Microsoft/Power BI Desktop Store App/AnalysisServicesWorkspaces",
        (user_profile or Path(os.environ.get("USERPROFILE", "")))
        / "Microsoft/Power BI Desktop Store App/AnalysisServicesWorkspaces",
    ]
    packages = local / "Packages"
    try:
        for package in packages.glob("Microsoft.MicrosoftPowerBIDesktop_*"):
            roots.extend(
                [
                    package / "LocalCache/Microsoft/Power BI Desktop/AnalysisServicesWorkspaces",
                    package
                    / "LocalCache/Microsoft/Power BI Desktop Store App/AnalysisServicesWorkspaces",
                    package / "LocalState/AnalysisServicesWorkspaces",
                ]
            )
    except OSError:
        pass
    return roots


def _listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.15):
            return True
    except OSError:
        return False


def _processes() -> list[dict]:
    result = []
    for proc in psutil.process_iter(["pid", "ppid", "name", "cmdline"]):
        try:
            if (proc.info["name"] or "").lower() in {"msmdsrv.exe", "pbidesktop.exe"}:
                result.append(proc.info)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return result


def _window_titles():
    """Best-effort PBIX title lookup; titles never establish a connection."""
    if sys.platform != "win32":
        return {}
    import ctypes
    from ctypes import wintypes

    titles = {}
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]

    @callback_type
    def visit(window, _):
        length = user32.GetWindowTextLengthW(window)
        if length and user32.IsWindowVisible(window):
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(window, buffer, length + 1)
            if "Power BI Desktop" in buffer.value:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
                titles[pid.value] = buffer.value.removesuffix(" - Power BI Desktop")
        return True

    user32.EnumWindows(visit, 0)
    return titles


def discover_instances(
    roots=None, probe=None, processes=None, titles=None
) -> list[DesktopInstance]:
    roots = workspace_roots() if roots is None else roots
    probe = _listening if probe is None else probe
    processes = _processes() if processes is None else processes
    titles = _window_titles() if titles is None else titles
    # The engine's -s argument can expose a workspace outside the usual directories.
    roots = list(roots)
    for proc in processes:
        args = proc.get("cmdline") or []
        for i, arg in enumerate(args[:-1]):
            if arg.lower() == "-s":
                roots.append(Path(args[i + 1]))
    found = {}
    for root in roots:
        try:
            files = list(Path(root).glob("*/Data/msmdsrv.port.txt"))
            files += list(Path(root).glob("msmdsrv.port.txt"))
            files += list(Path(root).glob("Data/msmdsrv.port.txt"))
        except OSError:
            continue
        for file in files:
            try:
                raw = file.read_bytes()
                encoding = (
                    "utf-16"
                    if raw.startswith((b"\xff\xfe", b"\xfe\xff"))
                    else ("utf-16-le" if b"\x00" in raw else "utf-8-sig")
                )
                value = raw.decode(encoding).strip().strip("\x00")
                if not re.fullmatch(r"\d{1,5}", value):
                    continue
                port = int(value)
                if not 1 <= port <= 65535 or not probe(port):
                    continue
                workspace = file.parent.parent.name
                process = next(
                    (
                        p
                        for p in processes
                        if workspace.lower() in " ".join(p.get("cmdline") or []).lower()
                    ),
                    {},
                )
                name = titles.get(process.get("ppid"), "Power BI Desktop")
                found[port] = DesktopInstance(
                    f"localhost:{port}", workspace, name=name, pid=process.get("pid")
                )
            except (OSError, UnicodeError, ValueError):
                continue
    return sorted(found.values(), key=lambda item: item.server)
