"""SQLite database tool declaration-ları."""

DATABASE_TOOL_DECLARATIONS = [
    {
        "name": "database_query",
        "description": (
            "VICTOR-un öz SQLite bazasında istənilən istifadəçi cədvəlini oxuyur və dəyişir. "
            "SELECT və INSERT birbaşa icra olunur. UPDATE və DELETE yalnız istifadəçinin açıq təsdiqindən "
            "sonra əvvəlki confirmation_id ilə icra edilir. sqlite_master və digər SQLite sistem obyektlərinə "
            "birbaşa giriş qadağandır. Bir dəfəlik SELECT/INSERT/UPDATE/DELETE statement istifadə et."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "sql": {
                    "type": "STRING",
                    "description": "İcra ediləcək tək SQLite SELECT, INSERT, UPDATE və ya DELETE statement"
                },
                "confirmation_id": {
                    "type": "STRING",
                    "description": "UPDATE/DELETE üçün VICTOR-un verdiyi əvvəlki confirmation_id"
                }
            },
            "required": ["sql"]
        }
    }
]
