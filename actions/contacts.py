from __future__ import annotations

import re
import unicodedata

from core.results import make_result
from integrations.google.contacts import (
    create_google_contact,
    delete_google_contact,
    get_google_contacts,
    update_google_contact,
)
from memory.contacts_repository import (
    contact_key,
    delete_contact as delete_sql_contact,
    find_contact,
    list_contacts,
    normalize_lookup,
    normalize_phone,
    upsert_contact,
)


def _normalize_lookup(text: str) -> str:
    text = (text or "").strip().casefold()
    text = text.translate(str.maketrans({"ə": "e", "ı": "i", "ö": "o", "ü": "u", "ş": "s", "ç": "c", "ğ": "g"}))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def _normalize_phone(phone_number: str) -> str:
    return normalize_phone(phone_number)


def _entry_phones(entry: dict) -> list[str]:
    values = []
    for key in ("value", "phone_number", "phone", "number", "mobile", "tel"):
        value = entry.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            values.append(str(value).strip())
    for key in ("phones", "numbers", "phone_numbers"):
        value = entry.get(key)
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, (str, int)):
                    values.append(str(item).strip())
                elif isinstance(item, dict):
                    nested = item.get("value") or item.get("number") or item.get("phone")
                    if nested:
                        values.append(str(nested).strip())
    normalized = []
    for value in values:
        try:
            normalized.append(_normalize_phone(value))
        except ValueError:
            continue
    return list(dict.fromkeys(normalized))


def _contact_key(name: str, phone: str, existing: dict) -> str:
    keys = set(existing) if isinstance(existing, dict) else set(existing or ())
    return contact_key(name, phone, keys)


def _build_entry(contact: dict, phones: list[str], previous: dict | None = None) -> dict:
    entry = dict(previous or {})
    entry["display_name"] = contact["display_name"]
    entry["value"] = f"+{phones[0]}"
    entry["phones"] = [{"number": f"+{phone}"} for phone in phones]
    if contact.get("resource_name"):
        entry["google_resource_name"] = contact["resource_name"]
    return entry


def _find_match(local: dict, contact: dict, phones: list[str]) -> tuple[str | None, dict | None]:
    resource_name = contact.get("resource_name")
    if resource_name:
        for key, entry in local.items():
            if isinstance(entry, dict) and entry.get("google_resource_name") == resource_name:
                return key, entry
    phone_set = set(phones)
    if phone_set:
        for key, entry in local.items():
            if isinstance(entry, dict) and phone_set.intersection(_entry_phones(entry)):
                return key, entry
    normalized_name = _normalize_lookup(contact.get("display_name", ""))
    if normalized_name:
        for key, entry in local.items():
            if isinstance(entry, dict) and _normalize_lookup(str(entry.get("display_name") or key)) == normalized_name:
                return key, entry
    return None, None


def _contact_result(contact: dict, query: dict | None = None, meta: dict | None = None) -> dict:
    resource_name = str(contact.get("resource_name") or contact.get("google_resource_name") or "")
    item = dict(contact)
    item["id"] = f"contact:{resource_name}" if resource_name else f"contact:{_normalize_lookup(str(contact.get('display_name') or ''))}"
    item["google_resource_name"] = resource_name
    return make_result("contact", "success", query=query or {}, data=[item], selected=item, meta=meta or {})


def _reconcile_local_create(contact: dict) -> None:
    display_name = str(contact.get("display_name") or "").strip()
    phones = [_normalize_phone(str(phone)) for phone in contact.get("phones") or []]
    if not display_name or not phones:
        raise ValueError("Google kontaktının SQL üçün adı və telefonu yoxdur.")
    existing = find_contact(
        display_name=display_name,
        phone=phones[0],
        google_resource_name=str(contact.get("resource_name") or ""),
    )
    metadata = {}
    if existing:
        metadata = {key: value for key, value in existing.items() if key not in {"id", "contact_key", "display_name", "value", "phones", "google_resource_name", "source", "status"}}
    upsert_contact(
        display_name=display_name,
        phones=phones,
        google_resource_name=str(contact.get("resource_name") or ""),
        contact_key_value=existing.get("contact_key", "") if existing else "",
        source="google",
        metadata=metadata,
    )


def _reconcile_local_update(contact: dict) -> None:
    _reconcile_local_create(contact)


def _reconcile_local_delete(resource_name: str) -> bool:
    return delete_sql_contact(resource_name)


def sync_google_contacts() -> dict:
    try:
        google_contacts = get_google_contacts()
    except Exception as exc:
        return make_result("contact", "error", data=[], meta={"error": f"Google kontaktları alınmadı: {exc}"})

    added = updated = unchanged = removed = 0
    seen_resources: set[str] = set()
    seen_phones: set[str] = set()

    try:
        for contact in google_contacts:
            display_name = str(contact.get("display_name") or "").strip()
            phones = []
            for raw_phone in contact.get("phones") or []:
                try:
                    phone = _normalize_phone(str(raw_phone))
                except ValueError:
                    continue
                if phone not in phones:
                    phones.append(phone)
            if not display_name or not phones:
                continue

            resource_name = str(contact.get("resource_name") or "").strip()
            if resource_name and resource_name in seen_resources:
                continue
            if resource_name:
                seen_resources.add(resource_name)
            if set(phones).intersection(seen_phones):
                continue
            seen_phones.update(phones)

            existing = find_contact(
                display_name=display_name,
                phone=phones[0],
                google_resource_name=resource_name,
            )
            if existing is None:
                upsert_contact(display_name, phones, resource_name, source="google")
                added += 1
                continue

            before = (existing["display_name"], tuple(item["number"] for item in existing["phones"]), existing.get("google_resource_name", ""))
            upsert_contact(
                display_name,
                phones,
                resource_name,
                contact_key_value=existing.get("contact_key", ""),
                source="google",
            )
            after = (display_name, tuple(f"+{phone}" for phone in phones), resource_name)
            if before == after:
                unchanged += 1
            else:
                updated += 1

        active_contacts = list_contacts()
        for contact in active_contacts:
            resource_name = str(contact.get("google_resource_name") or "")
            if resource_name and resource_name not in seen_resources:
                if delete_sql_contact(resource_name):
                    removed += 1
    except Exception as exc:
        return make_result("contact", "error", data=[], meta={"error": str(exc)})

    stats = {"id": "contact:sync", "new": added, "updated": updated, "removed": removed, "unchanged": unchanged}
    status = "success" if added or updated or removed else "empty"
    return make_result("contact", status, data=[stats], meta={"sync": True})


def create_contact(display_name: str, phone_number: str) -> dict:
    phone = _normalize_phone(phone_number)
    contact = create_google_contact(display_name, [f"+{phone}"])
    try:
        _reconcile_local_create(contact)
    except Exception as exc:
        return _contact_result(contact, {"display_name": display_name}, {"local_sync_error": str(exc)}) | {"status": "partial"}
    return _contact_result(contact, {"display_name": display_name})


def update_contact(resource_name: str, display_name: str, phone_number: str) -> dict:
    phone = _normalize_phone(phone_number)
    contact = update_google_contact(resource_name, display_name, [f"+{phone}"])
    try:
        _reconcile_local_update(contact)
    except Exception as exc:
        return _contact_result(contact, {"resource_name": resource_name, "display_name": display_name}, {"local_sync_error": str(exc)}) | {"status": "partial"}
    return _contact_result(contact, {"resource_name": resource_name, "display_name": display_name})


def delete_contact(resource_name: str) -> dict:
    result = delete_google_contact(resource_name)
    try:
        local_removed = _reconcile_local_delete(result["resource_name"])
    except Exception as exc:
        return make_result("contact", "partial", query={"resource_name": resource_name}, data=[{"id": f"contact:{resource_name}", "google_resource_name": resource_name}], selected=None, meta={"verification_status": result["verification_status"], "local_sync_error": str(exc)})
    return make_result("contact", "success", query={"resource_name": resource_name}, data=[{"id": f"contact:{resource_name}", "google_resource_name": resource_name}], selected=None, meta={"verification_status": result["verification_status"], "local_removed": local_removed})
