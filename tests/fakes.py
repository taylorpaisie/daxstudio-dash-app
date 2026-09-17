"""EXPLICIT TEST FAKE. These rows are synthetic and are never used by app.py."""

import pandas as pd

from src.connections.base import QueryResult, StudioError


class FakeProvider:
    def __init__(self):
        self.fail = False
        self.queries = []

    def catalogs(self, spec):
        if self.fail:
            raise StudioError("Synthetic connection failure")
        return ["TEST MODEL"]

    def execute(self, spec, query, limit, timeout):
        self.queries.append(query)
        if self.fail or "BROKEN" in query:
            raise StudioError("Synthetic query error")
        if "TMSCHEMA_TABLES" in query:
            frame = pd.DataFrame([{"ID": 1, "Name": "Test Sales", "IsHidden": False}])
        elif "TMSCHEMA_COLUMNS" in query:
            frame = pd.DataFrame(
                [
                    {
                        "TableID": 1,
                        "ExplicitName": "Amount",
                        "InferredName": None,
                        "ExplicitDataType": 8,
                        "InferredDataType": None,
                        "IsHidden": False,
                    }
                ],
                dtype=object,
            )
        elif "TMSCHEMA_MEASURES" in query:
            frame = pd.DataFrame(
                [
                    {
                        "TableID": 1,
                        "Name": "Total",
                        "DataType": 8,
                        "IsHidden": False,
                    }
                ]
            )
        elif "INFO.CALCDEPENDENCY" in query:
            frame = pd.DataFrame(
                [
                    {
                        "[OBJECT_TYPE]": "MEASURE",
                        "[TABLE]": "Test Sales",
                        "[OBJECT]": "Total",
                        "[REFERENCED_OBJECT_TYPE]": "COLUMN",
                        "[REFERENCED_TABLE]": "Test Sales",
                        "[REFERENCED_OBJECT]": "Amount",
                    }
                ]
            )
        elif "EMPTY" in query:
            frame = pd.DataFrame(columns=["Value"])
        else:
            frame = pd.DataFrame({"Value": [1, 2], "Blank": [None, None]})
        return QueryResult(frame.head(limit), len(frame) > limit, 0.01)


class FakeReader:
    def __init__(self, names, rows, error=False):
        self.names, self.rows, self.error = names, rows, error
        self.FieldCount = len(names)
        self.index = -1
        self.closed = False

    def GetName(self, i):
        return self.names[i]

    def Read(self):
        if self.error:
            raise RuntimeError("Synthetic read failure")
        self.index += 1
        return self.index < len(self.rows)

    def IsDBNull(self, i):
        return self.rows[self.index][i] is None

    def GetValue(self, i):
        return self.rows[self.index][i]

    def Close(self):
        self.closed = True


class FakeCommand:
    def __init__(self, reader):
        self.reader = reader
        self.disposed = False

    def ExecuteReader(self):
        return self.reader

    def Dispose(self):
        self.disposed = True


class FakeConnection:
    def __init__(self, reader, fail=False):
        self.command = FakeCommand(reader)
        self.fail, self.closed, self.disposed = fail, False, False

    def Open(self):
        if self.fail:
            raise RuntimeError("Secret in underlying error")

    def CreateCommand(self):
        return self.command

    def Close(self):
        self.closed = True

    def Dispose(self):
        self.disposed = True
