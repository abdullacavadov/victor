from unittest.mock import MagicMock, patch

from actions import whatsapp
from integrations.whatsapp.web import WhatsAppVisibleMessage, WhatsAppWebBridge


def test_normalize_phone_keeps_international_number():
    assert whatsapp._normalize_phone("+994 50 123 45 67") == "994501234567"


def test_normalize_lookup_is_case_and_diacritic_insensitive():
    assert whatsapp._normalize_lookup("İSMAYIL") == "ismayil"


def test_find_contact_matches_alias(monkeypatch):
    monkeypatch.setattr(
        whatsapp,
        "list_contacts",
        lambda: [
            {
                "display_name": "Əhməd",
                "contact_key": "ehmed",
                "value": "+994501234567",
                "aliases": ["Ami"],
            }
        ],
    )

    contact = whatsapp._find_contact("Ami")

    assert contact is not None
    assert contact["display_name"] == "Əhməd"
    assert contact["value"] == "+994501234567"


def test_find_contact_returns_none_for_unknown_contact(monkeypatch):
    monkeypatch.setattr(
        whatsapp,
        "list_contacts",
        lambda: [
            {
                "display_name": "Əhməd",
                "contact_key": "ehmed",
                "value": "+994501234567",
            }
        ],
    )

    assert whatsapp._find_contact("Tanınmayan şəxs") is None


def test_save_contact_rejects_invalid_phone():
    result = whatsapp.save_whatsapp_contact("Test", "123")

    assert "Telefon nömrəsi" in result


def test_send_message_requires_message():
    assert whatsapp.send_whatsapp_message("   ") == "Mesaj boş ola bilməz."


def test_send_message_requires_recipient_when_phone_missing(monkeypatch):
    monkeypatch.setattr(whatsapp, "_find_contact", lambda _: None)

    result = whatsapp.send_whatsapp_message(
        "Salam",
        recipient_name="Naməlum şəxs",
    )

    assert "telefon nömrəsi tapılmadı" in result


def test_draft_does_not_run_automatic_send(monkeypatch):
    monkeypatch.setattr(whatsapp, "HAS_PYAUTOGUI", True)
    monkeypatch.setattr(
        whatsapp,
        "_open_whatsapp_desktop_via_scheme",
        MagicMock(return_value=(True, "WhatsApp Desktop açıldı.")),
    )
    send_prefilled = MagicMock(return_value=(True, "ok"))
    monkeypatch.setattr(whatsapp, "_send_prefilled_message", send_prefilled)

    result = whatsapp.send_whatsapp_message(
        "Salam",
        phone_number="+994501234567",
        send_now=False,
        app_target="desktop",
    )

    assert "qaralama" in result
    send_prefilled.assert_not_called()


def test_send_now_sends_uri_prefilled_message(monkeypatch):
    monkeypatch.setattr(whatsapp, "HAS_PYAUTOGUI", True)
    open_desktop = MagicMock(return_value=(True, "WhatsApp Desktop açıldı."))
    monkeypatch.setattr(whatsapp, "_open_whatsapp_desktop_via_scheme", open_desktop)
    send_prefilled = MagicMock(return_value=(True, "ok"))
    monkeypatch.setattr(whatsapp, "_send_prefilled_message", send_prefilled)

    result = whatsapp.send_whatsapp_message(
        "Salam",
        phone_number="+994501234567",
        send_now=True,
        app_target="desktop",
    )

    assert "göndərildi" in result
    open_desktop.assert_called_once_with(
        "994501234567",
        "Salam",
        include_text=True,
    )
    send_prefilled.assert_called_once_with(whatsapp.DESKTOP_LOAD_DELAY)


def test_resolve_contact_phone_supports_phone_collections():
    contact = {
        "display_name": "Test",
        "phones": [{"number": "+994559041494"}],
    }

    assert whatsapp._resolve_contact_phone(contact) == "994559041494"


def test_send_message_uses_resolved_contact_phone(monkeypatch):
    monkeypatch.setattr(
        whatsapp,
        "_find_contact",
        lambda _: {
            "display_name": "Мисс Джавадова",
            "phones": [{"number": "+994559041494"}],
        },
    )
    monkeypatch.setattr(
        whatsapp,
        "_open_whatsapp_desktop_via_scheme",
        MagicMock(return_value=(True, "WhatsApp Desktop açıldı.")),
    )

    result = whatsapp.send_whatsapp_message(
        "Salam",
        recipient_name="Мисс Джавадова",
        send_now=False,
        app_target="desktop",
    )

    assert "qaralama" in result


def test_tool_executor_dispatches_whatsapp_send():
    import asyncio
    from types import SimpleNamespace

    from core.tool_executor import ToolExecutor

    ui = MagicMock()
    ui.muted = False
    executor = ToolExecutor(ui, MagicMock(), MagicMock(), MagicMock())

    with patch(
        "core.tool_executor.send_whatsapp_message",
        return_value="WhatsApp Desktop içində qaralama mesaj açıldı.",
    ) as send:
        response = asyncio.run(
            executor.execute(
                SimpleNamespace(
                    id="wa-1",
                    name="send_whatsapp_message",
                    args={
                        "message": "Salam",
                        "phone_number": "+994501234567",
                        "send_now": False,
                        "app_target": "desktop",
                    },
                )
            )
        )

    send.assert_called_once_with(
        "Salam",
        "+994501234567",
        "",
        False,
        "desktop",
    )
    assert response.response["result"] == "WhatsApp Desktop içində qaralama mesaj açıldı."


def _message(message_id, timestamp, direction="incoming", content="text"):
    return WhatsAppVisibleMessage(
        message_id=message_id,
        conversation_id="Rəşad Qurbanlı",
        sender="Rəşad Qurbanlı" if direction == "incoming" else "Abdulla",
        sender_phone="",
        content=content,
        timestamp=timestamp,
        direction=direction,
    )


def test_whatsapp_message_sort_is_chronological_and_preserves_same_time_order():
    messages = [
        _message("late", "23:53"),
        _message("early", "17:42"),
        _message("middle", "21:58"),
        _message("middle-2", "21:58"),
    ]

    result = WhatsAppWebBridge._sort_messages(messages)

    assert [item.message_id for item in result] == ["early", "middle", "middle-2", "late"]


def test_whatsapp_message_direction_uses_message_out_marker():
    item = MagicMock()
    item.locator.return_value.count.return_value = 0
    item.evaluate.return_value = "message-out x1 abc"

    assert WhatsAppWebBridge._message_direction(item) == "outgoing"


def test_whatsapp_message_media_is_not_reported_as_empty():
    item = MagicMock()
    item.locator.return_value.count.return_value = 0
    item.locator.side_effect = lambda selector: (
        MagicMock(**{"count.return_value": 1})
        if selector == '[data-testid="ptt-status"]'
        else MagicMock(**{"count.return_value": 0})
    )

    assert WhatsAppWebBridge._message_media_label(item) == "Səsli mesaj"


def test_whatsapp_emoji_content_is_normalized_for_tts():
    assert WhatsAppWebBridge._is_emoji_only("😀👍") is True
    assert WhatsAppWebBridge._is_emoji_only("Salam 😀") is False
