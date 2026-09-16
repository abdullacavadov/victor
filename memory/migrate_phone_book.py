"""phone_book.json məlumatlarını SQL kontakt domeninə köçürür."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import memory.database as database
from memory.contacts_repository import upsert_contact

BASE_DIR = Path(__file__).resolve().parent.parent
PHONEBOOK_FILE = BASE_DIR / "memory" / "phone_book.json"


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
                if isinstance(item, (str, int)) and str(item).strip():
                    values.append(str(item).strip())
                elif isinstance(item, dict):
                    nested = item.get("value") or item.get("number") or item.get("phone")
                    if nested:
                        values.append(str(nested).strip())
    return list(dict.fromkeys(values))


def load_source(path: Path = PHONEBOOK_FILE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("phone_book.json strukturu düzgün deyil.")
    return data


def migrate(path: Path = PHONEBOOK_FILE, dry_run: bool = False) -> dict:
    database.initialize_database()
    source = load_source(path)
    if not source:
        return {"total": 0, "new": 0, "existing": 0, "invalid": 0}

    total = new = existing = invalid = 0
    for key, entry in source.items():
        if not isinstance(entry, dict):
            invalid += 1
            continue
        display_name = str(entry.get("display_name") or key).strip()
        phones = _entry_phones(entry)
        if not display_name or not phones:
            invalid += 1
            continue
        total += 1
        if dry_run:
            continue
        before = None
        from memory.contacts_repository import find_contact
        before = find_contact(display_name=display_name, phone=phones[0], google_resource_name=str(entry.get("google_resource_name") or ""))
        metadata = {k: v for k, v in entry.items() if k not in {"display_name", "value", "phones", "google_resource_name"}}
        upsert_contact(
            display_name=display_name,
            phones=phones,
            google_resource_name=str(entry.get("google_resource_name") or ""),
            contact_key_value=key,
            source="google" if entry.get("google_resource_name") else "local",
            metadata=metadata,
        )
        if before:
            existing += 1
        else:
            new += 1

    return {"total": total, "new": new, "existing": existing, "invalid": invalid}


def main() -> int:
    parser = argparse.ArgumentParser(description="phone_book.json -> SQLite kontakt miqrasiyası")
    parser.add_argument("--source", type=Path, default=PHONEBOOK_FILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = migrate(args.source, args.dry_run)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Miqrasiya alınmadı: {exc}")
        return 1
    print(f"Miqrasiya ediləcək kontaktlar: {result['total']}")
    print(f"Yeni köçürülən: {result['new']}")
    print(f"SQL-də əvvəlcədən mövcud: {result['existing']}")
    print(f"Keçilməyən/qüsurlu: {result['invalid']}")
    if args.dry_run:
        print("Dry-run tamamlandı; SQL məlumatına dəyişiklik edilmədi.")
    else:
        print("Kontakt miqrasiyası tamamlandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
