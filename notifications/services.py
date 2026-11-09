import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import Notification

log = logging.getLogger(__name__)


def notify(users, title, message="", url="", email=True):
    """Crée une notification interne par utilisateur et envoie un e-mail (sans jamais échouer)."""
    created = []
    seen = set()
    for user in users:
        if user is None or user.pk in seen or not user.company_id:
            continue
        seen.add(user.pk)
        created.append(Notification.objects.create(company=user.company, user=user, title=title[:150],
                                                   message=message, url=url))
        if email and user.email:
            try:
                body = message + (f"\n\n{settings.SITE_URL}{url}" if url and getattr(settings, "SITE_URL", "") else "")
                send_mail(f"[{settings.APP_NAME}] {title}", body or title, None, [user.email], fail_silently=True)
            except Exception:  # pragma: no cover - l'e-mail ne doit jamais bloquer le métier
                log.exception("Échec d'envoi d'e-mail")
    return created


def hr_users(company):
    from accounts.models import User

    return list(User.objects.filter(company=company, is_active=True, role__in=["admin", "hr"]))


def unread_count(user):
    return Notification.objects.filter(user=user, is_read=False).count()
