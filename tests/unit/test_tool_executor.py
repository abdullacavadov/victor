import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.tool_executor import ToolExecutor


def make_executor():
    ui = MagicMock()
    ui.muted = False
    webcam = MagicMock()
    focus = MagicMock()
    speak_error = MagicMock()
    executor = ToolExecutor(ui, webcam, focus, speak_error)
    return executor, ui, webcam, focus, speak_error


def test_result_looks_like_error():
    assert ToolExecutor.result_looks_like_error("Xəta: bağlantı alınmadı") is True
    assert ToolExecutor.result_looks_like_error("Əməliyyat uğurla tamamlandı") is False


def test_success_sfx_for_calendar_action():
    assert ToolExecutor.should_play_success_sfx(
        "add_calendar_event", {}, "Tədbir əlavə edildi."
    ) is True


def test_success_sfx_for_whatsapp_send():
    assert ToolExecutor.should_play_success_sfx(
        "send_whatsapp_message",
        {"send_now": True},
        "Mesaj göndərildi.",
    ) is True


def test_memory_tools_do_not_play_success_sfx():
    assert ToolExecutor.should_play_success_sfx("save_memory", {}, "ok") is False
    assert ToolExecutor.should_play_success_sfx(
        "delete_memory", {}, "profile/name hafizadan kaldirildi."
    ) is False


def test_unknown_tool_returns_function_response():
    executor, ui, *_ = make_executor()
    fc = SimpleNamespace(id="call-1", name="unknown_tool", args={})

    response = asyncio.run(executor.execute(fc))

    assert response.id == "call-1"
    assert response.name == "unknown_tool"
    assert response.response["result"] == "Naməlum alət: unknown_tool"
    ui.set_state.assert_any_call("THINKING")


@patch("core.tool_executor.open_app", return_value="Notepad açıldı.")
def test_open_app_is_dispatched_to_action(mock_open_app):
    executor, ui, *_ = make_executor()
    fc = SimpleNamespace(
        id="call-2",
        name="open_app",
        args={"app_name": "notepad"},
    )

    response = asyncio.run(executor.execute(fc))

    assert response.response["result"] == "Notepad açıldı."
    mock_open_app.assert_called_once_with("notepad")
    ui.play_success_sfx.assert_called_once()


def test_action_exception_is_converted_to_generic_error_response():
    executor, ui, _, _, speak_error = make_executor()
    fc = SimpleNamespace(id="call-3", name="open_app", args={"app_name": "notepad"})

    with patch("core.tool_executor.open_app", side_effect=RuntimeError("secret local path")):
        response = asyncio.run(executor.execute(fc))

    assert response.response["result"] == "Xəta: alət icra edilərkən daxili xəta baş verdi."
    assert "secret local path" not in response.response["result"]
    speak_error.assert_called_once_with(
        "open_app", "Alət icra edilərkən daxili xəta baş verdi."
    )
    ui.set_state.assert_any_call("ERROR")


@patch("core.tool_executor.update_memory")
def test_save_memory_dispatches_expected_payload(mock_update_memory):
    executor, *_ = make_executor()
    fc = SimpleNamespace(
        id="memory-save-1",
        name="save_memory",
        args={"category": "profile", "key": "name", "value": "Abdulla"},
    )

    response = asyncio.run(executor.execute(fc))

    mock_update_memory.assert_called_once_with(
        {"profile": {"name": {"value": "Abdulla"}}}
    )
    assert response.id == "memory-save-1"
    assert response.name == "save_memory"
    assert response.response["result"] == "ok"


@patch("core.tool_executor.update_memory")
def test_save_memory_invalid_arguments_must_not_report_success(mock_update_memory):
    executor, *_ = make_executor()
    fc = SimpleNamespace(
        id="memory-save-2",
        name="save_memory",
        args={"category": "profile", "key": "", "value": "Abdulla"},
    )

    response = asyncio.run(executor.execute(fc))

    mock_update_memory.assert_not_called()
    assert response.response["result"] != "ok"


@patch("core.tool_executor.update_memory", side_effect=RuntimeError("disk error"))
def test_save_memory_exception_is_converted_to_generic_error_response(mock_update_memory):
    executor, ui, _, _, speak_error = make_executor()
    fc = SimpleNamespace(
        id="memory-save-3",
        name="save_memory",
        args={"category": "profile", "key": "name", "value": "Abdulla"},
    )

    response = asyncio.run(executor.execute(fc))

    assert response.response["result"] == "Xəta: alət icra edilərkən daxili xəta baş verdi."
    mock_update_memory.assert_called_once()
    speak_error.assert_called_once_with(
        "save_memory", "Alət icra edilərkən daxili xəta baş verdi."
    )
    ui.set_state.assert_any_call("ERROR")


@patch("core.tool_executor.delete_memory")
def test_delete_memory_requires_confirmation(mock_delete_memory):
    executor, *_ = make_executor()
    fc = SimpleNamespace(
        id="memory-delete-1",
        name="delete_memory",
        args={
            "category": "profile",
            "key": "name",
            "match_text": "",
        },
    )

    response = asyncio.run(executor.execute(fc))

    mock_delete_memory.assert_not_called()
    assert response.response["result"]["status"] == "needs_confirmation"
    assert response.response["result"]["meta"]["requires_confirmation"] is True
    assert response.response["result"]["meta"]["confirmation_action"] == "delete_memory"


@patch("core.tool_executor.delete_memory", return_value="profile/name hafizadan kaldirildi.")
def test_delete_memory_executes_after_confirmation(mock_delete_memory):
    executor, *_ = make_executor()
    first_fc = SimpleNamespace(
        id="memory-delete-2a",
        name="delete_memory",
        args={"category": "profile", "key": "name", "match_text": ""},
    )

    first_response = asyncio.run(executor.execute(first_fc))
    token = first_response.response["result"]["meta"]["confirmation_id"]

    confirm_fc = SimpleNamespace(
        id="memory-delete-2b",
        name="confirm_action",
        args={"confirmation_id": token},
    )
    response = asyncio.run(executor.execute(confirm_fc))

    mock_delete_memory.assert_called_once_with("profile", "name", "")
    assert response.response["result"] == "profile/name hafizadan kaldirildi."


@patch("core.tool_executor.delete_memory")
def test_delete_memory_confirmation_preserves_payload(mock_delete_memory):
    executor, *_ = make_executor()
    fc = SimpleNamespace(
        id="memory-delete-3",
        name="delete_memory",
        args={"category": "profile", "key": "missing", "match_text": "claude ai limit"},
    )

    response = asyncio.run(executor.execute(fc))
    token = response.response["result"]["meta"]["confirmation_id"]

    confirm_fc = SimpleNamespace(
        id="memory-delete-3-confirm",
        name="confirm_action",
        args={"confirmation_id": token},
    )
    asyncio.run(executor.execute(confirm_fc))

    mock_delete_memory.assert_called_once_with("profile", "missing", "claude ai limit")


@patch("core.tool_executor.add_reminder", return_value="Google Tasks-a 'Test' reminder-i əlavə edildi.")
def test_add_reminder_is_dispatched_to_action(mock_add_reminder):
    executor, *_ = make_executor()
    fc = SimpleNamespace(
        id="reminder-add-1",
        name="add_reminder",
        args={
            "title": "Test",
            "due_iso": "2026-08-20T10:00:00+04:00",
            "notes": "Note",
            "list_name": "Work",
            "priority": "",
            "all_day": False,
        },
    )

    response = asyncio.run(executor.execute(fc))

    mock_add_reminder.assert_called_once_with(
        "Test",
        "2026-08-20T10:00:00+04:00",
        "Note",
        "Work",
        "",
        False,
    )
    assert "əlavə edildi" in response.response["result"]
    executor.ui.play_success_sfx.assert_called_once()

@patch("core.tool_executor.execute_database_query", return_value={
    "type": "database",
    "status": "success",
    "data": [{"id": 1, "display_name": "Test"}],
    "count": 1,
    "meta": {"statement": "SELECT"},
})
def test_database_query_select_is_dispatched(mock_query):
    executor, *_ = make_executor()

    fc = SimpleNamespace(
        id="database-select-1",
        name="database_query",
        args={"sql": "SELECT id, display_name FROM users"},
    )

    response = asyncio.run(executor.execute(fc))

    mock_query.assert_called_once_with("SELECT id, display_name FROM users")
    assert response.response["result"]["status"] == "success"


@patch("core.tool_executor.execute_database_query", return_value={
    "type": "database",
    "status": "success",
    "data": [],
    "count": 1,
    "meta": {"statement": "INSERT", "last_insert_id": 10},
})
def test_database_query_insert_is_dispatched(mock_query):
    executor, *_ = make_executor()

    fc = SimpleNamespace(
        id="database-insert-1",
        name="database_query",
        args={
            "sql": (
                "INSERT INTO users(external_key, display_name, created_at, updated_at) "
                "VALUES ('test', 'Test', 'now', 'now')"
            )
        },
    )

    response = asyncio.run(executor.execute(fc))

    mock_query.assert_called_once()
    assert response.response["result"]["status"] == "success"


@patch("core.tool_executor.execute_database_query")
def test_database_query_update_requires_confirmation(mock_query):
    executor, *_ = make_executor()

    fc = SimpleNamespace(
        id="database-update-1",
        name="database_query",
        args={"sql": "UPDATE users SET display_name = 'Changed' WHERE id = 1"},
    )

    response = asyncio.run(executor.execute(fc))

    mock_query.assert_not_called()
    assert response.response["result"]["status"] == "needs_confirmation"
    assert response.response["result"]["meta"]["requires_confirmation"] is True
    assert response.response["result"]["meta"]["confirmation_action"] == "database_query"


@patch("core.tool_executor.execute_database_query", return_value={
    "type": "database",
    "status": "success",
    "data": [],
    "count": 1,
    "meta": {"statement": "UPDATE"},
})
def test_database_query_update_executes_after_confirmation(mock_query):
    executor, *_ = make_executor()

    first_fc = SimpleNamespace(
        id="database-update-2a",
        name="database_query",
        args={"sql": "UPDATE users SET display_name = 'Changed' WHERE id = 1"},
    )

    first_response = asyncio.run(executor.execute(first_fc))
    token = first_response.response["result"]["meta"]["confirmation_id"]

    confirm_fc = SimpleNamespace(
        id="database-update-2b",
        name="confirm_action",
        args={"confirmation_id": token},
    )

    response = asyncio.run(executor.execute(confirm_fc))

    mock_query.assert_called_once_with(
        "UPDATE users SET display_name = 'Changed' WHERE id = 1"
    )
    assert response.response["result"]["status"] == "success"


@patch("core.tool_executor.execute_database_query")
def test_database_query_delete_requires_confirmation(mock_query):
    executor, *_ = make_executor()

    fc = SimpleNamespace(
        id="database-delete-1",
        name="database_query",
        args={"sql": "DELETE FROM users WHERE id = 1"},
    )

    response = asyncio.run(executor.execute(fc))

    mock_query.assert_not_called()
    assert response.response["result"]["status"] == "needs_confirmation"
    assert response.response["result"]["meta"]["requires_confirmation"] is True
    assert response.response["result"]["meta"]["confirmation_action"] == "database_query"


@patch("core.tool_executor.get_database_schema", return_value={
    "type": "database_schema",
    "status": "success",
    "data": [{"table": "contacts", "columns": [{"name": "id"}], "foreign_keys": []}],
    "count": 1,
    "meta": {"tables": 1},
})
def test_database_schema_is_dispatched(mock_schema):
    executor, *_ = make_executor()

    fc = SimpleNamespace(
        id="database-schema-1",
        name="database_schema",
        args={},
    )

    response = asyncio.run(executor.execute(fc))

    mock_schema.assert_called_once_with()
    assert response.response["result"]["type"] == "database_schema"
    assert response.response["result"]["status"] == "success"
