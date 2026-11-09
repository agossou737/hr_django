from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email):
        """Connexion insensible à la casse de l'adresse e-mail."""
        return self.get(email__iexact=email.strip())

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", User.Role.ADMIN)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """Utilisateur identifié par e-mail, rattaché à une entreprise et à un rôle."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrateur"
        HR = "hr", "Responsable RH"
        MANAGER = "manager", "Manager"
        EMPLOYEE = "employee", "Employé"
        KIOSK = "kiosk", "Borne de pointage"

    username = None
    email = models.EmailField("E-mail", unique=True)
    company = models.ForeignKey(
        "companies.Company",
        verbose_name="Entreprise",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
    )
    role = models.CharField("Rôle", max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    must_change_password = models.BooleanField("Doit changer son mot de passe", default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def can_manage_hr(self):
        return self.role in (self.Role.ADMIN, self.Role.HR)

    @property
    def is_kiosk(self):
        return self.role == self.Role.KIOSK
