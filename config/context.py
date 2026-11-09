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
        "attendance", "Pointage", "clock", HR | KIOSK,
        [
            ("Borne de pointage", "attendance:kiosk", HR | KIOSK),
            ("Présences", "attendance:list", HR),
            ("Rapport mensuel", "attendance:monthly", HR),
            ("Journal des scans", "attendance:logs", HR),
        ],
    ),
    (
        "leaves", "Congés", "calendar", STAFF,
        [
            ("Mes congés", "leaves:mine", STAFF),
            ("Demandes à traiter", "leaves:pending", {"admin", "hr", "manager"}),
            ("Toutes les demandes", "leaves:list", HR),
            ("Calendrier", "leaves:calendar", STAFF),
            ("Types de congés", "leaves:type_list", HR),
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


def branding(request):
    """Nom du produit, navigation latérale et entreprise courante, pour tous les templates."""
    user = getattr(request, "user", None)
    authenticated = bool(user and user.is_authenticated)
    return {
        "company": getattr(user, "company", None) if authenticated else None,
        "APP_NAME": settings.APP_NAME,
        "APP_TAGLINE": settings.APP_TAGLINE,
        "nav_sections": _build_nav(request, user),
    }
