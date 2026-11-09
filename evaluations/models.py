from django.conf import settings
from django.db import models

from companies.models import CompanyOwnedModel

CRITERIA = [
    ("quality", "Qualité du travail"),
    ("productivity", "Productivité et respect des délais"),
    ("attendance", "Assiduité et ponctualité"),
    ("teamwork", "Esprit d'équipe"),
    ("initiative", "Initiative et autonomie"),
    ("communication", "Communication"),
]
SCORE_CHOICES = [(5, "5 — Excellent"), (4, "4 — Très bien"), (3, "3 — Satisfaisant"), (2, "2 — À améliorer"), (1, "1 — Insuffisant")]


class Evaluation(CompanyOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        SUBMITTED = "submitted", "Transmise à l'employé"
        ACKNOWLEDGED = "acknowledged", "Prise en compte par l'employé"

    employee = models.ForeignKey(
        "employees.Employee", verbose_name="Employé", on_delete=models.CASCADE, related_name="evaluations"
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Évaluateur", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    period = models.CharField("Période évaluée", max_length=60, help_text="Ex. : Année 2026, 1er semestre 2026")
    date = models.DateField("Date de l'entretien")
    scores = models.JSONField("Notes par critère", default=dict)
    strengths = models.TextField("Points forts", blank=True)
    improvements = models.TextField("Axes d'amélioration", blank=True)
    objectives = models.TextField("Objectifs de la prochaine période", blank=True)
    employee_comment = models.TextField("Commentaire de l'employé", blank=True)
    status = models.CharField("Statut", max_length=14, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField("Créée le", auto_now_add=True)

    class Meta:
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.employee} — {self.period}"

    @property
    def average(self):
        values = [v for v in self.scores.values() if isinstance(v, int)]
        return round(sum(values) / len(values), 2) if values else None

    @property
    def score_rows(self):
        return [(label, self.scores.get(key)) for key, label in CRITERIA]
