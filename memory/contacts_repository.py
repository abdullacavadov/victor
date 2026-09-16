"""VICTOR kontakt domeni üçün SQL əməliyyatları."""

from __future__ import annotations

import json
import re
import unicodedata

import memory.database as database


def normalize_phone(phone_number: str) -> str:
    raw = str(phone_number or "").strip()
    digits = re.sub(r"\D+", "", raw)
    if raw.startswith("+"):
        if not 8 <= len(digits) <= 15:
            raise ValueError("Telefon nömrəsi etibarlı beynəlxalq formatda deyil.")
        return digits
    if digits.startswith("994"):
        pass
    elif digits.startswith("0") and len(digits) in (10, 11):
        digits = "994" + digits[1:]
    elif len(digits) == 9:
        digits = "994" + digits
    else:
        raise ValueError("Telefon nömrəsi etibarlı beynəlxalq formatda deyil.")
    if len(digits) < 8 or len(digits) > 15:
        raise ValueError("Telefon nömrəsi etibarlı beynəlxalq formatda deyil.")
    return digits


def normalize_lookup(text: str) -> str:
    text = (text or "").strip().casefold()
    text = text.translate(str.maketrans({"ə": "e", "ı": "i", "ö": "o", "ü": "u", "ş": "s", "ç": "c", "ğ": "g"}))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def contact_key(name: str, phone: str, existing_keys: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", normalize_lookup(name)).strip("_") or "contact"
    if base not in existing_keys:
        return base
    candidate = f"{base}_{normalize_phone(phone)[-6:]}"
    if candidate not in existing_keys:
        return candidate
    index = 2
    while f"{candidate}_{index}" in existing_keys:
        index += 1
    return f"{candidate}_{index}"


def _ensure_db() -> None:
    database.initialize_database()


def _phones_for_contact(connection, contact_id: int) -> list[str]:
    rows = connection.execute(
        "SELECT phone_number FROM contact_phones WHERE contact_id = ? ORDER BY is_primary DESC, id",
        (contact_id,),
    ).fetchall()
    return [row["phone_number"] for row in rows]


def _row_to_contact(connection, row) -> dict:
    phones = _phones_for_contact(connection, row["id"])
    metadata = {}
    if row["metadata"]:
        try:
            metadata = json.loads(row["metadata"])
        except (TypeError, json.JSONDecodeError):
            metadata = {}
    result = {
        "id": row["id"],
        "contact_key": row["contact_key"],
        "display_name": row["display_name"],
        "value": f"+{phones[0]}" if phones else "",
        "phones": [{"number": f"+{phone}"} for phone in phones],
        "google_resource_name": row["google_resource_name"] or "",
        "source": row["source"],
        "status": row["status"],
    }
    result.update(metadata)
    return result


def list_contacts(user_id: int = 1, include_deleted: bool = False) -> list[dict]:
    _ensure_db()
    with database.transaction() as connection:
        sql = "SELECT * FROM contacts WHERE user_id = ?"
        params = [user_id]
        if not include_deleted:
            sql += " AND status = 'active'"
        sql += " ORDER BY id"
        rows = connection.execute(sql, params).fetchall()
        return [_row_to_contact(connection, row) for row in rows]


def get_contact(contact_id: int, user_id: int = 1) -> dict | None:
    _ensure_db()
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT * FROM contacts WHERE id = ? AND user_id = ? AND status = 'active'",
            (contact_id, user_id),
        ).fetchone()
        return _row_to_contact(connection, row) if row else None


def find_contact(display_name: str = "", phone: str = "", google_resource_name: str = "", user_id: int = 1) -> dict | None:
    _ensure_db()
    normalized_phone = ""
    if phone:
        try:
            normalized_phone = normalize_phone(phone)
        except ValueError:
            normalized_phone = ""
    normalized_name = normalize_lookup(display_name)
    with database.transaction() as connection:
        row = None
        if google_resource_name:
            row = connection.execute(
                "SELECT * FROM contacts WHERE user_id = ? AND google_resource_name = ? AND status = 'active'",
                (user_id, google_resource_name),
            ).fetchone()
        if row is None and normalized_phone:
            row = connection.execute(
                """SELECT c.* FROM contacts c
                   JOIN contact_phones p ON p.contact_id = c.id
                   WHERE c.user_id = ? AND p.phone_number = ? AND c.status = 'active'
                   ORDER BY c.id LIMIT 1""",
                (user_id, normalized_phone),
            ).fetchone()
        if row is None and normalized_name:
            rows = connection.execute(
                "SELECT * FROM contacts WHERE user_id = ? AND status = 'active' ORDER BY id",
                (user_id,),
            ).fetchall()
            for candidate in rows:
                if normalize_lookup(candidate["display_name"]) == normalized_name or normalize_lookup(candidate["contact_key"]) == normalized_name:
                    row = candidate
                    break
        return _row_to_contact(connection, row) if row else None


def find_contacts_by_name(query: str, user_id: int = 1) -> list[dict]:
    needle = normalize_lookup(query)
    if not needle:
        return []
    _ensure_db()
    with database.transaction() as connection:
        rows = connection.execute(
            "SELECT * FROM contacts WHERE user_id = ? AND status = 'active' ORDER BY id",
            (user_id,),
        ).fetchall()
        matches = []
        for row in rows:
            candidate = normalize_lookup(row["display_name"])
            key = normalize_lookup(row["contact_key"])
            if candidate == needle or key == needle or candidate.startswith(needle) or needle in candidate:
                matches.append(_row_to_contact(connection, row))
        return matches


def upsert_contact(
    display_name: str,
    phones: list[str],
    google_resource_name: str = "",
    contact_key_value: str = "",
    source: str = "local",
    metadata: dict | None = None,
    user_id: int = 1,
) -> dict:
    _ensure_db()
    display_name = str(display_name or "").strip()
    normalized_phones = list(dict.fromkeys(normalize_phone(str(phone)) for phone in phones if str(phone).strip()))
    if not display_name or not normalized_phones:
        raise ValueError("Kontakt üçün ad və ən azı bir telefon nömrəsi lazımdır.")

    with database.transaction() as connection:
        row = None
        if google_resource_name:
            row = connection.execute(
                "SELECT * FROM contacts WHERE user_id = ? AND google_resource_name = ?",
                (user_id, google_resource_name),
            ).fetchone()
        if row is None:
            for phone in normalized_phones:
                row = connection.execute(
                    """SELECT c.* FROM contacts c
                       JOIN contact_phones p ON p.contact_id = c.id
                       WHERE c.user_id = ? AND p.phone_number = ?
                       ORDER BY c.id LIMIT 1""",
                    (user_id, phone),
                ).fetchone()
                if row:
                    break
        if row is None:
            normalized_name = normalize_lookup(display_name)
            rows = connection.execute(
                "SELECT * FROM contacts WHERE user_id = ? AND status = 'active' ORDER BY id",
                (user_id,),
            ).fetchall()
            for candidate in rows:
                if normalize_lookup(candidate["display_name"]) == normalized_name:
                    row = candidate
                    break

        if row is None:
            keys = {item["contact_key"] for item in connection.execute("SELECT contact_key FROM contacts WHERE user_id = ?", (user_id,)).fetchall()}
            key = contact_key_value or contact_key(display_name, normalized_phones[0], keys)
            now = database.utc_now()
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"))
            cursor = connection.execute(
                """INSERT INTO contacts
                   (user_id, contact_key, display_name, google_resource_name, source, status, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                (user_id, key, display_name, google_resource_name or None, source, metadata_json, now, now),
            )
            contact_id = cursor.lastrowid
        else:
            contact_id = row["id"]
            key = row["contact_key"]
            now = database.utc_now()
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"))
            connection.execute(
                """UPDATE contacts
                   SET display_name = ?, google_resource_name = COALESCE(?, google_resource_name),
                       source = ?, status = 'active', metadata = ?, updated_at = ?
                   WHERE id = ? AND user_id = ?""",
                (display_name, google_resource_name or None, source, metadata_json, now, contact_id, user_id),
            )
            connection.execute("DELETE FROM contact_phones WHERE contact_id = ?", (contact_id,))

        now = database.utc_now()
        for index, phone in enumerate(normalized_phones):
            connection.execute(
                "INSERT INTO contact_phones(contact_id, phone_number, is_primary, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (contact_id, phone, 1 if index == 0 else 0, now, now),
            )
        result = connection.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        return _row_to_contact(connection, result)


def delete_contact(google_resource_name: str, user_id: int = 1) -> bool:
    if not google_resource_name:
        return False
    _ensure_db()
    with database.transaction() as connection:
        now = database.utc_now()
        cursor = connection.execute(
            "UPDATE contacts SET status = 'deleted', updated_at = ? WHERE user_id = ? AND google_resource_name = ? AND status = 'active'",
            (now, user_id, google_resource_name),
        )
        return cursor.rowcount > 0


def restore_contact(contact_id: int, user_id: int = 1) -> bool:
    _ensure_db()
    with database.transaction() as connection:
        cursor = connection.execute(
            "UPDATE contacts SET status = 'active', updated_at = ? WHERE id = ? AND user_id = ?",
            (database.utc_now(), contact_id, user_id),
        )
        return cursor.rowcount > 0
