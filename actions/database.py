"""VICTOR SQLite verilənlər bazası əməliyyatları."""

from __future__ import annotations

import re
from typing import Any

from memory.database import initialize_database, transaction


_ALLOWED_STATEMENTS = {"SELECT", "INSERT", "UPDATE", "DELETE"}
_MAX_SELECT_ROWS = 100


def _statement_type(sql: str) -> str:
    text = str(sql or "").strip()

    # Başdakı SQL şərhlərini nəzərə almadan ilk sözü tapırıq.
    while True:
        if text.startswith("--"):
            newline = text.find("\n")
            if newline == -1:
                return ""
            text = text[newline + 1 :].lstrip()
            continue

        if text.startswith("/*"):
            end = text.find("*/", 2)
            if end == -1:
                return ""
            text = text[end + 2 :].lstrip()
            continue

        break

    match = re.match(r"([A-Za-z]+)", text)
    return match.group(1).upper() if match else ""


def _validate_sql(sql: str) -> str:
    text = str(sql or "").strip()

    if not text:
        raise ValueError("SQL sorğusu boş ola bilməz.")

    statement = _statement_type(text)

    if statement not in _ALLOWED_STATEMENTS:
        raise ValueError(
            "Yalnız SELECT, INSERT, UPDATE və DELETE SQL əməliyyatlarına icazə verilir."
        )

    # sqlite3.execute() onsuz da bir neçə statement-i rədd edir.
    # Burada isə daha aydın xəta qaytarırıq.
    without_trailing_semicolon = text.rstrip().rstrip(";").rstrip()

    if ";" in without_trailing_semicolon:
        raise ValueError("Bir sorğuda yalnız bir SQL statement icra edilə bilər.")

    # Sistem cədvəllərinə birbaşa giriş qadağandır.
    if re.search(
        r"\b(?:sqlite_master|sqlite_schema|sqlite_temp_master|sqlite_temp_schema)\b",
        text,
        re.IGNORECASE,
    ):
        raise ValueError("SQLite sistem cədvəllərinə girişə icazə verilmir.")

    return text


def execute_database_query(sql: str) -> dict[str, Any]:
    """VICTOR-un SQLite bazasında təhlükəsiz tək SQL əməliyyatı icra edir."""

    query = _validate_sql(sql)
    statement = _statement_type(query)

    initialize_database()

    with transaction() as connection:
        cursor = connection.execute(query)

        if statement == "SELECT":
            rows = cursor.fetchmany(_MAX_SELECT_ROWS)
            data = [dict(row) for row in rows]

            return {
                "type": "database",
                "status": "success",
                "data": data,
                "count": len(data),
                "meta": {
                    "statement": "SELECT",
                    "row_limit": _MAX_SELECT_ROWS,
                },
            }

        if statement == "INSERT":
            return {
                "type": "database",
                "status": "success",
                "data": [],
                "count": cursor.rowcount if cursor.rowcount >= 0 else 0,
                "meta": {
                    "statement": "INSERT",
                    "last_insert_id": cursor.lastrowid,
                },
            }

        return {
            "type": "database",
            "status": "success",
            "data": [],
            "count": cursor.rowcount if cursor.rowcount >= 0 else 0,
            "meta": {
                "statement": statement,
            },
        }
