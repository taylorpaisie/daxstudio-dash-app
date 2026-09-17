from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from src.connections.base import StudioError
from src.utilities.dax import validate_query


def execute_query(provider, spec, query, limit=1000, timeout=30):
    validate_query(query)
    try:
        limit, timeout = int(limit), int(timeout)
    except (ValueError, TypeError):
        raise StudioError("Row limit and timeout must be whole numbers.") from None
    if not 1 <= limit <= 10_000 or not 1 <= timeout <= 120:
        raise StudioError("Use 1–10,000 rows and a timeout of 1–120 seconds.")
    return provider.execute(spec, query, limit, timeout)


def run_with_history(provider, session, query, limit, timeout):
    start = perf_counter()
    entry = {
        "id": str(uuid4()),
        "query": (query or "")[:100_000],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": 0,
        "status": "Failed",
        "error": "",
    }
    try:
        if session.spec is None:
            raise StudioError("Connect to a model before running a query.")
        result = execute_query(provider, session.spec, query, limit, timeout)
        entry.update(rows=len(result.frame), status="Success", truncated=result.truncated)
        return result
    except StudioError as exc:
        entry["error"] = str(exc)[:500]
        raise
    except Exception:
        entry["error"] = "Unexpected query failure. Reconnect and retry."
        raise StudioError(entry["error"]) from None
    finally:
        entry["duration"] = round(perf_counter() - start, 3)
        session.history.insert(0, entry)
        del session.history[50:]
