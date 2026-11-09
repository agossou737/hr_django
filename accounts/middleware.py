from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Tant que le mot de passe temporaire n'a pas été changé, seules les pages de changement/déconnexion sont accessibles."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and getattr(user, "must_change_password", False):
            allowed = (reverse("accounts:password_change"), reverse("accounts:logout"))
            if request.path not in allowed and not request.path.startswith(("/static/", "/admin/")):
                return redirect("accounts:password_change")
        return self.get_response(request)
