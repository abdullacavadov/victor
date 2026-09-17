"""VICTOR üçün təhlükəsiz, ümumi SQLite sorğu qatı."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from memory import database


_ALLOWED = {"SELECT", "INSERT", "UPDATE", "DELETE"}
_WRITE_TABLE_RE = re.compile(r"\b(?:INTO|UPDATE|FROM)\s+([\"'`]?)([A-Za-z_][A-Za-z0-9_]*)\1", re.IGNORECASE)


def _statement_type(sql: str) -> str:
    match = re.match(r"^\s*([A-Za-z]+)", sql or "")
    return match.group(1).upper() if match else ""


def _validate_sql(sql: str) -> tuple[bool, str, str]:
    text = str(sql or "").strip()
    if not text:
        return False, "SQL sorğusu boş ola bilməz.", ""
    if text.count(";") > 1 or (";" in text and not text.rstrip().endswith(";")):
        return False, "Yalnız bir SQL statement icazəlidir.", ""
    statement = _statement_type(text)
    if statement not in _ALLOWED:
        return False, "Yalnız SELECT, INSERT, UPDATE və DELETE sorğularına icazə verilir.", statement
    if "sqlite_" in text.casefold():
        return False, "SQLite sistem cədvəllərinə birbaşa dəyişiklik və ya çıxış qadağandır.", statement
    return True, "", statement


def _tables_exist(connection: sqlite3.Connection, sql: str) -> tuple[bool, str]:
    tables = {match.group(2) for match in _WRITE_TABLE_RE.finditer(sql)}
    if not tables:
        return True, ""
    for table in tables:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
            (table,),
        ).fetchone()
        if row is None:
            return False, f"Cədvəl tapılmadı: {table}"
    return True, ""


def execute_database_query(sql: str) -> dict[str, Any]:
    """VICTOR-un SQLite bazasında bir statement icra edir.

    Təsdiq mexanizmi ToolExecutor səviyyəsində UPDATE/DELETE üçün tətbiq olunur.
    Bu qat isə yalnız icazəli SQL statement növlərini və mövcud cədvəlləri qəbul edir.
    """
    valid, error, statement = _validate_sql(sql)
    if not valid:
        return {"type": "database", "status": "error", "data": [], "count": 0, "meta": {"message": error}}

    database.initialize_database()
    connection = database.get_connection()
    try:
        tables_ok, table_error = _tables_exist(connection, sql)
        if not tables_ok:
            return {"type": "database", "status": "error", "data": [], "count": 0, "meta": {"message": table_error}}

        cursor = connection.execute(sql)
        if statement == "SELECT":
            rows = [dict(row) for row in cursor.fetchmany(100)]
            return {
                "type": "database",
                "status": "success" if rows else "empty",
                "data": rows,
                "count": len(rows),
                "meta": {"statement": statement, "source": "python_sqlite_repository"},
            }

        connection.commit()
        count = max(0, int(cursor.rowcount or 0))
        return {
            "type": "database",
            "status": "success",
            "data": [],
            "count": count,
            "meta": {
                "statement": statement,
                "affected_rows": count,
                "last_insert_id": cursor.lastrowid if statement == "INSERT" else None,
                "source": "python_sqlite_repository",
            },
        }
    except sqlite3.Error as exc:
        connection.rollback()
        return {"type": "database", "status": "error", "data": [], "count": 0, "meta": {"message": str(exc)}}
    finally:
        connection.close()
