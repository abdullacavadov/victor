"""
WhatsApp mesaj göndərmə — Windows üçün WhatsApp Desktop URI scheme və ya Web.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import unicodedata
import urllib.parse
import webbrowser
from pathlib import Path

from memory.contacts_repository import list_contacts
from memory.contacts_repository import upsert_contact

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


AUTO_SEND_DELAY_SECONDS = 2.4
# WhatsApp pəncərəsinin açılıb söhbətin yüklənməsi üçün gözləmə müddətləri.
DESKTOP_LOAD_DELAY = 4.5
WEB_LOAD_DELAY = 6.5
PREFERRED_BROWSERS = ["chrome", "msedge", "firefox"]


def _normalize_phone(phone_number: str) -> str:
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


def _normalize_lookup(text: str) -> str:
    text = (text or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ı", "i")
    text = re.sub(r"\s+", " ", text)
    return text


def _contact_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalize_lookup(name)).strip("_") or "contact"


def _contact_candidates() -> list[dict]:
    """Kontaktları yalnız SQL-dən oxuyur."""
    candidates = []
    for entry in list_contacts():
        item = dict(entry)
        item["_source"] = "contacts"
        item["_key"] = item.get("contact_key", "")
        candidates.append(item)
    return candidates


def _match_score(needle: str, candidate: str) -> int:
    candidate_norm = _normalize_lookup(candidate)
    if not candidate_norm:
        return 0
    if candidate_norm == needle:
        return 300
    if candidate_norm.startswith(needle) or needle.startswith(candidate_norm):
        return 220
    if needle in candidate_norm:
        return 160
    needle_parts = needle.split()
    if needle_parts and all(part in candidate_norm for part in needle_parts):
        return 120
    return 0


def _find_contact(recipient_name: str) -> dict | None:
    needle = _normalize_lookup(recipient_name)
    if not needle:
        return None

    best_match = None
    best_score = 0
    for entry in _contact_candidates():
        names = [entry.get("display_name", ""), entry.get("_key", "")]
        metadata = entry.get("metadata", {})
        if isinstance(metadata, dict):
            aliases = metadata.get("aliases", [])
            if isinstance(aliases, list):
                names.extend(str(alias) for alias in aliases)
            elif aliases:
                names.append(str(aliases))
        for name in names:
            score = _match_score(needle, str(name))
            if score > best_score:
                best_score = score
                best_match = entry

    return best_match


def _contact_phone_candidates(contact: dict) -> list[str]:
    values = []
    value = contact.get("value")
    if isinstance(value, (str, int)) and str(value).strip():
        values.append(str(value).strip())

    phones = contact.get("phones", [])
    if isinstance(phones, list):
        for item in phones:
            if isinstance(item, dict):
                number = item.get("number") or item.get("phone_number") or item.get("phone")
                if isinstance(number, (str, int)) and str(number).strip():
                    values.append(str(number).strip())
            elif isinstance(item, (str, int)) and str(item).strip():
                values.append(str(item).strip())
    return values


def _resolve_contact_phone(contact: dict) -> str:
    for candidate in _contact_phone_candidates(contact):
        try:
            return _normalize_phone(candidate)
        except ValueError:
            continue
    return ""


def save_whatsapp_contact(display_name: str, phone_number: str, aliases: str = "") -> str:
    if not display_name or not display_name.strip():
        return "Kontakt adı boş ola bilməz."

    try:
        normalized_phone = _normalize_phone(phone_number)
    except ValueError as exc:
        return str(exc)

    alias_list = []
    if aliases and aliases.strip():
        alias_list = [part.strip() for part in aliases.split(",") if part.strip()]

    upsert_contact(
        display_name=display_name.strip(),
        phones=[f"+{normalized_phone}"],
        source="whatsapp",
        metadata={"aliases": alias_list} if alias_list else None,
    )

    if alias_list:
        return f"{display_name.strip()} WhatsApp kontaktlarında saxlanıldı. Ləqəblər: {', '.join(alias_list)}"
    return f"{display_name.strip()} WhatsApp kontaktlarında saxlanıldı."


def _copy_to_clipboard(text: str) -> None:
    if HAS_PYPERCLIP:
        pyperclip.copy(text)
        return
    safe = text.replace("'", "`'")
    subprocess.run(
        ["powershell", "-Command", f"Set-Clipboard -Value '{safe}'"],
        check=True, timeout=5,
    )


def _open_url(url: str) -> None:
    webbrowser.open(url)


def _open_whatsapp_desktop_via_scheme(phone_number: str, message: str, include_text: bool = True) -> tuple[bool, str]:
    if include_text and message.strip():
        url = f"whatsapp://send?phone={phone_number}&text={urllib.parse.quote(message.strip())}"
    else:
        url = f"whatsapp://send?phone={phone_number}"
    try:
        os.startfile(url)  # type: ignore[attr-defined]
    except Exception:
        try:
            subprocess.run(["cmd", "/c", "start", "", url], timeout=10)
        except Exception as exc:
            return False, f"WhatsApp Desktop açılmadı: {exc}"
    return True, "WhatsApp Desktop açıldı."


def _open_whatsapp_web(phone_number: str, message: str, include_text: bool = True) -> tuple[bool, str]:
    if include_text and message.strip():
        url = f"https://web.whatsapp.com/send?phone={phone_number}&text={urllib.parse.quote(message.strip())}"
    else:
        url = f"https://web.whatsapp.com/send?phone={phone_number}"
    try:
        _open_url(url)
    except Exception as exc:
        return False, f"WhatsApp Web açılmadı: {exc}"
    return True, "web tarayıcı"


def _focus_whatsapp_window() -> None:
    """WhatsApp Desktop pəncərəsini önə gətirməyə çalışır (best-effort, pygetwindow)."""
    try:
        import pygetwindow as gw
    except Exception:
        return
    try:
        for win in gw.getAllWindows():
            if "whatsapp" in (win.title or "").lower():
                try:
                    if win.isMinimized:
                        win.restore()
                except Exception:
                    pass
                try:
                    win.activate()
                except Exception:
                    pass
                break
    except Exception:
        pass


def _send_prefilled_message(load_delay: float) -> tuple[bool, str]:
    """Göndərmə üçün URI ilə əvvəlcədən doldurulmuş mesajı Enter ilə göndərir."""
    if not HAS_PYAUTOGUI:
        return False, "pyautogui quraşdırılmayıb — avtomatik göndəriş alınmadı."

    try:
        time.sleep(load_delay)
        _focus_whatsapp_window()
        time.sleep(0.6)
        pyautogui.press("enter")
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def send_whatsapp_message(
    message: str,
    phone_number: str = "",
    recipient_name: str = "",
    send_now: bool = False,
    app_target: str = "auto",
) -> str:
    if not message or not message.strip():
        return "Mesaj boş ola bilməz."

    app_target = (app_target or "auto").strip().lower()
    if app_target not in {"auto", "desktop", "web"}:
        app_target = "auto"

    normalized_phone = ""
    if phone_number and phone_number.strip():
        try:
            normalized_phone = _normalize_phone(phone_number)
        except ValueError as exc:
            return str(exc)

    resolved_name = recipient_name.strip() if recipient_name else ""
    contact = _find_contact(resolved_name) if resolved_name else None

    if contact and not normalized_phone:
        normalized_phone = _resolve_contact_phone(contact)
        resolved_name = (
            str(contact.get("display_name", resolved_name)).strip()
            or resolved_name
        )
        contact_source = contact.get("_source", "")
    else:
        contact_source = ""

    if app_target in {"auto", "desktop"}:
        if normalized_phone:
            source_note = " (kontaktlardan tapıldı)" if contact_source else ""
            label = resolved_name or f"+{normalized_phone}"
            ok, detail = _open_whatsapp_desktop_via_scheme(
                normalized_phone, message, include_text=True
            )
            if ok:
                if not send_now:
                    return f"WhatsApp Desktop içində {label}{source_note} üçün qaralama mesaj açıldı."
                ok_send, send_detail = _send_prefilled_message(DESKTOP_LOAD_DELAY)
                if ok_send:
                    return f"WhatsApp Desktop üzərindən {label}{source_note} nəfərə mesaj göndərildi."
                return (
                    f"WhatsApp Desktop söhbəti açıldı, amma avtomatik göndərim alınmadı: {send_detail}. "
                    "Mesaj qutusuna gəlib Enter'a basmaq kifayətdir."
                )
            if app_target == "desktop":
                return f"WhatsApp Desktop açılarkən xəta baş verdi: {detail}"

    if not normalized_phone:
        if resolved_name:
            return (
                f"'{resolved_name}' üçün qeyd olunmuş bir telefon nömrəsi tapılmadı. "
                "İstəsən, əvvəlcə həmin şəxsi nömrəsi ilə yadda saxla."
            )
        return "WhatsApp mesajı üçün kontakt adı və ya telefon nömrəsi tələb olunur."

    source_note = " (kontaktlardan tapıldı)" if contact_source else ""
    label = resolved_name or f"+{normalized_phone}"

    ok, detail = _open_whatsapp_web(normalized_phone, message, include_text=True)
    if not ok:
        return detail

    if not send_now:
        return (
            f"WhatsApp Web {label}{source_note} üçün brauzerdə açıldı. "
            "Göndərmək üçün Enter'a bas."
        )

    if not HAS_PYAUTOGUI:
        return (
            f"WhatsApp Web {label}{source_note} üçün açıldı və mesaj hazırdır. "
            "Avtomatik göndərim üçün pyautogui lazımdır; Enter'a basaraq göndərə bilərsən."
        )

    try:
        time.sleep(WEB_LOAD_DELAY)
        pyautogui.press("enter")
        return f"WhatsApp Web üzərindən {label}{source_note} şəxsə mesaj göndərildi."
    except Exception as exc:
        return (
            f"WhatsApp Web açıldı, amma, avtomatik göndəriş baş tutmadı: {exc}. "
            "Enter'a basaraq göndərə bilərsən."
        )


# ── vCard (.vcf) rehber idxalı ──────────────────────────────────────────────

def _unfold_vcf_lines(text: str) -> list[str]:
    unfolded = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def import_phone_book_from_vcf(vcf_path: str) -> str:
    source = Path(vcf_path).expanduser()
    if not source.exists():
        return f"Rehber faylı tapılmadı: {source}"

    try:
        text = source.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return f"Rehber faylı oxunmadı: {exc}"

    imported = 0
    skipped = 0

    def _flush_card(lines: list[str]):
        nonlocal imported, skipped
        if not lines:
            return
        display_name = ""
        numbers = []
        for line in lines:
            upper = line.upper()
            if upper.startswith("FN:"):
                display_name = line.split(":", 1)[1].strip()
            elif upper.startswith("N:") and not display_name:
                parts = [part.strip() for part in line.split(":", 1)[1].split(";") if part.strip()]
                if parts:
                    display_name = " ".join(reversed(parts[:2])).strip()
            elif "TEL" in upper and ":" in line:
                number = line.split(":", 1)[1].strip()
                if number:
                    numbers.append(number)

        if not display_name or not numbers:
            skipped += 1
            return

        normalized_numbers = []
        for raw_number in numbers:
            try:
                normalized_numbers.append("+" + _normalize_phone(raw_number))
            except ValueError:
                continue
        if not normalized_numbers:
            skipped += 1
            return

        try:
            upsert_contact(
                display_name=display_name,
                phones=normalized_numbers,
                source="vcf_import",
            )
            imported += 1
        except (TypeError, ValueError):
            skipped += 1

    current_lines = []
    for line in _unfold_vcf_lines(text):
        if line.upper() == "BEGIN:VCARD":
            current_lines = []
        elif line.upper() == "END:VCARD":
            _flush_card(current_lines)
            current_lines = []
        else:
            current_lines.append(line)

    return f"{imported} rehber şəxsi SQL kontaktlarına idxal edildi, {skipped} qeyd atlandı."
