import pandas as pd
import pytest

from src.callbacks.workspace import safe_export
from src.components.grids import grid_payload
from src.connections.base import ConnectionSpec, StudioError
from src.models.session import StudioSession
from src.services.dependency_service import (
    dependency_query,
    filter_dependencies,
    query_for_dependency,
)
from src.services.metadata_service import load_metadata
from src.services.query_service import execute_query, run_with_history
from src.utilities.dax import object_identifier, string_literal, table_identifier, validate_query
from tests.fakes import FakeProvider


def test_identifier_escaping():
    assert table_identifier("O'Brien") == "'O''Brien'"
    assert object_identifier("O'Brien", "Total] USD") == "'O''Brien'[Total]] USD]"
    assert string_literal('a"b') == '"a""b"'


@pytest.mark.parametrize(
    "query",
    [
        'EVALUATE ROW("DROP", 1)',
        "-- test\nEVALUATE 'DELETE'",
        "DEFINE MEASURE 'T'[X] = 1 EVALUATE ROW(\"x\", [X])",
    ],
)
def test_read_only_accepts_dax(query):
    assert validate_query(query) == query


@pytest.mark.parametrize(
    "query",
    [
        "",
        "<Execute>evil</Execute>",
        "CREATE TABLE X",
        "SELECT * FROM x",
        "EVALUATE ROW() ALTER CUBE x",
        "DEFINE FUNCTION X = 1 EVALUATE X",
    ],
)
def test_read_only_blocks_commands(query):
    with pytest.raises(StudioError):
        validate_query(query)


def test_metadata_join_and_identifiers():
    result = load_metadata(FakeProvider(), ConnectionSpec("localhost:1234", "TEST MODEL"))
    assert result[0]["name"] == "Test Sales"
    assert result[0]["objects"][1]["identifier"] == "'Test Sales'[Total]"
    assert result[0]["objects"][1]["kind"] == "Measure"


def test_dependency_filters_are_literal_case_insensitive_null_safe():
    frame = pd.DataFrame(
        [
            {
                "[OBJECT_TYPE]": "MEASURE",
                "[OBJECT]": "Total [A]",
                "[REFERENCED_TABLE]": "GFEBS [1]",
                "[REFERENCED_OBJECT_TYPE]": "COLUMN",
            },
            {
                "[OBJECT_TYPE]": "COLUMN",
                "[OBJECT]": "Other",
                "[REFERENCED_TABLE]": None,
                "[REFERENCED_OBJECT_TYPE]": "MEASURE",
            },
        ]
    )
    result = filter_dependencies(frame, "gfebs [1]", "[a]", "measure", "column")
    assert len(result) == 1
    assert filter_dependencies(frame, "missing").empty
    query = dependency_query('x"y', "Total", "MEASURE", "COLUMN")
    assert '"X""Y"' in query and "FILTER(INFO.CALCDEPENDENCY()" in query
    assert query_for_dependency({"TABLE": 'T"X', "OBJECT": "Total"}).count('"T""X"') == 1


def test_query_history_success_failure_and_empty():
    session = StudioSession(spec=ConnectionSpec("localhost:1234", "TEST MODEL"))
    provider = FakeProvider()
    result = run_with_history(provider, session, "EVALUATE EMPTY", 10, 30)
    assert result.frame.empty and session.history[0]["status"] == "Success"
    with pytest.raises(StudioError):
        run_with_history(provider, session, "EVALUATE BROKEN", 10, 30)
    assert session.history[0]["status"] == "Failed"
    assert session.history[0]["error"] == "Synthetic query error"
    for i in range(55):
        run_with_history(provider, session, "EVALUATE ROW()", 10, 30)
    assert len(session.history) == 50


@pytest.mark.parametrize("limit,timeout", [(0, 30), (10001, 30), (1, 121), (None, 10)])
def test_limits(limit, timeout):
    with pytest.raises(StudioError):
        execute_query(
            FakeProvider(), ConnectionSpec("localhost:1234"), "EVALUATE ROW()", limit, timeout
        )


def test_grid_fields_are_safe_and_numbers_preserved():
    frame = pd.DataFrame([[True, 1.2, None]], columns=["[Is.True]", "[Value]", "[Blank]"])
    rows, columns = grid_payload(frame)
    assert rows[0] == {"c0": True, "c1": 1.2, "c2": None}
    assert columns[0]["cellDataType"] == "boolean"
    assert columns[1]["cellDataType"] == "number"


def test_export_formula_safety():
    frame = safe_export(pd.DataFrame({"=header": ["=1+1", "  @evil", "-2", -2, None]}))
    assert frame.columns[0] == "'=header"
    assert frame.iloc[0, 0] == "'=1+1"
    assert frame.iloc[1, 0] == "'  @evil"
    assert frame.iloc[3, 0] == -2
