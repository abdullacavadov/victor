"""VICTOR SQLite database_query alətinin deklarasiyası."""

DATABASE_TOOL_DECLARATIONS = [
    {
        "name": "database_query",
        "description": (
            "VICTOR-un daxili SQLite verilənlər bazasında SQL sorğusu icra edir. "
            "İstənilən istifadəçi cədvəlindən SELECT oxuya və INSERT əlavə edə bilər. "
            "UPDATE və DELETE əməliyyatları üçün əvvəlcə istifadəçidən açıq təsdiq tələb olunur. "
            "Verilənlər bazasına shell_run və sqlite3 executable vasitəsilə deyil, "
            "birbaşa Python SQLite bağlantısı ilə giriş edir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "sql": {
                    "type": "STRING",
                    "description": (
                        "İcra ediləcək tək SQL statement. "
                        "SELECT, INSERT, UPDATE və ya DELETE ola bilər."
                    ),
                },
                "confirmation_id": {
                    "type": "STRING",
                    "description": (
                        "UPDATE və ya DELETE üçün VICTOR-un əvvəlki təsdiq cavabından "
                        "alınan confirmation ID. İlk çağırışda boş saxlanılır."
                    ),
                },
            },
            "required": ["sql"],
        },
    }
]
