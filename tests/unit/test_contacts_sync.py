from unittest.mock import MagicMock, patch

import pytest

from actions import contacts
from memory import database
from memory.contacts_repository import list_contacts, upsert_contact


@pytest.fixture
def contact_db(monkeypatch, tmp_path):
    db_path = tmp_path / "victor.db"
    monkeypatch.setattr(database, "DATABASE_FILE", db_path)
    database.initialize_database()
    return db_path


def test_sync_adds_new_google_contact(contact_db, monkeypatch):
    monkeypatch.setattr(contacts, "get_google_contacts", lambda: [{"resource_name": "people/c123", "display_name": "Əhməd", "phones": ["+994501234567"]}])
    result = contacts.sync_google_contacts()
    data = list_contacts()
    assert len(data) == 1
    assert data[0]["display_name"] == "Əhməd"
    assert data[0]["value"] == "+994501234567"
    assert data[0]["google_resource_name"] == "people/c123"
    assert result["data"][0]["new"] == 1
    assert result["data"][0]["removed"] == 0


def test_sync_keeps_unchanged_contact_untouched(contact_db, monkeypatch):
    upsert_contact("Əhməd", ["+994501234567"], "people/c123", source="google")
    before = list_contacts()[0]
    monkeypatch.setattr(contacts, "get_google_contacts", lambda: [{"resource_name": "people/c123", "display_name": "Əhməd", "phones": ["+994501234567"]}])
    contacts.sync_google_contacts()
    after = list_contacts()[0]
    assert after["id"] == before["id"]
    assert after["display_name"] == before["display_name"]
    assert after["phones"] == before["phones"]


def test_sync_updates_changed_name(contact_db, monkeypatch):
    upsert_contact("Əhməd", ["+994501234567"], "people/c123", source="google")
    monkeypatch.setattr(contacts, "get_google_contacts", lambda: [{"resource_name": "people/c123", "display_name": "Əhməd Cavadov", "phones": ["+994501234567"]}])
    contacts.sync_google_contacts()
    assert list_contacts()[0]["display_name"] == "Əhməd Cavadov"


def test_sync_updates_changed_phone(contact_db, monkeypatch):
    upsert_contact("Əhməd", ["+994501234567"], "people/c123", source="google")
    monkeypatch.setattr(contacts, "get_google_contacts", lambda: [{"resource_name": "people/c123", "display_name": "Əhməd", "phones": ["+994559041494"]}])
    contacts.sync_google_contacts()
    assert list_contacts()[0]["value"] == "+994559041494"


def test_sync_preserves_local_only_contacts(contact_db, monkeypatch):
    upsert_contact("Local", ["+994501111111"], source="local")
    monkeypatch.setattr(contacts, "get_google_contacts", lambda: [])
    contacts.sync_google_contacts()
    assert [item["display_name"] for item in list_contacts()] == ["Local"]


def test_sync_removes_stale_google_managed_contact(contact_db, monkeypatch):
    upsert_contact("Google Contact", ["+994501111111"], "people/deleted", source="google")
    upsert_contact("Local", ["+994502222222"], source="local")
    monkeypatch.setattr(contacts, "get_google_contacts", lambda: [])
    result = contacts.sync_google_contacts()
    assert [item["display_name"] for item in list_contacts()] == ["Local"]
    assert result["status"] == "success"
    assert result["data"][0]["removed"] == 1


def test_reconcile_local_create_persists_google_identity(contact_db):
    contacts._reconcile_local_create({"display_name": "Test", "resource_name": "people/c1", "phones": ["+994501234567"]})
    data = list_contacts()
    assert data[0]["display_name"] == "Test"
    assert data[0]["value"] == "+994501234567"
    assert data[0]["google_resource_name"] == "people/c1"


def test_reconcile_local_update_matches_existing_google_identity(contact_db):
    upsert_contact("Old", ["+994501234567"], "people/c1", source="google")
    contacts._reconcile_local_update({"display_name": "Updated", "resource_name": "people/c1", "phones": ["+994559041494"]})
    data = list_contacts()
    assert len(data) == 1
    assert data[0]["display_name"] == "Updated"
    assert data[0]["value"] == "+994559041494"


def test_reconcile_local_delete_removes_matching_google_contact(contact_db):
    upsert_contact("Google", ["+994501111111"], "people/c1", source="google")
    upsert_contact("Local", ["+994502222222"], source="local")
    assert contacts._reconcile_local_delete("people/c1") is True
    assert [item["display_name"] for item in list_contacts()] == ["Local"]


def test_sync_does_not_corrupt_sql_on_google_error(contact_db, monkeypatch):
    upsert_contact("Local", ["+994501111111"], source="local")
    monkeypatch.setattr(contacts, "get_google_contacts", MagicMock(side_effect=RuntimeError("OAuth failed")))
    result = contacts.sync_google_contacts()
    assert result["status"] == "error"
    assert "Google kontaktları alınmadı" in result["meta"]["error"]
    assert list_contacts()[0]["display_name"] == "Local"


def test_sync_deduplicates_google_contacts_by_phone(contact_db, monkeypatch):
    monkeypatch.setattr(contacts, "get_google_contacts", lambda: [{"resource_name": "people/1", "display_name": "Test", "phones": ["+994501234567"]}, {"resource_name": "people/2", "display_name": "Test 2", "phones": ["+994501234567"]}])
    contacts.sync_google_contacts()
    assert len(list_contacts()) == 1


def test_tool_executor_dispatches_contact_sync():
    import asyncio
    from types import SimpleNamespace
    from core.tool_executor import ToolExecutor
    ui = MagicMock()
    ui.muted = False
    executor = ToolExecutor(ui, MagicMock(), MagicMock(), MagicMock())
    with patch("core.tool_executor.sync_google_contacts", return_value={"type": "contact", "status": "success", "query": {}, "data": [{"id": "contact:sync", "new": 1}], "count": 1, "selected": None, "meta": {}}) as sync:
        response = asyncio.run(executor.execute(SimpleNamespace(id="contacts-1", name="sync_google_contacts", args={})))
    sync.assert_called_once_with()
    assert response.response["result"]["data"][0]["new"] == 1
