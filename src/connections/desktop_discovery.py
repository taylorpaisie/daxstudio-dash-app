"""Best-effort local discovery; stale/inaccessible workspaces are skipped."""

import os
import re
import socket
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


def workspace_roots(local_app_data: Path | None = None) -> list[Path]:
    local = local_app_data or Path(os.environ.get("LOCALAPPDATA", ""))
    roots = [
        local / "Microsoft/Power BI Desktop/AnalysisServicesWorkspaces",
        local / "Microsoft/Power BI Desktop Store App/AnalysisServicesWorkspaces",
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
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if (proc.info["name"] or "").lower() in {"msmdsrv.exe", "pbidesktop.exe"}:
                result.append(proc.info)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return result


def discover_instances(roots=None, probe=None, processes=None) -> list[DesktopInstance]:
    roots = workspace_roots() if roots is None else roots
    probe = _listening if probe is None else probe
    processes = _processes() if processes is None else processes
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
                pid = next(
                    (
                        p["pid"]
                        for p in processes
                        if workspace.lower() in " ".join(p.get("cmdline") or []).lower()
                    ),
                    None,
                )
                # Report titles are not reliably stored in workspace files; catalog
                # names are obtained through DBSCHEMA_CATALOGS after connecting.
                found[port] = DesktopInstance(f"localhost:{port}", workspace, pid=pid)
            except (OSError, UnicodeError, ValueError):
                continue
    return sorted(found.values(), key=lambda item: item.server)
