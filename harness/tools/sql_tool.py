from __future__ import annotations

import sqlite3
from typing import Any, Dict, List
from .base import BaseTool


class SqlExecutionTool(BaseTool):
    name = "execute_sql"
    description = "Executes a read-only SQL query against the database and returns rows as structured dictionaries."
    read_only = True

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def get_connection(self) -> sqlite3.Connection:
        return self._conn

    def run(self, query: str) -> List[Dict[str, Any]]:
        clean_query = query.strip()
        # Security guard: Enforce read-only constraint
        forbidden_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "GRANT", "REVOKE"]
        upper_query = clean_query.upper()
        for kw in forbidden_keywords:
            if kw in upper_query.split():
                raise PermissionError(f"Security Invariant Violated: Destructive operation '{kw}' is prohibited.")

        cursor = self._conn.cursor()
        cursor.execute(clean_query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
