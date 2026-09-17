"""VICTOR kontakt axtarışını SQL repository üzərindən icra edir."""

from __future__ import annotations

from core.results import make_result
from memory.contacts_repository import find_contact, find_contacts_by_name, normalize_phone


def _contact_item(contact: dict) -> dict:
    item = dict(contact)
    item["id"] = f"contact:{contact.get('id', '')}"
    return item


def search_contacts(query: str = "", phone: str = "", limit: int = 10) -> dict:
    """Kontaktı yalnız VICTOR-un SQL kontakt repository-sindən axtarır."""
    query = str(query or "").strip()
    phone = str(phone or "").strip()
    limit = max(1, min(int(limit or 10), 50))

    matches: list[dict] = []
    if phone:
        try:
            contact = find_contact(phone=normalize_phone(phone))
        except ValueError:
            contact = None
        if contact:
            matches.append(contact)

    if query and not matches:
        matches = find_contacts_by_name(query)

    data = [_contact_item(contact) for contact in matches[:limit]]
    status = "success" if data else "empty"
    return make_result(
        "contact",
        status,
        query={"query": query, "phone": phone, "limit": limit},
        data=data,
        selected=data[0] if data else None,
        meta={"source": "sql"},
    )
