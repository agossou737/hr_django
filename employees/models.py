from django.conf import settings
from django.db import models
from django.db.models import Max

from companies.models import CompanyOwnedModel


class Department(CompanyOwnedModel):
    name = models.CharField("Nom", max_length=120)
    description = models.TextField("Description", blank=True)
    head = models.ForeignKey(
        "Employee",
        verbose_name="Responsable",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_departments",
    )

    class Meta:
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uniq_department_per_company")
        ]

    def __str__(self):
        return self.name


class Position(CompanyOwnedModel):
    title = models.CharField("Intitulé du poste", max_length=120)
    department = models.ForeignKey(
        Department,
        verbose_name="Département",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positions",
    )
    base_salary = models.DecimalField(
        "Salaire de base indicatif (FCFA)", max_digits=12, decimal_places=0, default=0
    )

    class Meta:
        verbose_name = "Poste"
        verbose_name_plural = "Postes"
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(fields=["company", "title"], name="uniq_position_per_company")
        ]

    def __str__(self):
        return self.title


class Employee(CompanyOwnedModel):
    class Gender(models.TextChoices):
        MALE = "M", "Masculin"
        FEMALE = "F", "Féminin"

    class MaritalStatus(models.TextChoices):
        SINGLE = "single", "Célibataire"
        MARRIED = "married", "Marié(e)"
        DIVORCED = "divorced", "Divorcé(e)"
        WIDOWED = "widowed", "Veuf/Veuve"

    class Status(models.TextChoices):
        ACTIVE = "active", "Actif"
        ON_LEAVE = "on_leave", "En congé"
        SUSPENDED = "suspended", "Suspendu"
        LEFT = "left", "Sorti"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="Compte utilisateur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee",
    )
    matricule = models.CharField("Matricule", max_length=20, blank=True)
    photo = models.ImageField("Photo", upload_to="employees/photos/", blank=True)

    first_name = models.CharField("Prénoms", max_length=120)
    last_name = models.CharField("Nom", max_length=120)
    gender = models.CharField("Sexe", max_length=1, choices=Gender.choices)
    birth_date = models.DateField("Date de naissance", null=True, blank=True)
    birth_place = models.CharField("Lieu de naissance", max_length=120, blank=True)
    nationality = models.CharField("Nationalité", max_length=60, default="Béninoise")
    marital_status = models.CharField(
        "Situation matrimoniale", max_length=20, choices=MaritalStatus.choices, blank=True
    )
    dependents = models.PositiveSmallIntegerField("Nombre d'enfants à charge", default=0)

    email = models.EmailField("E-mail", blank=True)
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    address = models.CharField("Adresse", max_length=255, blank=True)
    emergency_contact_name = models.CharField("Contact d'urgence", max_length=120, blank=True)
    emergency_contact_phone = models.CharField("Téléphone d'urgence", max_length=30, blank=True)

    cnss_number = models.CharField("N° CNSS", max_length=30, blank=True)
    ifu = models.CharField("IFU", max_length=20, blank=True)

    department = models.ForeignKey(
        Department,
        verbose_name="Département",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    position = models.ForeignKey(
        Position,
        verbose_name="Poste",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    manager = models.ForeignKey(
        "self",
        verbose_name="Supérieur hiérarchique",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subordinates",
    )
    hire_date = models.DateField("Date d'embauche")
    exit_date = models.DateField("Date de sortie", null=True, blank=True)
    status = models.CharField("Statut", max_length=20, choices=Status.choices, default=Status.ACTIVE)

    created_at = models.DateTimeField("Créé le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifié le", auto_now=True)

    class Meta:
        verbose_name = "Employé"
        verbose_name_plural = "Employés"
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "matricule"],
                condition=~models.Q(matricule=""),
                name="uniq_matricule_per_company",
            )
        ]

    def __str__(self):
        return f"{self.full_name} ({self.matricule})" if self.matricule else self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def _next_matricule(self):
        prefix = "EMP"
        last = (
            Employee.objects.filter(company=self.company, matricule__startswith=prefix)
            .exclude(pk=self.pk)
            .aggregate(m=Max("matricule"))["m"]
        )
        number = int(last[len(prefix):]) + 1 if last and last[len(prefix):].isdigit() else 1
        return f"{prefix}{number:04d}"

    def save(self, *args, **kwargs):
        if not self.matricule:
            self.matricule = self._next_matricule()
        super().save(*args, **kwargs)


class Contract(CompanyOwnedModel):
    class ContractType(models.TextChoices):
        CDI = "cdi", "CDI"
        CDD = "cdd", "CDD"
        INTERNSHIP = "internship", "Stage"
        CONSULTANT = "consultant", "Prestation / Consultant"
        APPRENTICE = "apprentice", "Apprentissage"

    employee = models.ForeignKey(
        Employee, verbose_name="Employé", on_delete=models.CASCADE, related_name="contracts"
    )
    contract_type = models.CharField("Type de contrat", max_length=20, choices=ContractType.choices)
    start_date = models.DateField("Date de début")
    end_date = models.DateField("Date de fin", null=True, blank=True)
    base_salary = models.DecimalField("Salaire de base mensuel (FCFA)", max_digits=12, decimal_places=0)
    weekly_hours = models.DecimalField("Heures hebdomadaires", max_digits=4, decimal_places=1, default=40)
    trial_period_months = models.PositiveSmallIntegerField("Période d'essai (mois)", default=0)
    notes = models.TextField("Observations", blank=True)
    is_current = models.BooleanField("Contrat en cours", default=True)

    class Meta:
        verbose_name = "Contrat"
        verbose_name_plural = "Contrats"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.get_contract_type_display()} — {self.employee.full_name}"
