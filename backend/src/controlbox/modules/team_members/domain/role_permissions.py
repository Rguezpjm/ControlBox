TEAM_ROLE_DEFINITIONS: dict[str, dict] = {
    "owner": {
        "name": "Owner",
        "description": "Full account access including billing and team management",
        "level": 100,
        "permissions": ["*"],
    },
    "administrator": {
        "name": "Administrator",
        "description": "Full platform access except billing",
        "level": 90,
        "permissions": [
            "tenants.read", "users.read", "users.manage", "roles.read", "roles.manage",
            "sessions.read", "sessions.manage", "audit.read", "team_members.read", "team_members.manage",
            "websites.read", "websites.manage", "wordpress.read", "wordpress.manage",
            "databases.read", "databases.manage", "supabase.read", "supabase.manage",
            "dns.read", "dns.manage", "files.read", "files.manage", "ftp.read", "ftp.manage",
            "backups.read", "backups.manage", "monitoring.read", "security.read", "security.manage",
            "platform.read", "platform.manage",
        ],
    },
    "website_manager": {
        "name": "Website Manager",
        "description": "Manage websites and view statistics",
        "level": 50,
        "permissions": [
            "websites.read", "websites.manage", "wordpress.read", "wordpress.manage",
            "monitoring.read", "files.read",
        ],
    },
    "dns_manager": {
        "name": "DNS Manager",
        "description": "Manage DNS zones and records",
        "level": 50,
        "permissions": ["dns.read", "dns.manage"],
    },
    "database_manager": {
        "name": "Database Manager",
        "description": "Manage databases and view backups",
        "level": 50,
        "permissions": ["databases.read", "databases.manage", "backups.read"],
    },
    "ftp_manager": {
        "name": "FTP Manager",
        "description": "Manage FTP accounts and files",
        "level": 50,
        "permissions": ["ftp.read", "ftp.manage", "files.read", "files.manage"],
    },
    "billing_manager": {
        "name": "Billing Manager",
        "description": "View and manage billing",
        "level": 60,
        "permissions": ["billing.read", "billing.manage", "tenants.read", "audit.read"],
    },
    "read_only": {
        "name": "Read Only",
        "description": "View-only access to all resources",
        "level": 10,
        "permissions": [
            "tenants.read", "users.read", "roles.read", "sessions.read", "audit.read",
            "team_members.read", "websites.read", "wordpress.read", "databases.read",
            "supabase.read", "dns.read", "files.read", "ftp.read", "backups.read",
            "monitoring.read", "security.read", "billing.read",
        ],
    },
}
