from django.conf import settings
from django.urls import NoReverseMatch, reverse

ICONS = {
    "dashboard": "M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z",
    "users": "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
    "clock": "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
    "calendar": "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
    "cash": "M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z",
    "recruit": "M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z",
    "star": "M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z",
    "folder": "M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z",
    "bell": "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
    "mail": "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    "tool": "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
    "receipt": "M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z",
    "academic": "M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z",
    "shield": "M12 9v3.75m0-10.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.75c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285zM12 15.75h.008v.008H12v-.008z",
    "cube": "M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9",
    "group": "M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z",
    "cog": "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065zM15 12a3 3 0 11-6 0 3 3 0 016 0z",
}

HR = {"admin", "hr"}
STAFF = {"admin", "hr", "manager", "employee"}
KIOSK = {"kiosk"}

# (clé, libellé, icône, rôles autorisés, [(libellé, nom d'URL, rôles autorisés)])
SECTIONS = [
    ("dashboard", "Tableau de bord", "dashboard", STAFF, [("Vue d'ensemble", "dashboard", STAFF)]),
    (
        "employees", "Employés", "users", HR,
        [
            ("Employés", "employees:list", HR),
            ("Départements", "employees:department_list", HR),
            ("Postes", "employees:position_list", HR),
        ],
    ),
    (
        "attendance", "Pointage", "clock", STAFF | KIOSK,
        [
            ("Borne de pointage", "attendance:kiosk", HR | KIOSK),
            ("Présences", "attendance:list", HR),
            ("Rapport mensuel", "attendance:monthly", HR),
            ("Journal des scans", "attendance:logs", HR),
            ("Pointer par empreinte", "biometrics:clock", HR | KIOSK | {"manager", "employee"}),
            ("Mes appareils biométriques", "biometrics:mine", {"manager", "employee"}),
            ("Empreintes et lecteurs", "biometrics:manage", HR),
        ],
    ),
    (
        "leaves", "Congés", "calendar", STAFF,
        [
            ("Mes congés", "leaves:mine", STAFF),
            ("Demandes à traiter", "leaves:pending", {"admin", "hr", "manager"}),
            ("Mes remplacements", "leaves:replacements", STAFF),
            ("Mes permissions", "leaves:permission_mine", STAFF),
            ("Permissions à traiter", "leaves:permission_pending", {"admin", "hr", "manager"}),
            ("Toutes les permissions", "leaves:permission_list", HR),
            ("Toutes les demandes", "leaves:list", HR),
            ("Calendrier", "leaves:calendar", STAFF),
            ("Types de congés", "leaves:type_list", HR),
        ],
    ),
    (
        "explanations", "Explications", "mail", STAFF,
        [
            ("Mes demandes d'explication", "explanations:mine", {"manager", "employee"}),
            ("Toutes les explications", "explanations:list", HR),
        ],
    ),
    (
        "payroll", "Paie", "cash", STAFF,
        [
            ("Mes bulletins", "payroll:mine", STAFF),
            ("Périodes de paie", "payroll:period_list", HR),
            ("Paramètres de paie", "payroll:settings", HR),
        ],
    ),
    (
        "recruitment", "Recrutement", "recruit", HR,
        [
            ("Offres d'emploi", "recruitment:job_list", HR),
            ("Candidatures", "recruitment:application_list", HR),
        ],
    ),
    (
        "evaluations", "Évaluations", "star", STAFF,
        [
            ("Mes évaluations", "evaluations:mine", STAFF),
            ("Évaluations de l'équipe", "evaluations:list", {"admin", "hr", "manager"}),
        ],
    ),
    (
        "expenses", "Notes de frais", "receipt", STAFF,
        [
            ("Mes notes de frais", "expenses:mine", STAFF),
            ("Notes à valider", "expenses:pending", {"admin", "hr", "manager"}),
            ("Toutes les notes", "expenses:list", HR),
        ],
    ),
    (
        "training", "Formations", "academic", STAFF,
        [("Mes formations", "training:mine", STAFF), ("Catalogue et inscriptions", "training:list", HR)],
    ),
    (
        "discipline", "Discipline", "shield", STAFF,
        [("Mes mesures", "discipline:mine", {"manager", "employee"}), ("Mesures disciplinaires", "discipline:list", HR)],
    ),
    (
        "assets", "Matériel", "cube", STAFF,
        [("Inventaire", "assets:list", HR), ("Mon matériel", "assets:mine", STAFF)],
    ),
    (
        "meetings", "Réunions", "group", STAFF,
        [("Mes réunions", "meetings:mine", STAFF), ("Toutes les réunions", "meetings:list", HR)],
    ),
    (
        "documents", "Documents", "folder", STAFF,
        [("Documents RH", "documents:list", HR), ("Documents à renouveler", "documents:expiring", HR), ("Mes documents", "documents:mine", {"manager", "employee"})],
    ),
    (
        "settings", "Paramètres", "cog", HR,
        [
            ("Entreprise et horaires", "companies:settings", HR),
            ("Jours fériés", "companies:holidays", HR),
            ("Utilisateurs", "accounts:user_list", HR),
        ],
    ),
]


def _build_nav(request, user):
    """Construit la navigation visible par l'utilisateur ; ignore les modules non installés."""
    if not (user and user.is_authenticated and user.company_id):
        return []
    role = user.role
    path = request.path
    sections = []
    for key, label, icon, roles, children in SECTIONS:
        if role not in roles:
            continue
        items = []
        for child_label, url_name, child_roles in children:
            if role not in child_roles:
                continue
            try:
                url = reverse(url_name)
            except NoReverseMatch:
                continue
            items.append({"label": child_label, "url": url, "active": False})
        if not items:
            continue
        active_item = None
        for item in items:
            if path == item["url"] or (item["url"] != "/" and path.startswith(item["url"])):
                if active_item is None or len(item["url"]) > len(active_item["url"]):
                    active_item = item
        if active_item:
            active_item["active"] = True
        sections.append(
            {
                "key": key,
                "label": label,
                "icon": ICONS[icon],
                "url": items[0]["url"],
                "items": items,
                "active": active_item is not None,
            }
        )
    return sections


def _unread(user):
    try:
        from notifications.services import unread_count

        return unread_count(user)
    except Exception:  # base non migrée, etc.
        return 0


def branding(request):
    """Nom du produit, navigation latérale et entreprise courante, pour tous les templates."""
    user = getattr(request, "user", None)
    authenticated = bool(user and user.is_authenticated)
    return {
        "company": getattr(user, "company", None) if authenticated else None,
        "APP_NAME": settings.APP_NAME,
        "APP_TAGLINE": settings.APP_TAGLINE,
        "nav_sections": _build_nav(request, user),
        "unread_notifications": _unread(user) if authenticated and user.company_id else 0,
    }
