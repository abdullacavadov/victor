"""Google Contacts CRUD tool declarations."""

CONTACT_TOOL_DECLARATIONS = [
    {
        "name": "create_contact",
        "description": "Google Contacts-da yeni kontakt yaradır. Local phone book-u dəyişmir; yalnız açıq create əmri üçün istifadə et.",
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
        "description": "Google Contacts-da mövcud kontaktı yeniləyir. Təhlükəsizlik üçün yalnız məlum Google resource_name ilə işləyir.",
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
        "description": "Google Contacts-dan kontaktı silir. Təhlükəsizlik üçün yalnız məlum Google resource_name ilə işləyir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "resource_name": {"type": "STRING", "description": "Google contact resource name, məsələn people/c123"},
            },
            "required": ["resource_name"],
        },
    },
]
