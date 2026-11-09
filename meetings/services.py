from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from config.pdfdocs import build_letter_pdf
from notifications.services import notify

from .models import Meeting


def can_organize(user):
    return user.is_authenticated and user.company_id is not None and user.role in ("admin", "hr", "manager")


def visible_meetings(user):
    qs = Meeting.objects.filter(company=user.company)
    if user.can_manage_hr:
        return qs
    return qs.filter(Q(organizer=user) | Q(participants__user=user)).distinct()


def can_edit(user, meeting):
    return user.is_authenticated and user.company_id == meeting.company_id and (
        user.can_manage_hr or meeting.organizer_id == user.pk)


def can_view(user, meeting):
    return user.is_authenticated and user.company_id == meeting.company_id and (
        user.can_manage_hr or meeting.organizer_id == user.pk or meeting.participants.filter(user=user).exists())


def _participant_users(meeting):
    return [e.user for e in meeting.participants.select_related("user") if e.user_id and e.user.is_active]


def notify_invitation(meeting, update=False):
    notify([u for u in _participant_users(meeting) if u.pk != meeting.organizer_id],
           ("Réunion modifiée : " if update else "Convocation : ") + meeting.title,
           f"Le {meeting.date:%d/%m/%Y} à {meeting.start_time:%H:%M}" + (f" — {meeting.location}" if meeting.location else ""),
           reverse("meetings:detail", args=[meeting.pk]))


def publish_minutes(meeting):
    meeting.status = Meeting.Status.HELD
    meeting.minutes_published_at = timezone.now()
    meeting.save(update_fields=["status", "minutes_published_at"])
    notify([u for u in _participant_users(meeting) if u.pk != meeting.organizer_id],
           f"Compte rendu disponible : {meeting.title}", "", reverse("meetings:detail", args=[meeting.pk]))


def cancel(meeting):
    meeting.status = Meeting.Status.CANCELLED
    meeting.save(update_fields=["status"])
    notify(_participant_users(meeting), f"Réunion annulée : {meeting.title}", f"Prévue le {meeting.date:%d/%m/%Y}.",
           reverse("meetings:detail", args=[meeting.pk]))


def _facts(m):
    when = f"{m.date:%d/%m/%Y} de {m.start_time:%H:%M}" + (f" à {m.end_time:%H:%M}" if m.end_time else "")
    org = m.organizer.get_full_name() if m.organizer else "—"
    return [("Réunion", m.title), ("Date et heure", when), ("Lieu", m.location or "—"), ("Organisateur", org),
            ("Participants", ", ".join(e.full_name for e in m.participants.all()) or "—")]


def convocation_pdf(m):
    return build_letter_pdf(m.company, "Convocation à une réunion", m.reference, _facts(m),
                            [("Ordre du jour", m.agenda or "À préciser.")])


def minutes_pdf(m):
    paras = [("Ordre du jour", m.agenda or "—"), ("Compte rendu", m.minutes or "(non rédigé)")]
    actions = list(m.actions.select_related("owner"))
    if actions:
        paras.append(("Actions et décisions", "\n".join(
            f"• {a.description} — {a.owner.full_name if a.owner else 'non assigné'}"
            + (f" (avant le {a.due_date:%d/%m/%Y})" if a.due_date else "") + (" [fait]" if a.done else "")
            for a in actions)))
    org = m.organizer.get_full_name() if m.organizer else ""
    return build_letter_pdf(m.company, "Compte rendu de réunion", m.reference, _facts(m), paras,
                            signatures=[("L'organisateur", org, "")])
