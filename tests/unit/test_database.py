from pathlib import Path

import memory.database as db
from actions.database import execute_database_query


def test_database_path_is_inside_data_directory():
    assert db.DATABASE_FILE == db.BASE_DIR / "data" / "victor.db"


def test_initialize_database_creates_expected_schema(tmp_path, monkeypatch):
    database_file = tmp_path / "data" / "victor.db"
    schema_file = Path(db.SCHEMA_FILE)

    monkeypatch.setattr(db, "DATABASE_FILE", database_file)
    monkeypatch.setattr(db, "DATA_DIR", database_file.parent)

    db.initialize_database()

    with db.get_connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert tables >= {
        "schema_version",
        "users",
        "memories",
        "facts",
        "conversations",
        "messages",
    }
    assert database_file.exists()
    assert schema_file.exists()


def test_transaction_commits_changes(tmp_path, monkeypatch):
    database_file = tmp_path / "victor.db"
    monkeypatch.setattr(db, "DATABASE_FILE", database_file)
    monkeypatch.setattr(db, "DATA_DIR", database_file.parent)
    db.initialize_database()

    with db.transaction() as connection:
        connection.execute(
            """
            INSERT INTO users(external_key, display_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            ("transaction-test", "VICTOR istifadəçisi", db.utc_now(), db.utc_now()),
        )

    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT external_key, display_name FROM users WHERE external_key = ?",
            ("transaction-test",),
        ).fetchone()

    assert row["external_key"] == "transaction-test"
    assert row["display_name"] == "VICTOR istifadəçisi"


def test_transaction_rolls_back_on_error(tmp_path, monkeypatch):
    database_file = tmp_path / "victor.db"
    monkeypatch.setattr(db, "DATABASE_FILE", database_file)
    monkeypatch.setattr(db, "DATA_DIR", database_file.parent)
    db.initialize_database()

    try:
        with db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO users(external_key, display_name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                ("rollback-test", "Test", db.utc_now(), db.utc_now()),
            )
            raise RuntimeError("rollback")
    except RuntimeError:
        pass

    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM users WHERE external_key = ?",
            ("rollback-test",),
        ).fetchone()

    assert row is None


def test_execute_database_query_select(tmp_path, monkeypatch):
    database_file = tmp_path / "victor.db"
    monkeypatch.setattr(db, "DATABASE_FILE", database_file)
    monkeypatch.setattr(db, "DATA_DIR", database_file.parent)
    db.initialize_database()

    result = execute_database_query(
        """
        SELECT external_key, display_name
        FROM users
        WHERE external_key = 'missing'
        """
    )

    assert result["type"] == "database"
    assert result["status"] == "success"
    assert result["data"] == []
    assert result["meta"]["statement"] == "SELECT"


def test_execute_database_query_insert(tmp_path, monkeypatch):
    database_file = tmp_path / "victor.db"
    monkeypatch.setattr(db, "DATABASE_FILE", database_file)
    monkeypatch.setattr(db, "DATA_DIR", database_file.parent)
    db.initialize_database()

    result = execute_database_query(
        """
        INSERT INTO users(external_key, display_name, created_at, updated_at)
        VALUES ('database-tool-test', 'Test', '2026-09-18T00:00:00+00:00', '2026-09-18T00:00:00+00:00')
        """
    )

    assert result["status"] == "success"
    assert result["meta"]["statement"] == "INSERT"

    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT display_name FROM users WHERE external_key = ?",
            ("database-tool-test",),
        ).fetchone()

    assert row["display_name"] == "Test"


def test_execute_database_query_rejects_unsupported_statement(tmp_path, monkeypatch):
    database_file = tmp_path / "victor.db"
    monkeypatch.setattr(db, "DATABASE_FILE", database_file)
    monkeypatch.setattr(db, "DATA_DIR", database_file.parent)
    db.initialize_database()

    import pytest

    with pytest.raises(ValueError, match="Yalnız SELECT"):
        execute_database_query("DROP TABLE users")


def test_execute_database_query_rejects_multiple_statements(tmp_path, monkeypatch):
    database_file = tmp_path / "victor.db"
    monkeypatch.setattr(db, "DATABASE_FILE", database_file)
    monkeypatch.setattr(db, "DATA_DIR", database_file.parent)
    db.initialize_database()

    import pytest

    with pytest.raises(ValueError, match="yalnız bir SQL statement"):
        execute_database_query("SELECT 1; SELECT 2")


def test_execute_database_query_rejects_sqlite_system_tables(tmp_path, monkeypatch):
    database_file = tmp_path / "victor.db"
    monkeypatch.setattr(db, "DATABASE_FILE", database_file)
    monkeypatch.setattr(db, "DATA_DIR", database_file.parent)
    db.initialize_database()

    import pytest

    with pytest.raises(ValueError, match="sistem cədvəllərinə"):
        execute_database_query("SELECT name FROM sqlite_master")
