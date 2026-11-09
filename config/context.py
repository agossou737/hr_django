from django.conf import settings
from django.urls import reverse

ICON_DASHBOARD = "M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
ICON_USERS = "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
ICON_BUILDING = "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-2 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
ICON_BRIEFCASE = "M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"


def _section(request):
    match = getattr(request, "resolver_match", None)
    if not match:
        return ""
    if match.url_name == "dashboard":
        return "dashboard"
    if match.namespace == "employees":
        if match.url_name.startswith("department"):
            return "departments"
        if match.url_name.startswith("position"):
            return "positions"
        return "employees"
    return ""


def branding(request):
    """Nom du produit, navigation latérale et section active, pour tous les templates."""
    user = getattr(request, "user", None)
    nav = [("dashboard", "Tableau de bord", reverse("dashboard"), ICON_DASHBOARD)]
    if user and user.is_authenticated and user.company_id and user.can_manage_hr:
        nav += [
            ("employees", "Employés", reverse("employees:list"), ICON_USERS),
            ("departments", "Départements", reverse("employees:department_list"), ICON_BUILDING),
            ("positions", "Postes", reverse("employees:position_list"), ICON_BRIEFCASE),
        ]
    return {
        "company": getattr(user, "company", None) if user and user.is_authenticated else None,
        "APP_NAME": settings.APP_NAME,
        "APP_TAGLINE": settings.APP_TAGLINE,
        "nav_items": [
            {"key": k, "label": label, "url": url, "icon": icon} for k, label, url, icon in nav
        ],
        "nav_section": _section(request),
    }
