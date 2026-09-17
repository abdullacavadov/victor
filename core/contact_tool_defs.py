"""Google Contacts CRUD və SQL kontakt axtarış tool declaration-ları."""

CONTACT_TOOL_DECLARATIONS = [
    {
        "name": "create_contact",
        "description": "Google Contacts-da yeni kontakt yaradır. Local SQL kontakt bazasını da sinxronlaşdırır; yalnız açıq create əmri üçün istifadə et.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "display_name": {"type": "STRING", "description": "Kontaktın adı"},
                "phone_number": {"type": "STRING", "description": "Beynəlxalq telefon nömrəsi"},
            },
            "required": ["display_name", "phone_number"],
        },
    },
    {
        "name": "update_contact",
        "description": "Google Contacts-da mövcud kontaktı yeniləyir və SQL kontakt bazasını sinxronlaşdırır. Təhlükəsizlik üçün yalnız məlum Google resource_name ilə işləyir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "resource_name": {"type": "STRING", "description": "Google contact resource name, məsələn people/c123"},
                "display_name": {"type": "STRING", "description": "Yeni kontakt adı"},
                "phone_number": {"type": "STRING", "description": "Yeni beynəlxalq telefon nömrəsi"},
            },
            "required": ["resource_name", "display_name", "phone_number"],
        },
    },
    {
        "name": "delete_contact",
        "description": "Google Contacts-dan kontaktı silir və uyğun SQL kontaktını deaktiv edir. Təhlükəsizlik üçün yalnız məlum Google resource_name ilə işləyir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "resource_name": {"type": "STRING", "description": "Google contact resource name, məsələn people/c123"},
            },
            "required": ["resource_name"],
        },
    },
    {
        "name": "search_contacts",
        "description": "VICTOR-un SQL kontakt bazasında kontakt axtarır. Ad, kontakt açarı və ya telefon nömrəsi ilə axtarış üçün istifadə et. Kontakt məlumatını yoxlamaq üçün shell_run və sqlite3 istifadə etmə.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Kontakt adı və ya axtarış ifadəsi"},
                "phone": {"type": "STRING", "description": "İxtiyari telefon nömrəsi"},
                "limit": {"type": "NUMBER", "description": "Maksimum nəticə sayı; defolt 10"},
            },
        },
    },
]
