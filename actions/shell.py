from __future__ import annotations

import re

from core.security.command_runner import run_command
from memory.contacts_repository import find_contact, find_contacts_by_name, normalize_phone


_CONTACT_DISPLAY_NAME_RE = re.compile(r"display_name\s+LIKE\s+['\"]%?(.*?)%?['\"]", re.IGNORECASE)
_CONTACT_PHONE_RE = re.compile(r"(?:phone_number|phone)\s*=\s*['\"](.*?)['\"]", re.IGNORECASE)


def _format_contact(contact: dict) -> str:
    phones = ", ".join(item.get("number", "") for item in contact.get("phones", []))
    return f"{contact.get('display_name', '')} — {phones}" if phones else str(contact.get("display_name", ""))


def _route_contact_sqlite_query(command: str) -> str | None:
    """Kontakt üçün köhnə sqlite3 shell sorğusunu SQL repository-yə yönləndirir."""
    if not re.match(r"^\s*sqlite3(?:\.exe)?\s+", command, re.IGNORECASE):
        return None
    if not re.search(r"\bSELECT\b", command, re.IGNORECASE) or not re.search(r"\bFROM\s+contacts\b", command, re.IGNORECASE):
        return "SQL kontakt sorğuları yalnız VICTOR-un Python repository-si ilə icra olunur."

    match = _CONTACT_DISPLAY_NAME_RE.search(command)
    if match:
        query = match.group(1).strip()
        contacts = find_contacts_by_name(query)
    else:
        phone_match = _CONTACT_PHONE_RE.search(command)
        if not phone_match:
            return "Kontakt sorğusu üçün ad və ya telefon filtri tələb olunur."
        try:
            contact = find_contact(phone=normalize_phone(phone_match.group(1)))
        except ValueError:
            contact = None
        contacts = [contact] if contact else []

    if not contacts:
        return "Kontakt tapılmadı."
    return "\n".join(_format_contact(contact) for contact in contacts)


def shell_run(command: str) -> str:
    routed = _route_contact_sqlite_query(command)
    if routed is not None:
        return routed
    return run_command(command)
