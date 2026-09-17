from actions import shell


def test_sqlite_contact_query_uses_sql_repository(monkeypatch):
    monkeypatch.setattr(
        shell,
        "find_contacts_by_name",
        lambda query: [{"display_name": "Др. Шахруд", "phones": [{"number": "+994501234567"}]}],
    )

    result = shell.shell_run(
        'sqlite3 victor.db "SELECT * FROM contacts WHERE display_name LIKE \'%Др. Шахруд%\'"'
    )

    assert result == "Др. Шахруд — +994501234567"


def test_non_sqlite_command_still_uses_command_runner(monkeypatch):
    monkeypatch.setattr(shell, "run_command", lambda command: f"runner:{command}")

    assert shell.shell_run("hostname") == "runner:hostname"
