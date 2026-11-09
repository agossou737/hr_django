"""Création des accès de connexion des employés (mot de passe temporaire à changer à la première connexion)."""
import secrets

from django.conf import settings
from django.core.mail import send_mail

from .models import User

ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class AccessError(ValueError):
    pass


def temp_password(length=10):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def create_access(employee, email=None, role=User.Role.EMPLOYEE, send_email=True):
    """Crée le compte de l'employé, le rattache à sa fiche et renvoie (user, mot_de_passe_temporaire)."""
    if employee.user_id:
        raise AccessError("Cet employé a déjà un accès.")
    if role not in (User.Role.EMPLOYEE, User.Role.MANAGER):
        raise AccessError("Rôle non autorisé pour un accès employé.")
    email = (email or employee.email or "").strip().lower()
    if not email:
        raise AccessError("Aucune adresse e-mail renseignée.")
    if User.objects.filter(email__iexact=email).exists():
        raise AccessError(f"L'adresse {email} est déjà utilisée par un autre compte.")
    password = temp_password()
    user = User.objects.create_user(email=email, password=password, first_name=employee.first_name,
                                    last_name=employee.last_name, company=employee.company, role=role,
                                    must_change_password=True)
    employee.user = user
    if not employee.email:
        employee.email = email
    employee.save(update_fields=["user", "email"])
    if send_email:
        send_invitation(user, password)
    return user, password


def send_invitation(user, password):
    base = getattr(settings, "SITE_URL", "")
    body = (f"Bonjour {user.first_name},\n\nVotre accès à {settings.APP_NAME} ({user.company.name}) a été créé.\n\n"
            f"Adresse de connexion : {base}/compte/connexion/\nIdentifiant : {user.email}\n"
            f"Mot de passe temporaire : {password}\n\n"
            "Vous devrez choisir un nouveau mot de passe dès votre première connexion.")
    try:
        send_mail(f"[{settings.APP_NAME}] Votre accès", body, None, [user.email], fail_silently=True)
    except Exception:  # l'e-mail ne doit jamais bloquer la création
        pass
