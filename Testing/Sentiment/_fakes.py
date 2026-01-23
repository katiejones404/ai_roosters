from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class FakeExecuteResult:
    rowcount: int = 0


class FakeFetchResult:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def fetchall(self) -> List[Dict[str, Any]]:
        return list(self._rows)


class FakeDB:
    """A minimal DB/session test double for sentiment endpoints."""

    def __init__(self):
        self.snapshots: List[Dict[str, Any]] = []
        self._delete_rowcount: int = 0
        self._committed: bool = False

    def seed_snapshots(self, rows: Iterable[Dict[str, Any]]) -> None:
        self.snapshots = list(rows)

    def seed_delete_rowcount(self, rowcount: int) -> None:
        self._delete_rowcount = int(rowcount)

    def execute(self, query: Any, params: Optional[Dict[str, Any]] = None):
        sql = str(query)
        params = params or {}

        if "DELETE FROM sentiment_snapshots" in sql:
            return FakeExecuteResult(rowcount=self._delete_rowcount)

        # SELECT DISTINCT ON ... FROM sentiment_snapshots
        if "FROM sentiment_snapshots" in sql and "SELECT" in sql:
            rows = list(self.snapshots)
            if "ticker" in params:
                # param is like %RELIANCE%
                needle = str(params["ticker"]).strip("%")
                rows = [r for r in rows if needle.lower() in str(r.get("ticker", "")).lower()]
            return FakeFetchResult(rows)

        return FakeFetchResult([])

    def commit(self) -> None:
        self._committed = True
