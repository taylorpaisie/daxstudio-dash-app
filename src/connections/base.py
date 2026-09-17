from dataclasses import dataclass
from typing import Protocol

import pandas as pd


class StudioError(Exception):
    """An actionable error safe to show in the local interface."""


@dataclass(frozen=True)
class ConnectionSpec:
    server: str
    catalog: str = ""


@dataclass
class QueryResult:
    frame: pd.DataFrame
    truncated: bool = False
    duration: float = 0.0


class ConnectionProvider(Protocol):
    """Stateless adapter contract. Each operation owns and closes its connection."""

    def catalogs(self, spec: ConnectionSpec) -> list[str]: ...

    def execute(
        self, spec: ConnectionSpec, query: str, limit: int, timeout: int
    ) -> QueryResult: ...
