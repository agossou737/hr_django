from django.urls import reverse

from config.pdfdocs import build_letter_pdf
from notifications.services import notify

from .models import TrainingParticipant


def enroll(training, employees):
    added = []
    for emp in employees:
        p, created = TrainingParticipant.objects.get_or_create(company=training.company, training=training, employee=emp)
        if created:
            added.append(p)
            if emp.user_id:
                notify([emp.user], f"Formation : {training.title}",
                       f"Du {training.start_date:%d/%m/%Y} au {training.end_date:%d/%m/%Y}"
                       + (f" — {training.location}" if training.location else ""), reverse("training:mine"))
    return added


def certificate_pdf(p):
    t, e = p.training, p.employee
    facts = [("Bénéficiaire", f"{e.full_name} ({e.matricule})"), ("Formation", t.title),
             ("Organisme", t.provider or "—"), ("Période", f"du {t.start_date:%d/%m/%Y} au {t.end_date:%d/%m/%Y}"),
             ("Lieu", t.location or "—")]
    return build_letter_pdf(t.company, "Attestation de formation", f"FORM-{t.pk:04d}-{p.pk:05d}", facts,
                            [f"Nous attestons que {e.full_name} a suivi la formation « {t.title} » dans les conditions indiquées ci-dessus."],
                            signatures=[("La Direction", "", "")], stamp="FORMATION SUIVIE")
